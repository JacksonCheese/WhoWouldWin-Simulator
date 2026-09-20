"""Create and render self-contained Blender projects with source provenance."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

from whowouldwin.cinematic.episodes.adapter import adapt_replay
from whowouldwin.cinematic.episodes.project import file_hash, write_json
from whowouldwin.cinematic.episodes.schemas import EventLog
from whowouldwin.simulation.replay import load_replay

from .adapter import build_hybrid_plan, build_prototype_plan
from .schemas import BlenderProjectManifest, BlenderSequencePlan


def _runtime_path() -> Path:
    return Path(__file__).with_name("runtime.py")


def _asset_runtime_path() -> Path:
    return Path(__file__).parents[1] / "assets" / "blender_import.py"


def find_blender(explicit: Path | None = None) -> Path | None:
    candidates = [
        explicit,
        Path(os.environ["WWS_BLENDER"]) if os.environ.get("WWS_BLENDER") else None,
        Path(found) if (found := shutil.which("blender")) else None,
        Path("/Applications/Blender.app/Contents/MacOS/Blender"),
    ]
    return next((p.resolve() for p in candidates if p and p.is_file()), None)


def _event_log(source: Path) -> tuple[EventLog, Path]:
    source = source.resolve()
    if source.is_dir():
        path = source / "events.json"
        if not path.is_file():
            raise ValueError(f"{source} has no events.json")
        return EventLog.model_validate_json(path.read_text()), path
    raw = json.loads(source.read_text())
    if "source_checksum" in raw and "state_timeline" in raw:
        return EventLog.model_validate(raw), source
    replay = load_replay(source)
    return adapt_replay(replay), source


def _validate_optional_assets(plan: BlenderSequencePlan, project: Path):
    for binding in plan.characters.values():
        paths = [binding.model_path, *binding.action_overrides.values()]
        for value in filter(None, paths):
            path = Path(value)
            if not path.is_absolute():
                path = project / path
            if not path.is_file():
                raise ValueError(
                    f"Missing Blender asset for {binding.character_id}: {path}. "
                    "Remove the binding to use the procedural rig."
                )
        if binding.character_package:
            from whowouldwin.cinematic.assets.validation import (
                validate_character_package,
            )

            package_path = Path(binding.character_package)
            if not package_path.is_absolute():
                package_path = project / package_path
            report = validate_character_package(
                package_path, inspect_blender=False
            )
            if report.errors:
                detail = "; ".join(issue.message for issue in report.errors)
                raise ValueError(
                    f"Invalid CharacterPackage for {binding.character_id}: {detail}"
                )


def create_project(
    source: Path,
    output: Path,
    *,
    hybrid: bool = False,
    character_packages: dict[str, Path] | None = None,
) -> Path:
    source = source.resolve()
    output = output.resolve()
    log, source_path = _event_log(source)
    builder = build_hybrid_plan if hybrid else build_prototype_plan
    plan = builder(log, source_event_log="source/events.json")
    if character_packages:
        characters = dict(plan.characters)
        for slot, package in character_packages.items():
            if slot not in characters:
                raise ValueError(f"Unknown Blender character slot: {slot}")
            characters[slot] = characters[slot].model_copy(
                update={"character_package": str(package.expanduser().resolve())}
            )
        plan = plan.model_copy(update={"characters": characters})
    if (output / "blender_manifest.json").is_file():
        existing = BlenderSequencePlan.model_validate_json(
            (output / "blender_plan.json").read_text()
        )
        if existing != plan:
            raise ValueError(
                "Existing Blender project has different source/instructions; choose a fresh output"
            )
        return output
    if output.exists() and any(output.iterdir()):
        raise ValueError("Blender output directory must be empty")
    for folder in ("source", "assets", "renders/preview", "renders/final", "cache"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    write_json(output / "blender_plan.json", plan)
    if source_path.name == "events.json":
        shutil.copyfile(source_path, output / "source/events.json")
    else:
        write_json(output / "source/events.json", log)
        shutil.copyfile(source_path, output / "source/simulation.json")
    shutil.copyfile(_runtime_path(), output / "scene.py")
    shutil.copyfile(_asset_runtime_path(), output / "character_assets.py")
    _validate_optional_assets(plan, output)
    manifest = BlenderProjectManifest(
        plan_sha256=file_hash(output / "blender_plan.json"),
        runtime_sha256=file_hash(output / "scene.py"),
        asset_runtime_sha256=file_hash(output / "character_assets.py"),
        source_checksum=plan.source_checksum,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    write_json(output / "blender_manifest.json", manifest)
    return output


def load_project(project: Path):
    project = project.resolve()
    manifest = BlenderProjectManifest.model_validate_json(
        (project / "blender_manifest.json").read_text()
    )
    plan = BlenderSequencePlan.model_validate_json(
        (project / "blender_plan.json").read_text()
    )
    if (
        file_hash(project / "blender_plan.json") != manifest.plan_sha256
        or file_hash(project / "scene.py") != manifest.runtime_sha256
        or (
            manifest.asset_runtime_sha256 is not None
            and file_hash(project / "character_assets.py")
            != manifest.asset_runtime_sha256
        )
        or plan.source_checksum != manifest.source_checksum
    ):
        raise ValueError("Blender project plan/runtime provenance has changed")
    _validate_optional_assets(plan, project)
    return manifest, plan


def render_project(
    project: Path,
    *,
    mode: str = "preview",
    blender: Path | None = None,
    render: bool = True,
) -> Path:
    project = project.resolve()
    manifest, _ = load_project(project)
    executable = find_blender(blender)
    if not executable:
        raise ValueError(
            "Blender 4.2+ was not found. Install Blender, set WWS_BLENDER to its executable, "
            f"then rerun: wws render-blender {project} --{mode}"
        )
    video = project / f"renders/{mode}/fight.mp4"
    blend = project / "scene.blend"
    if (
        render
        and manifest.video_file == video.relative_to(project).as_posix()
        and video.is_file()
        and manifest.video_sha256 == file_hash(video)
    ):
        return video
    command = [
        str(executable),
        "--background",
        "--python",
        str(project / "scene.py"),
        "--",
        str(project / "blender_plan.json"),
        str(blend),
        mode,
        str(video),
        "render" if render else "scene-only",
    ]
    completed = subprocess.run(command, cwd=project, text=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"Blender exited with status {completed.returncode}")
    if not blend.is_file():
        raise RuntimeError("Blender did not create scene.blend")
    if render and not video.is_file():
        # Blender's FFmpeg writer appends a frame-range suffix on some 4.x builds.
        # Normalize that provider-specific filename once, so callers always receive
        # the stable project contract: renders/<mode>/fight.mp4.
        candidates = sorted(video.parent.glob(video.stem + "*.mp4"))
        if len(candidates) == 1:
            candidates[0].replace(video)
        else:
            raise RuntimeError("Blender did not create the requested video")
    manifest.blender_executable = str(executable)
    manifest.mode = mode
    if render:
        manifest.video_file = video.relative_to(project).as_posix()
        manifest.video_sha256 = file_hash(video)
    write_json(project / "blender_manifest.json", manifest)
    return video if render else blend


def command_preview(project: Path, mode="preview", blender: Path | None = None):
    executable = find_blender(blender)
    prefix = str(executable) if executable else "blender"
    project = project.resolve()
    video = project / f"renders/{mode}/fight.mp4"
    return [
        prefix,
        "--background",
        "--python",
        str(project / "scene.py"),
        "--",
        str(project / "blender_plan.json"),
        str(project / "scene.blend"),
        mode,
        str(video),
        "render",
    ]
