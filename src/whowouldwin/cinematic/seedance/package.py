"""Write a reproducible local upload package without calling any media provider."""

from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

from whowouldwin.combat.environment import Matchup
from whowouldwin.simulation.engine import Engine
from whowouldwin.simulation.replay import digest, load_replay, save_replay
from .planning import direct, load_bibles


REFERENCE_VIDEOS = (
    Path("/Users/jacksonjue/Documents/ChatGPT/WhoWouldWIn/ExampleVideo1.MP4"),
    Path("/Users/jacksonjue/Documents/ChatGPT/WhoWouldWIn/ExampleVideo2.MP4"),
)
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def write_json(path: Path, value) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _probe(path: Path) -> dict:
    if not path.is_file():
        return {"path": str(path.resolve()), "exists": False}
    try:
        data = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
            "-show_entries", "format=duration", "-of", "json", str(path),
        ], text=True))
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        data = {}
    return {"path": str(path.resolve()), "exists": True, "sha256": sha(path), "private_internal_reference": True,
            "stream": next(iter(data.get("streams", [])), {}), "duration_seconds": float(data.get("format", {}).get("duration", 0))}


def _reference_analysis(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    # Private review frames never enter an episode's distributable shot folders.
    stills = ((0, "example1", (2, 10, 18, 30)), (1, "example2", (2, 22, 38, 54)))
    for index, label, times in stills:
        if index >= len(REFERENCE_VIDEOS) or not REFERENCE_VIDEOS[index].is_file():
            continue
        frame_folder = folder / "private_reference_frames"
        frame_folder.mkdir(exist_ok=True)
        for second in times:
            target = frame_folder / f"{label}_at_{second}s.jpg"
            if target.is_file():
                continue
            try:
                subprocess.run([
                    "ffmpeg", "-loglevel", "error", "-ss", str(second), "-i",
                    str(REFERENCE_VIDEOS[index]), "-frames:v", "1", "-q:v", "4",
                    "-y", str(target),
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            except (FileNotFoundError, subprocess.CalledProcessError):
                target.unlink(missing_ok=True)
    notes = {
        "method": "Private 4-second sampling and central action-band review; timestamps are approximate; source videos are screen recordings, not clean masters.",
        "example_1": [
            {"seconds": 2, "private_still": "private_reference_frames/example1_at_2s.jpg", "observation": "Flat color duel; two separated silhouettes and simple white background."},
            {"seconds": 10, "private_still": "private_reference_frames/example1_at_10s.jpg", "observation": "Overhead crater impact isolates one body against a radial mark."},
            {"seconds": 18, "private_still": "private_reference_frames/example1_at_18s.jpg", "observation": "Brief blue environmental burst; physical fighter remains visible."},
            {"seconds": 30, "private_still": "private_reference_frames/example1_at_30s.jpg", "observation": "Group tableau uses a stable wide composition before the next action."},
        ],
        "example_2": [
            {"seconds": 2, "private_still": "private_reference_frames/example2_at_2s.jpg", "observation": "Dark painterly medium shot establishes large/small silhouette contrast."},
            {"seconds": 22, "private_still": "private_reference_frames/example2_at_22s.jpg", "observation": "Close attack frame keeps weapon and opponent on one readable axis."},
            {"seconds": 38, "private_still": "private_reference_frames/example2_at_38s.jpg", "observation": "Large blue circular effect frames the actor rather than covering it entirely."},
            {"seconds": 54, "private_still": "private_reference_frames/example2_at_54s.jpg", "observation": "Warm energy accent appears briefly against a cool arena."},
        ],
        "copyright": "Private analysis only. Still frames remain in private_reference_frames and are not copied into shot upload folders.",
    }
    write_json(folder / "reference-frame-notes.json", notes)
    (folder / "ExampleVideo1-analysis.md").write_text(
        "# ExampleVideo1 — internal visual direction\n\n"
        "47.26 s, 1206×2622 screen recording, 60 fps. The combat image occupies a wide central band inside a vertical social-app capture, with large black/UI areas. The fight artwork itself uses flat saturated colors, simple silhouettes, clear pose changes, white or sparse backgrounds, and radial impact marks. Action often reads in roughly 1–3-second visual beats; sampled scene changes also include shorter inserts. Camera direction shifts between medium two-character contact, overhead impact and occasional wide tableau. Transitions are mostly direct cuts or abrupt pose/action changes. The visible design complexity is low, which helps identity survive small-screen playback. Effects are short blue or white accents rather than constant full-screen glow. Repeated costume color, body scale and a stable action axis provide continuity.\n\n"
        "Production takeaway: keep two clean silhouettes, one action lane, brief impact punctuation and sparse environmental detail. Do not reproduce its exact characters, shots, captions or choreography.\n",
        encoding="utf-8",
    )
    (folder / "ExampleVideo2-analysis.md").write_text(
        "# ExampleVideo2 — internal visual direction\n\n"
        "63.31 s, 1206×2622 screen recording, 60 fps. The active fight is again a wide middle band in the phone capture. The art uses darker painterly texture, smoky gray depth, warm red/orange effects and occasional cold blue energy. Large opposing body masses remain readable against sparse scenery. A typical beat holds longer than the flat-color reference, with a preparatory pose, a directional attack arc, a contact/reaction image and a wider aftermath. Camera framing alternates medium combat shots and wider scale shots; close details appear at major injury or force moments. Cuts dominate, with a few extended camera-follow arcs. Effects are concentrated on attacks and impacts; they become dense only at the strongest beats. Repeatable armor/cape shapes, fixed light direction and arena haze support continuity.\n\n"
        "Production takeaway: borrow the restrained texture, value separation and impact rhythm, while keeping our designs simpler for repeatable generation. Do not reproduce exact characters, gore, dialogue or choreography.\n",
        encoding="utf-8",
    )
    (folder / "style-comparison.md").write_text(
        "# Reference comparison and WWS direction\n\n"
        "| Feature | ExampleVideo1 | ExampleVideo2 | WWS Seedance package |\n"
        "|---|---|---|---|\n"
        "| Source aspect | Tall social-app capture; wide action band | Tall social-app capture; wide action band | True full-frame 9:16 shot |\n"
        "| Pacing | Fast pose/cut rhythm, many 1–3 s beats | Longer pose and force arcs, occasional quick inserts | 6–12 shots over 8–15 s; 0.5–3 s each |\n"
        "| Motion/camera | Directional cuts, overhead impact | Controlled follow, medium and wide scale | One camera move and one dominant action per shot |\n"
        "| Design | Flat saturated comic shapes | Textured painterly forms | Simple stable silhouettes with restrained texture |\n"
        "| Impact | Radial mark, short blue accents | Localized glow, dust and body reaction | Contact must remain visible; one brief effect |\n"
        "| Continuity | Repeated color, pose and action axis | Costume mass, lighting and arena haze | Explicit start/end state, screen lane and landmarks |\n\n"
        "The screen recordings include social-app UI, captions and black margins. Those are recording artifacts, not a desired video canvas. Private stills remain outside distributable shot folders.\n",
        encoding="utf-8",
    )
    (folder / "simplified-style-guide.md").write_text(
        "# Simplified graphic animation direction\n\n"
        "The two supplied files are 1206×2622 / 60 fps social-app screen recordings. Their embedded action regions are wider than the phone capture; the UI and black margins are not desired output. Extracted stills are private visual study only.\n\n"
        "| Attribute | ExampleVideo1 | ExampleVideo2 | Chosen WWS direction |\n"
        "|---|---|---|---|\n"
        "| Figures | Very simple heads, large flat limb masses, strong costume blocks | More rendered anatomy and texture | Use the simpler first-video construction; retain only key identity anchors |\n"
        "| Silhouette | Fighters separate cleanly against white space | Large/small body contrast against dark haze | Short angular Naruto versus broad caped Omni-Man, with visible limb gaps |\n"
        "| Color and edge | Saturated flat fills, obvious contours | Warm/cool painterly accents | Orange/black versus red/white, single dark outline, at most one flat shadow |\n"
        "| Face | Minimal expressions visible at action scale | More face detail in medium shots | Eyes, brows, mouth, mustache or cheek marks only |\n"
        "| Framing | Medium fight views and short overhead inserts | Medium-to-wide impact scale | Medium 9:16 two-person shots; no game-camera distance |\n"
        "| Rhythm | Often roughly 1–3-second pose/cut beats | Longer force arcs with brief inserts | Eight 1–1.6-second shots over 10 seconds, hard cuts on action |\n"
        "| Motion | Abrupt acceleration and clear pose changes | More continuous force arcs | Short anticipation, one action path, readable support and recovery |\n"
        "| Impact and effects | Radial marks and brief blue accents | Local red/blue glow, smoke at major beats | One small contact mark; energy remains local and never hides bodies |\n"
        "| Environment | Intentionally sparse | Painterly arena depth | One road stripe, two simple facades, stable blue-hour light |\n\n"
        "Omit fabric microdetail, realistic muscles, facial acting, complex architecture and constant particles. Exaggerate pose, spacing and timing only while joints and support feet remain legible. Never copy a source video's exact pose, shot sequence, dialogue, character or choreography.\n",
        encoding="utf-8",
    )


def _blocking_svg(shot, start: bool) -> str:
    state = shot.continuity_start if start else shot.continuity_end
    positions = state.screen_positions
    colors = {key: ("#f59a38" if "naruto" in key else "#e6e6e6" if "omni" in key else "#a0cfe5") for key in positions}
    figures = []
    for key in sorted(positions):
        x = 290 if positions[key] == "left" else 790
        color = colors[key]
        figures.append(f'<circle cx="{x}" cy="675" r="75" fill="{color}"/><path d="M{x} 750 L{x} 1120 M{x} 850 L{x-110} 960 M{x} 850 L{x+110} 960 M{x} 1120 L{x-90} 1370 M{x} 1120 L{x+90} 1370" stroke="{color}" stroke-width="40" fill="none" stroke-linecap="round"/><text x="{x}" y="1480" text-anchor="middle" fill="white" font-size="42">{key}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">'
            '<rect width="1080" height="1920" fill="#152032"/><path d="M60 1450 L1020 1450" stroke="#657083" stroke-width="12"/>'
            + ''.join(figures) + f'<text x="50" y="105" fill="white" font-size="45">{shot.shot_id}: {"START" if start else "END"} BLOCKING ONLY</text>'
            '<text x="50" y="1800" fill="#d6d6d6" font-size="30">SCHEMATIC — NOT CHARACTER ART OR SEEDANCE INPUT</text></svg>')


def _valid_image(path: Path) -> bool:
    """Reject empty/renamed junk; decode fully when Pillow is installed."""
    if not path.is_file() or path.stat().st_size < 32:
        return False
    with path.open("rb") as stream:
        header = stream.read(16)
    suffix = path.suffix.lower()
    matches = (
        suffix == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n")
        or suffix in {".jpg", ".jpeg"} and header.startswith(b"\xff\xd8")
        or suffix == ".webp" and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    )
    if not matches:
        return False
    try:
        from PIL import Image
    except ImportError:
        return True
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def _shot_files(project: Path, shot) -> dict:
    folder = project / "shots" / shot.shot_id
    for name in ("character_references", "ability_references", "style_references", "motion_reference", "first_frame", "last_frame"):
        (folder / name).mkdir(parents=True, exist_ok=True)
    write_json(folder / "shot.json", shot)
    (folder / "seedance_prompt.txt").write_text(shot.seedance_prompt + "\n", encoding="utf-8")
    (folder / "seedance_negative_prompt.txt").write_text(shot.negative_prompt + "\n", encoding="utf-8")
    write_json(folder / "continuity_start.json", shot.continuity_start)
    write_json(folder / "continuity_end.json", shot.continuity_end)
    (folder / "first_frame/blocking.svg").write_text(_blocking_svg(shot, True), encoding="utf-8")
    (folder / "last_frame/blocking.svg").write_text(_blocking_svg(shot, False), encoding="utf-8")
    required = [*shot.required_reference_images, "first_frame/approved.png", "last_frame/approved.png"]
    upload = {
        "shot_id": shot.shot_id, "duration_seconds": shot.duration_seconds,
        "relative_shot_directory": f"shots/{shot.shot_id}",
        "prompt": "seedance_prompt.txt", "negative_prompt": "seedance_negative_prompt.txt",
        "required_upload_images": required,
        "optional_motion_reference_video": "motion_reference/guide.mp4",
        "blocking_diagrams_are_not_upload_assets": True,
        "manual_actions": ["Supply approved first/last frame images", "Supply approved character and style image references",
                           "Check contact, costume, facing and outcome after generation"],
        "provider_calls": 0,
    }
    write_json(folder / "upload_manifest.json", upload)
    (folder / "validation_checklist.md").write_text(
        f"# {shot.shot_id} review\n\n" + "\n".join(f"- [ ] {item}" for item in shot.human_review_checklist)
        + "\n- [ ] Approved first/last frames and all required references exist\n- [ ] No new combat event or outcome appears\n",
        encoding="utf-8",
    )
    return upload


def stage_shared_references(project: Path) -> dict:
    """Copy validated shared references into each shot upload folder."""
    from .schemas import EpisodePlan
    from .first_episode import EPISODE_ID, apply_first_episode_direction

    project = project.resolve()
    plan = EpisodePlan.model_validate_json((project / "episode_plan.json").read_text(encoding="utf-8"))
    first_episode = plan.episode_id == EPISODE_ID
    if first_episode:
        apply_first_episode_direction(project)
        plan = EpisodePlan.model_validate_json((project / "episode_plan.json").read_text(encoding="utf-8"))
    aliases = {
        "style_references/approved_style.png": "simplified-style-reference.png",
        "ability_references/naruto_chakra_form.png": "naruto-chakra-form-simple.png",
        "ability_references/naruto_charged_vortex.png": "charged-vortex-projectile.png",
        "ability_references/naruto_energy_orb.png": "energy-orb-projectile.png",
        "ability_references/omniman_grapple.png": "omniman-grapple-simple.png",
        "ability_references/omniman_heavy_strike.png": "omniman-impact-simple.png",
    }
    staged = []
    for shot in plan.shots:
        for relative in shot.required_reference_images:
            source = (project / "shared_references" / relative).resolve()
            if first_episode and not source.is_file():
                basename = Path(relative).name.replace("_", "-")
                source = (project / "shared_references" / aliases.get(relative, basename)).resolve()
            target = (project / "shots" / shot.shot_id / relative).resolve()
            if not source.is_relative_to(project / "shared_references") or not target.is_relative_to(project):
                raise ValueError(f"Unsafe shared reference path: {relative}")
            if source.is_file() and _valid_image(source) and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                staged.append(str(target.relative_to(project)))
        if first_episode:
            folder = project / "shots" / shot.shot_id
            manifest_path = folder / "upload_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["required_upload_images"] = [*shot.required_reference_images, "keyframe.png"]
            manifest["preferred_start_image"] = "keyframe.png"
            manifest["optional_end_image"] = "last_frame/approved.png"
            manifest["manual_actions"] = [
                "Review the generated keyframe and character design before upload",
                "Confirm the recorded hit, miss, or ability remains correct",
                "Review the ending pose against the next shot before adding an optional end frame",
            ]
            write_json(manifest_path, manifest)
    return {"staged_files": staged, "staged_count": len(staged), "validation": validate_package(project)}


def validate_package(project: Path, *, write: bool = True) -> dict:
    project = project.resolve()
    plan_path = project / "episode_plan.json"
    if not plan_path.is_file():
        raise ValueError(f"Missing episode plan: {plan_path}")
    from .schemas import EpisodePlan
    plan = EpisodePlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    replay = load_replay(project / "simulation.json")
    if replay["checksum"] != plan.source_checksum:
        raise ValueError("Simulation checksum does not match episode plan")
    event_sha = digest([event for frame in replay["frames"] for event in frame["events"]])
    if event_sha != plan.canonical_event_sha256:
        raise ValueError("Canonical event log hash does not match episode plan")
    if plan.outcome != replay["result"]:
        raise ValueError("Episode outcome differs from the saved simulator result")
    beats = json.loads((project / "fight_beats.json").read_text(encoding="utf-8"))
    source_count = sum(len(frame["events"]) for frame in replay["frames"])
    if len(beats) != source_count:
        raise ValueError(f"FightBeat count {len(beats)} differs from {source_count} source events")
    issues = []
    known = {beat["beat_id"] for beat in beats}
    batch = []
    for index, shot in enumerate(plan.shots):
        if shot.sequence_index != index + 1 or shot.shot_id != f"shot_{index + 1:03d}":
            issues.append(f"{shot.shot_id}: shot order is not sequential")
        if shot.continuity_start.camera_side != shot.continuity_end.camera_side:
            issues.append(f"{shot.shot_id}: camera crossed the action axis")
        if shot.continuity_start.lighting_direction != shot.continuity_end.lighting_direction:
            issues.append(f"{shot.shot_id}: unexplained lighting reversal")
        if set(shot.continuity_start.screen_positions) != set(shot.continuity_end.screen_positions):
            issues.append(f"{shot.shot_id}: fighter continuity keys changed")
        if shot.continuity_end.simulation_time < shot.continuity_start.simulation_time:
            issues.append(f"{shot.shot_id}: source simulation time moved backward")
        if index and shot.source_simulation_time < plan.shots[index - 1].source_simulation_time:
            issues.append(f"{shot.shot_id}: selected source events are out of order")
        if shot.continuity_end.screen_positions != shot.continuity_start.screen_positions:
            source_events = [beat for beat in beats if beat["beat_id"] in shot.source_beat_ids]
            if not any(beat["event_type"] in {"ActionChosen", "Knockback", "FighterMoved"} for beat in source_events):
                issues.append(f"{shot.shot_id}: screen lanes flip without a movement beat; manually review")
    for shot in plan.shots:
        folder = (project / "shots" / shot.shot_id).resolve()
        shot_file = folder / "shot.json"
        if not shot_file.is_file() or json.loads(shot_file.read_text(encoding="utf-8")) != shot.model_dump(mode="json"):
            issues.append(f"{shot.shot_id}: shot.json differs from episode plan")
        for beat_id in shot.source_beat_ids:
            if beat_id not in known:
                issues.append(f"{shot.shot_id}: unknown source beat {beat_id}")
        if not shot.seedance_prompt.strip() or not shot.negative_prompt.strip():
            issues.append(f"{shot.shot_id}: empty prompt or negative prompt")
        for name, expected in (("seedance_prompt.txt", shot.seedance_prompt),
                               ("seedance_negative_prompt.txt", shot.negative_prompt)):
            file = folder / name
            if not file.is_file() or file.read_text(encoding="utf-8").strip() != expected.strip():
                issues.append(f"{shot.shot_id}: {name} differs from the episode plan")
        for name, expected in (("continuity_start.json", shot.continuity_start),
                               ("continuity_end.json", shot.continuity_end)):
            file = folder / name
            if not file.is_file() or json.loads(file.read_text(encoding="utf-8")) != expected.model_dump(mode="json"):
                issues.append(f"{shot.shot_id}: {name} differs from the episode plan")
        manifest = json.loads((folder / "upload_manifest.json").read_text(encoding="utf-8"))
        required = manifest["required_upload_images"]
        if not set(shot.required_reference_images).issubset(required):
            issues.append(f"{shot.shot_id}: manifest omits required character, style, or ability references")
        if "keyframe.png" not in required and not {"first_frame/approved.png", "last_frame/approved.png"}.issubset(required):
            issues.append(f"{shot.shot_id}: manifest lacks a valid start-frame policy")
        for relative in required:
            if relative.startswith(("character_references/", "ability_references/")) and not any(
                Path(relative).name.startswith(f"{fighter}_") for fighter in plan.fighter_ids
            ):
                issues.append(f"{shot.shot_id}: unrelated character reference {relative}")
        missing = []
        for relative in required:
            file = (folder / relative).resolve()
            if not file.is_relative_to(folder) or file.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
                issues.append(f"{shot.shot_id}: invalid reference path {relative}")
                continue
            if not _valid_image(file):
                missing.append(relative)
            if relative == "keyframe.png" and _valid_image(file):
                try:
                    from PIL import Image
                    with Image.open(file) as image:
                        width, height = image.size
                    if height < 512 or abs(width / height - 9 / 16) > 0.015:
                        issues.append(f"{shot.shot_id}: keyframe is not a usable vertical 9:16 image")
                except ImportError:
                    issues.append(f"{shot.shot_id}: install Pillow to validate keyframe dimensions")
        if missing:
            issues.extend(f"{shot.shot_id}: missing {name}" for name in missing)
        batch.append({"shot_id": shot.shot_id, "relative_shot_directory": f"shots/{shot.shot_id}",
                      "duration_seconds": shot.duration_seconds,
                      "required_upload_images": manifest["required_upload_images"],
                      "missing_upload_images": missing,
                      "ready_for_manual_upload": not missing})
    status = {"ready_for_manual_upload": not issues, "missing_count": len(issues),
              "issues": issues, "shots": batch, "canonical_event_sha256": event_sha,
              "source_replay_checksum": replay["checksum"],
              "package_root_absolute": str(project), "provider_calls": 0}
    if write:
        write_json(project / "seedance_batch_manifest.json", {
            "schema_version": 1, "episode_id": plan.episode_id, "package_root_absolute": str(project),
            "paths_inside_package_are_relative": True, "shots": batch,
            "ready_for_manual_upload": status["ready_for_manual_upload"], "provider_calls": 0,
        })
        write_json(project / "validation-summary.json", status)
        (project / "validation-summary.md").write_text(
            f"# Seedance package validation\n\nStatus: **{'READY' if not issues else 'BLOCKED — required manual images missing'}**.\n\n"
            f"Source checksum: `{replay['checksum']}`. Event log SHA-256: `{event_sha}`. "
            f"{len(plan.shots)} shots; {len(beats)} beats for {source_count} canonical events. "
            "No paid provider was called.\n\n" + ("\n".join(f"- {item}" for item in issues) if issues else "All required files found.") + "\n",
            encoding="utf-8",
        )
    return status


def prepare(source: Path | Matchup, *, output: Path | None = None, duration: float = 10,
            shots: int = 8, fps: int = 30) -> tuple[Path, dict]:
    """Generate once from a replay or seed; same inputs yield byte-identical package files."""
    if isinstance(source, Matchup):
        engine = Engine(source, record=True)
        engine.run()
        with tempfile.TemporaryDirectory(prefix="wws-seedance-") as temp:
            replay_path = save_replay(engine, Path(temp) / "simulation.json")
            return _prepare_replay(replay_path, output=output, duration=duration, shots=shots, fps=fps)
    return _prepare_replay(Path(source), output=output, duration=duration, shots=shots, fps=fps)


def _prepare_replay(source: Path, *, output: Path | None, duration: float, shots: int, fps: int) -> tuple[Path, dict]:
    replay = load_replay(source)
    plan, beats, specs = direct(replay, duration=duration, shots=shots, fps=fps)
    project = (output or Path("outputs/seedance_ready") / plan.episode_id).resolve()
    if project.exists() and any(project.iterdir()):
        existing = project / "episode_plan.json"
        if existing.is_file():
            from .schemas import EpisodePlan
            saved = EpisodePlan.model_validate_json(existing.read_text(encoding="utf-8"))
            if (saved.source_checksum == plan.source_checksum
                    and saved.canonical_event_sha256 == plan.canonical_event_sha256
                    and len(saved.shots) == len(plan.shots)
                    and saved.duration_seconds == plan.duration_seconds and saved.fps == plan.fps):
                from .first_episode import EPISODE_ID, install_curated_assets
                if saved.episode_id == EPISODE_ID:
                    install_curated_assets(project)
                    return project, stage_shared_references(project)["validation"]
                return project, validate_package(project)
        raise ValueError(f"Output directory contains a different or incomplete episode: {project}")
    project.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, project / "simulation.json")
    write_json(project / "fight_beats.json", [beat.model_dump(mode="json") for beat in beats])
    editorial_cursor = 0.0
    timeline = []
    for shot in plan.shots:
        editorial_end = round(editorial_cursor + shot.duration_seconds, 6)
        timeline.append({"shot_id": shot.shot_id, "source_simulation_time": shot.source_simulation_time,
                         "source_beat_ids": shot.source_beat_ids,
                         "editorial_start_seconds": editorial_cursor,
                         "editorial_end_seconds": editorial_end,
                         "editorial_duration_seconds": shot.duration_seconds})
        editorial_cursor = editorial_end
    write_json(project / "fight_timeline.json", timeline)
    write_json(project / "continuity_states.json", [
        {"shot_id": shot.shot_id, "start": shot.continuity_start.model_dump(mode="json"),
         "end": shot.continuity_end.model_dump(mode="json")}
        for shot in plan.shots
    ])
    write_json(project / "episode_plan.json", plan)
    write_json(project / "character_visual_bibles.json", {key: value.model_dump(mode="json") for key, value in load_bibles(plan.fighter_ids).items()})
    write_json(project / "ability_visual_specs.json", {key: value.model_dump(mode="json") for key, value in specs.items()})
    inventory = [_probe(path) for path in REFERENCE_VIDEOS]
    write_json(project / "example-video-inventory.json", inventory)
    _reference_analysis(project.parent / "reference_analysis")
    shared = project / "shared_references"
    for name in ("character_references", "ability_references", "style_references"):
        (shared / name).mkdir(parents=True, exist_ok=True)
    for shot in plan.shots:
        _shot_files(project, shot)
    from .first_episode import apply_first_episode_direction
    apply_first_episode_direction(project)
    write_json(project / "shared_reference_requirements.json", sorted({
        name for shot in plan.shots for name in shot.required_reference_images
    }))
    (project / "storyboard.md").write_text(
        "# Shot storyboard — planning text, no approved character artwork\n\n"
        + "\n\n".join(f"## {shot.shot_id} · {shot.duration_seconds:.2f}s\n\n"
                       f"{shot.purpose}. {shot.action_description}\n\n"
                       f"Start: {shot.starting_pose}. End: {shot.ending_pose}. "
                       f"Camera: {shot.camera_framing}; {shot.camera_movement}."
                       for shot in plan.shots) + "\n",
        encoding="utf-8",
    )
    (project / "production_notes.md").write_text(
        "# Production notes\n\nThe saved deterministic battle is canonical. This package interprets selected events for short visual shots; it does not alter combat facts. Editorial time differs from simulation time. The character and ability bibles are development fixtures, not researched matchup evidence or licensed art. Source event IDs remain in every shot. Use one dominant action per 0.5–3-second shot, full-frame vertical 9:16, restrained effects and a fixed camera axis. The first and last blocking SVGs are diagrams only. No external provider was called.\n\n"
        "Complete the missing approved character, style, ability and first/last-frame images before manual Seedance upload. Re-run `wws validate-seedance <project>` after adding them. Keep source videos private and out of shot folders.\n",
        encoding="utf-8",
    )
    (project / "seedance_upload_guide.md").write_text(
        "# Manual Seedance upload guide\n\n"
        "1. Review `simulation.json`, `fight_timeline.json`, the visual bibles and the shot plan.\n"
        "2. Supply approved common images under `shared_references/` using `shared_reference_requirements.json`, then run `wws seedance-stage-refs <project>` to copy them into shot upload folders. Use rights-cleared character boards in consistent front, side and three-quarter views. Supply real shot-specific `first_frame/approved.png` and `last_frame/approved.png` in each shot. Blocking SVGs are planning diagrams, not character art.\n"
        "3. Run `wws validate-seedance <project>`. Only upload shots with `ready_for_manual_upload: true`.\n"
        "4. For each shot, use its positive and negative prompt, duration and uploaded references. Render one shot at a time. Keep the same camera side and costume anchors.\n"
        "5. Compare each result with its checklist and continuity start/end. Reject any extra hit, identity drift or altered outcome. Assemble the approved clips in `episode_plan.json` order using hard cuts.\n\n"
        "This command does not call Seedance or another paid API. Provider settings and credentials are not stored.\n",
        encoding="utf-8",
    )
    from .first_episode import EPISODE_ID, install_curated_assets
    if plan.episode_id == EPISODE_ID:
        install_curated_assets(project)
        return project, stage_shared_references(project)["validation"]
    return project, validate_package(project)
