"""Resumable episode files, approval checkpoint, per-shot assets and audit trail."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Callable
from whowouldwin.simulation.replay import digest, load_replay
from .adapter import adapt_replay
from .director import CinematicDirector
from .editor import assemble_video, inspect_video
from .providers import (
    ImageRequest,
    MockImageProvider,
    MockVideoProvider,
    VideoOptions,
    provider_settings,
)
from .schemas import (
    ArenaVisualProfile,
    AssetRecord,
    DirectorSettings,
    EpisodeManifest,
    EventLog,
    SelectorSettings,
    ShotList,
    ShotStatus,
    VisualProfile,
)
from .selector import CinematicEventSelector
from .storyboard import (
    MockStoryboardRenderer,
    RenderContext,
    StoryboardFrame,
    contact_sheet,
)
from .visual_bibles import load_arena, load_visuals


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(project: Path, relative: str) -> Path:
    path = (project / relative).resolve()
    if not path.is_relative_to(project.resolve()):
        raise ValueError("Episode asset path escapes the project directory")
    return path


def record_asset(
    project: Path,
    manifest: EpisodeManifest,
    key: str,
    path: Path,
    version=None,
    provider="local",
):
    manifest.assets[key] = AssetRecord(
        path=path.relative_to(project).as_posix(),
        sha256=file_hash(path),
        shot_version=version,
        provider=provider,
    )


def cached(
    project: Path, manifest: EpisodeManifest, key: str, version=None
) -> Path | None:
    asset = manifest.assets.get(key)
    if not asset or asset.shot_version != version:
        return None
    path = safe_path(project, asset.path)
    return path if path.is_file() and file_hash(path) == asset.sha256 else None


def save_manifest(project: Path, manifest: EpisodeManifest, action: str):
    manifest.updated_at = now()
    manifest.history.append({"time": manifest.updated_at, "action": action})
    write_json(project / "manifest.json", manifest)


def direct_episode(
    source: Path,
    output: Path | None = None,
    *,
    settings: DirectorSettings | None = None,
    selector_settings: SelectorSettings | None = None,
    visual_directory: Path | None = None,
    arena_path: Path | None = None,
    provider_config: Path | None = None,
    representative="single seeded battle",
) -> Path:
    replay = load_replay(source)
    settings = settings or DirectorSettings()
    selection = selector_settings or SelectorSettings()
    providers = provider_settings(provider_config)
    log = adapt_replay(replay)
    visuals = load_visuals(log.fighter_profile_ids, visual_directory)
    arena = load_arena(arena_path)
    episode_id = (
        "_vs_".join(log.fighter_profile_ids.values())
        + f"_seed{log.simulation_seed}_{replay['checksum'][:8]}_{digest(settings.model_dump())[:6]}"
    )
    project = (output or Path("outputs") / episode_id).resolve()
    if (project / "manifest.json").exists():
        manifest, existing = load_episode(project)
        if (
            manifest.source_checksum != replay["checksum"]
            or manifest.director_settings != settings
            or manifest.selector_settings != selection
            or manifest.provider_settings != providers
            or json.loads((project / "visual_profiles.json").read_text())
            != {k: v.model_dump(mode="json") for k, v in visuals.items()}
            or json.loads((project / "arena_visual.json").read_text())
            != arena.model_dump(mode="json")
        ):
            raise ValueError(
                "Existing episode has different source/settings; choose a fresh --output directory"
            )
        return project
    if project.exists() and any(project.iterdir()):
        raise ValueError(
            "Output directory is not empty; choose a fresh episode directory"
        )
    # Validate the complete plan before creating a partially usable episode directory.
    moments = CinematicEventSelector(selection).select(log)
    shot_list = CinematicDirector().direct(log, moments, visuals, arena, settings)
    for folder in ("storyboard", "keyframes", "clips", "audio", "final", "references"):
        (project / folder).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, project / "simulation.json")
    write_json(project / "events.json", log)
    write_json(project / "moments.json", [m.model_dump(mode="json") for m in moments])
    write_json(project / "shot_list.json", shot_list)
    write_json(
        project / "continuity.json",
        {
            s.shot_id: s.continuity_state.model_dump(mode="json")
            for s in shot_list.shots
        },
    )
    write_json(
        project / "visual_profiles.json",
        {k: v.model_dump(mode="json") for k, v in visuals.items()},
    )
    write_json(project / "arena_visual.json", arena)
    manifest = EpisodeManifest(
        episode_id=episode_id,
        created_at=now(),
        updated_at=now(),
        simulation_seed=log.simulation_seed,
        source_checksum=log.source_checksum,
        outcome_digest=digest(log.outcome),
        fighter_versions=log.fighter_versions,
        visual_versions={k: v.version_id for k, v in visuals.items()},
        representative_battle=representative,
        director_settings=settings,
        selector_settings=selection,
        provider_settings=providers,
        shot_versions={s.shot_id: s.version for s in shot_list.shots},
        approval_status={s.shot_id: s.status for s in shot_list.shots},
    )
    for name in (
        "simulation",
        "events",
        "moments",
        "shot_list",
        "continuity",
        "visual_profiles",
        "arena_visual",
    ):
        record_asset(project, manifest, name, project / f"{name}.json")
    save_manifest(
        project,
        manifest,
        "Directed with deterministic local rules; no paid providers connected",
    )
    return project


def load_episode(project: Path) -> tuple[EpisodeManifest, ShotList]:
    manifest = EpisodeManifest.model_validate_json(
        (project / "manifest.json").read_text()
    )
    shots = ShotList.model_validate_json((project / "shot_list.json").read_text())
    replay = load_replay(project / "simulation.json")
    if (
        replay["checksum"] != manifest.source_checksum
        or shots.source_checksum != manifest.source_checksum
        or digest(replay["result"]) != manifest.outcome_digest
        or digest(shots.outcome) != manifest.outcome_digest
    ):
        raise ValueError("Episode source or outcome has changed")
    for key in ("events", "moments", "continuity", "visual_profiles", "arena_visual"):
        record = manifest.assets.get(key)
        if record and file_hash(safe_path(project, record.path)) != record.sha256:
            raise ValueError(
                f"Episode {key} was modified outside its versioned workflow"
            )
    asset = manifest.assets.get("shot_list")
    if asset and file_hash(project / "shot_list.json") != asset.sha256:
        raise ValueError(
            "Shot list changed outside the revision workflow; use revise-shot to preserve versions and approvals"
        )
    if any(
        manifest.shot_versions.get(s.shot_id) != s.version
        or manifest.approval_status.get(s.shot_id) != s.status
        for s in shots.shots
    ):
        raise ValueError("Shot versions/approval metadata disagree")
    return manifest, shots


def context_for(project, shots):
    visuals = {
        k: VisualProfile.model_validate(v)
        for k, v in json.loads((project / "visual_profiles.json").read_text()).items()
    }
    names = EventLog.model_validate_json(
        (project / "events.json").read_text()
    ).fighter_names
    return RenderContext(project, shots.settings, visuals, names)


def storyboard_episode(project: Path, progress: Callable | None = None) -> Path:
    project = project.resolve()
    manifest, shots = load_episode(project)
    context = context_for(project, shots)
    renderer = MockStoryboardRenderer()
    frames = []
    for i, shot in enumerate(shots.shots):
        path = cached(project, manifest, "storyboard:" + shot.shot_id, shot.version)
        frame = (
            StoryboardFrame(
                shot.shot_id,
                path,
                shots.settings.width,
                shots.settings.height,
                file_hash(path),
            )
            if path
            else renderer.render(shot, context)
        )
        frames.append(frame)
        record_asset(
            project,
            manifest,
            "storyboard:" + shot.shot_id,
            frame.path,
            shot.version,
            "mock-storyboard",
        )
        if progress:
            progress(i + 1, len(shots.shots))
    contact = contact_sheet(frames, project / "storyboard/contact-sheet.png")
    record_asset(project, manifest, "contact_sheet", contact)
    manifest.stage = "STORYBOARDED"
    save_manifest(project, manifest, "Mock storyboard ready for human approval")
    return contact


def set_shot_status(
    project: Path,
    shot_id: str,
    status: ShotStatus,
    *,
    motion_prompt: str | None = None,
    keyframe_prompt: str | None = None,
):
    project = project.resolve()
    manifest, shots = load_episode(project)
    selected = [s for s in shots.shots if s.shot_id == shot_id or shot_id == "all"]
    if not selected:
        raise ValueError(f"Unknown shot: {shot_id}")
    if status == ShotStatus.RENDERED:
        raise ValueError("RENDERED status is set only after a real clip is produced")
    for shot in selected:
        if status == ShotStatus.APPROVED and not cached(
            project, manifest, "storyboard:" + shot.shot_id, shot.version
        ):
            raise ValueError("Generate the current storyboard before approval")
        if status == ShotStatus.NEEDS_REGENERATION:
            shot.version += 1
            if motion_prompt is not None:
                shot.motion_prompt = motion_prompt
            if keyframe_prompt is not None:
                shot.keyframe_prompt = keyframe_prompt
        shot.status = status
        manifest.shot_versions[shot.shot_id] = shot.version
        manifest.approval_status[shot.shot_id] = status
        if status in {
            ShotStatus.DRAFT,
            ShotStatus.REJECTED,
            ShotStatus.NEEDS_REGENERATION,
        }:
            manifest.assets.pop("clip:" + shot.shot_id, None)
            manifest.render_approvals.pop(shot.shot_id, None)
    manifest.assets.pop("final_video", None)
    manifest.stage = "REVIEW"
    write_json(project / "shot_list.json", shots)
    record_asset(project, manifest, "shot_list", project / "shot_list.json")
    save_manifest(project, manifest, f"{shot_id}: {status.value}")


def render_episode(
    project: Path,
    *,
    allow_draft=False,
    shot_id: str | None = None,
    progress: Callable | None = None,
) -> list[Path]:
    project = project.resolve()
    manifest, shots = load_episode(project)
    if manifest.golden is not None:
        raise ValueError("Use golden-keyframes and golden-animate for the separate keyframe approval checkpoint")
    image_provider = MockImageProvider()
    video_provider = MockVideoProvider()
    selected = [s for s in shots.shots if shot_id is None or s.shot_id == shot_id]
    if not selected:
        raise ValueError(f"Unknown shot: {shot_id}")
    for shot in selected:
        if shot.status in {ShotStatus.REJECTED, ShotStatus.NEEDS_REGENERATION}:
            raise ValueError(
                f"{shot.shot_id} needs a new storyboard review and approval"
            )
        approved = shot.status == ShotStatus.APPROVED or (
            shot.status == ShotStatus.RENDERED
            and manifest.render_approvals.get(shot.shot_id) == "approved"
        )
        if not approved and not allow_draft:
            raise ValueError(
                f"{shot.shot_id} has no human approval. Approve its storyboard or explicitly use --allow-draft for mock preview"
            )
    outputs = []
    for i, shot in enumerate(selected):
        board = cached(project, manifest, "storyboard:" + shot.shot_id, shot.version)
        if not board:
            raise ValueError(f"Missing current storyboard: {shot.shot_id}")
        existing = cached(project, manifest, "clip:" + shot.shot_id, shot.version)
        if existing:
            manifest.render_approvals[shot.shot_id] = (
                "approved"
                if shot.status == ShotStatus.APPROVED
                else manifest.render_approvals.get(
                    shot.shot_id, "explicit mock draft override"
                )
            )
            shot.status = ShotStatus.RENDERED
            manifest.approval_status[shot.shot_id] = shot.status
            outputs.append(existing)
            continue
        keyframe = project / "keyframes" / f"{shot.shot_id}-v{shot.version}.png"
        image = image_provider.generate_keyframe(
            ImageRequest(
                shot.keyframe_prompt,
                tuple(shot.negative_constraints),
                shots.settings.aspect_ratio,
                (),
                shots.settings.width,
                shots.settings.height,
                keyframe,
                board,
            )
        )
        options = VideoOptions(
            shots.settings.width,
            shots.settings.height,
            shots.settings.fps,
            shot.frame_count,
            shot.camera_motion,
            shot.editorial,
        )
        clip = project / "clips" / f"{shot.shot_id}-v{shot.version}.mp4"
        video = video_provider.generate_video(
            image.path,
            shot.motion_prompt,
            shot.duration_seconds,
            shots.settings.aspect_ratio,
            (),
            options,
            clip,
        )
        proof = (
            "approved"
            if shot.status == ShotStatus.APPROVED
            else manifest.render_approvals.get(
                shot.shot_id, "explicit mock draft override"
            )
        )
        shot.status = ShotStatus.RENDERED
        manifest.approval_status[shot.shot_id] = shot.status
        manifest.render_approvals[shot.shot_id] = proof
        record_asset(
            project,
            manifest,
            "keyframe:" + shot.shot_id,
            image.path,
            shot.version,
            image.provider,
        )
        record_asset(
            project,
            manifest,
            "clip:" + shot.shot_id,
            video.path,
            shot.version,
            video.provider,
        )
        write_json(project / "shot_list.json", shots)
        record_asset(project, manifest, "shot_list", project / "shot_list.json")
        manifest.stage = "RENDERING"
        save_manifest(
            project,
            manifest,
            f"Rendered {shot.shot_id} v{shot.version}: {proof}; cost $0",
        )
        outputs.append(video.path)
        if progress:
            progress(i + 1, len(selected))
    write_json(project / "shot_list.json", shots)
    record_asset(project, manifest, "shot_list", project / "shot_list.json")
    manifest.stage = (
        "RENDERED"
        if all(s.status == ShotStatus.RENDERED for s in shots.shots)
        else "PARTIALLY_RENDERED"
    )
    save_manifest(project, manifest, manifest.stage)
    return outputs


def assemble_episode(project: Path) -> Path:
    project = project.resolve()
    manifest, shots = load_episode(project)
    if manifest.golden is not None:
        raise ValueError("Use golden-assemble to retain full provider clips and cost provenance")
    clips = []
    for shot in shots.shots:
        clip = cached(project, manifest, "clip:" + shot.shot_id, shot.version)
        if (
            not clip
            or shot.status != ShotStatus.RENDERED
            or shot.shot_id not in manifest.render_approvals
        ):
            raise ValueError(
                f"{shot.shot_id} has no current reviewed/overridden render"
            )
        clips.append(clip)
    output = assemble_video(project, shots, clips)
    metadata = inspect_video(output)
    if metadata["frames"] != sum(s.frame_count for s in shots.shots) or (
        metadata["width"],
        metadata["height"],
    ) != (shots.settings.width, shots.settings.height):
        raise RuntimeError("Assembled output does not match frame or resolution budget")
    write_json(
        project / "final/validation.json",
        dict(
            metadata,
            source_checksum=manifest.source_checksum,
            outcome_digest=manifest.outcome_digest,
            actual_cost_usd=0,
            provider="mock",
            simulation_outcome=shots.outcome,
        ),
    )
    for name, path in [
        ("final_video", output),
        ("captions", project / "final/captions.srt"),
        ("audio", project / "audio/mock-sfx.wav"),
        ("timing", project / "audio/timing.json"),
        ("video_validation", project / "final/validation.json"),
    ]:
        record_asset(project, manifest, name, path)
    manifest.stage = "ASSEMBLED"
    save_manifest(
        project,
        manifest,
        "Assembled and decoded complete mock video; zero paid API calls",
    )
    return output
