"""Nine short Seedance 2.5 uploads with minimal 2D art and multi-angle guides.

This is a presentation derivative of the validated seed-289 replay. It neither
changes combat data nor calls a paid generation provider.
"""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image

from whowouldwin.simulation.replay import load_replay

from .longform_seed289 import EVENT_SHA, SOURCE_CHECKSUM, build_plan
from .package import write_json
from .seedance25 import ROOT, SOURCE, _ffprobe, _state
from .seedance25_v2 import MOTION_NAMES, SEQUENCES
from .seedance25_v3_art import CAMERAS, W, H, frame_at, motion_video


DEFAULT_OUTPUT = ROOT / "outputs/seedance_ready/naruto_vs_omniman_seedance25_v3"
ART_SOURCE = ROOT / "assets/seedance/seed289_60s/style_matched_v3"
REFERENCE_NAMES = (
    "naruto_style_matched_front.png", "naruto_style_matched_action.png",
    "naruto_style_matched_reaction.png", "omniman_style_matched_front.png",
    "omniman_style_matched_action.png", "omniman_style_matched_reaction.png",
    "style_matched_faceoff.png", "style_matched_impact.png",
    "style_matched_recovery.png", "style_matched_environment.png",
)
EXACT_STYLE_SENTENCE = (
    "Match the supplied private reference video’s simplified cinematic 2D visual language, "
    "expressive anatomy, dynamic pose design, controlled painterly shading, impact timing, "
    "and camera rhythm. Do not copy its characters or exact choreography."
)

SEEDANCE_MOTION_SIZE = (720, 1280)
SEEDANCE_MIN_PIXELS = 409_600


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _motion_probe(path: Path) -> dict:
    probe = _ffprobe(path)
    probe["pixel_count"] = probe["width"] * probe["height"]
    return probe


def _matching_timing(source: dict, upload: dict) -> bool:
    return (Fraction(source["fps"]) == Fraction(upload["fps"])
            and source["frame_count"] == upload["frame_count"]
            and abs(source["duration_seconds"] - upload["duration_seconds"]) <= .005)


def upgrade_motion_references(output: Path) -> dict:
    """Replace 360p guides with 720p upload masters after complete validation.

    The originals remain untouched while FFmpeg scales and verifies all nine
    outputs. Once all are valid, the old masters are removed. Sequence upload
    paths become hard links to their masters, avoiding duplicate video storage.
    Only pixels are scaled; no action or timing is regenerated.
    """
    output = output.resolve()
    source_dir = output / "motion_refs"
    upload_dir = output / "motion_refs_seedance"
    upload_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for sequence, name in zip(SEQUENCES, MOTION_NAMES, strict=True):
        source = source_dir / name
        upload = upload_dir / name
        folder = output / "sequences" / f"sequence_{sequence.index:02d}"
        manifest_path = folder / "reference_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Missing manifest for sequence {sequence.index:02d}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if source.is_file():
            source_hash = _sha256(source)
            source_probe = _motion_probe(source)
            if (source_probe["width"], source_probe["height"]) != (W, H):
                raise ValueError(f"Original guide must be {W}x{H}: {source}")
        elif upload.is_file() and manifest.get("motion_reference_source_sha256") and manifest.get("motion_reference_original_probe"):
            source_hash = manifest["motion_reference_source_sha256"]
            source_probe = manifest["motion_reference_original_probe"]
        else:
            raise FileNotFoundError(f"Missing both original and verified upscale for sequence {sequence.index:02d}")
        if upload.is_file():
            if manifest.get("motion_reference_source_sha256") != source_hash:
                raise ValueError(f"Existing upload copy has unverified source revision: {upload}")
        else:
            temporary = upload_dir / f".{name}.building.mp4"
            try:
                subprocess.run([
                    "ffmpeg", "-loglevel", "error", "-nostdin", "-y", "-i", str(source),
                    "-vf", "scale=720:1280:flags=lanczos,setsar=1", "-fps_mode", "passthrough",
                    "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary),
                ], check=True)
                candidate = _motion_probe(temporary)
                if ((candidate["width"], candidate["height"]) != SEEDANCE_MOTION_SIZE
                        or candidate["pixel_count"] < SEEDANCE_MIN_PIXELS
                        or not _matching_timing(source_probe, candidate)):
                    raise ValueError(f"FFmpeg upscale changed timing or has incorrect dimensions: {temporary}")
                temporary.replace(upload)
            finally:
                if temporary.is_file():
                    temporary.unlink()
        upload_probe = _motion_probe(upload)
        if ((upload_probe["width"], upload_probe["height"]) != SEEDANCE_MOTION_SIZE
                or upload_probe["pixel_count"] < SEEDANCE_MIN_PIXELS
                or not _matching_timing(source_probe, upload_probe)):
            raise ValueError(f"Noncompliant upload motion reference: {upload}")
        if source.is_file() and _sha256(source) != source_hash:
            raise ValueError(f"Original motion reference changed during upscale: {source}")
        upload_hash = _sha256(upload)
        local_copy = folder / "motion_reference.mp4"
        if not local_copy.is_file() or not local_copy.samefile(upload):
            temporary_link = folder / ".motion_reference.upscaled.mp4"
            if temporary_link.exists():
                temporary_link.unlink()
            temporary_link.hardlink_to(upload)
            temporary_link.replace(local_copy)
        manifest["motion_reference_master_directory"] = "motion_refs_seedance"
        manifest.pop("motion_reference_source_master", None)
        manifest["motion_reference_source_sha256"] = source_hash
        manifest["motion_reference_original_probe"] = source_probe
        manifest["motion_reference_sha256"] = upload_hash
        manifest["motion_reference_resolution"] = {
            "width": upload_probe["width"], "height": upload_probe["height"],
            "pixel_count": upload_probe["pixel_count"], "minimum_pixels": SEEDANCE_MIN_PIXELS,
            "scaling_filter": "Lanczos", "original_width": W, "original_height": H,
            "spatial_only": True,
        }
        write_json(manifest_path, manifest)
        rows.append({
            "filename": name, "sequence": f"sequence_{sequence.index:02d}",
            "width": upload_probe["width"], "height": upload_probe["height"],
            "pixel_count": upload_probe["pixel_count"], "duration_seconds": upload_probe["duration_seconds"],
            "frame_rate": upload_probe["fps"], "frame_count": upload_probe["frame_count"],
            "original_sha256": source_hash, "upload_sha256": upload_hash,
            "original_path": "removed after validated upscale", "upload_path": str(upload.relative_to(output)),
            "sequence_upload_path": str(local_copy.relative_to(output)),
        })
    # The user's storage preference supersedes retaining the 360p masters.
    # This runs only after every output, sequence link and timing check passed.
    for name in MOTION_NAMES:
        source = source_dir / name
        if source.is_file():
            source.unlink()
    if source_dir.is_dir() and not any(source_dir.iterdir()):
        source_dir.rmdir()
    report = {
        "threshold_pixels": SEEDANCE_MIN_PIXELS, "target_width": 720, "target_height": 1280,
        "scaling_filter": "Lanczos", "all_compliant": len(rows) == len(SEQUENCES)
        and all(row["pixel_count"] >= SEEDANCE_MIN_PIXELS for row in rows),
        "originals_removed": all(not (source_dir / name).exists() for name in MOTION_NAMES),
        "sequence_files_hardlinked_to_masters": all(
            (output / "sequences" / f"sequence_{sequence.index:02d}" / "motion_reference.mp4").samefile(upload_dir / name)
            for sequence, name in zip(SEQUENCES, MOTION_NAMES, strict=True)),
        "provider_calls": 0, "references": rows,
    }
    write_json(output / "review/motion_resolution_compliance.json", report)
    lines = ["# Dreamina motion-reference resolution", "",
             "Upload the 720×1280 videos in each sequence folder. Their masters are in `motion_refs_seedance/`; the sequence files are hard links, so they occupy no additional video storage. The nine 360×640 originals were removed only after all upscales passed. FFmpeg applied Lanczos scaling only; frame count, frame rate and duration are unchanged. Original hashes and metadata remain in this report.", "",
             "| Sequence | Filename | Resolution | Pixels | Duration | FPS |", "|---|---|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['sequence']} | `{row['filename']}` | {row['width']}×{row['height']} | "
                     f"{row['pixel_count']:,} | {row['duration_seconds']:.3f}s | {row['frame_rate']} |")
    lines += ["", "Pixel threshold: 409,600. Sequence 01's `motion_reference.mp4` is the compliant upload copy. The separate 360×640 episode animatic is local review only and is not an upload reference.", ""]
    (output / "review/motion_resolution_compliance.md").write_text("\n".join(lines), encoding="utf-8")
    playlist = output / "review/motion_concat.txt"
    playlist.write_text("".join(f"file '../motion_refs_seedance/{name}'\n" for name in MOTION_NAMES), encoding="utf-8")
    provenance_path = output / "provenance.json"
    if provenance_path.is_file():
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["motion_reference_delivery"] = "720x1280 Lanczos upload masters; 360x640 individual masters removed after validation"
        write_json(provenance_path, provenance)
    _documents(output)
    return report
def _selected_references(index: int) -> tuple[list[str], str]:
    if index == 1:
        variants = ("front", "action")
        style = "style_matched_faceoff.png"
    elif index in (2, 3, 5, 6, 8, 9):
        variants = ("action", "reaction")
        style = "style_matched_impact.png" if index != 9 else "style_matched_recovery.png"
    else:
        variants = ("front", "reaction")
        style = "style_matched_recovery.png" if index == 7 else "style_matched_faceoff.png"
    identities = [f"{actor}_style_matched_{variant}.png"
                  for actor in ("naruto", "omniman") for variant in variants]
    return identities, style


def _prompt(sequence) -> str:
    start, end = _state(sequence.keys[0]), _state(sequence.keys[-1])
    cues = CAMERAS[sequence.index]
    camera_lines = "; ".join(
        f"{cue.time:.2f}s cut to {cue.angle.replace('_', '-')} {cue.framing} on {cue.focus}"
        for cue in cues
    )
    rows = [
        f"Dreamina Seedance 2.5, original vertical 9:16 fight, {sequence.duration} seconds. {sequence.name}.",
        EXACT_STYLE_SENTENCE,
        "Visual simplification: flat hand-painted figures, two or three broad tone regions per costume, "
        "minimal facial marks, expressive body posture, sparse near-white street, nearly no texture. "
        "Keep Naruto's blond spikes/headband/orange-black silhouette and Omni-Man's broad white-red suit, mustache and cape. "
        "Do not add intricate armor, complex city detail, painterly skin texture or photorealistic faces.",
        "Reference roles: the four character stills identify the fighters; the scene still sets the simple color language; "
        "the sparse environment still defines spatial continuity; start and end images define handoff; "
        "motion_reference.mp4 is a multi-angle action and cut guide, not final animation. The supplied private video "
        "is optional camera/style/pacing inspiration only, never a character or exact-shot source.",
        f"Start state: Naruto x={start['naruto']['x']:.0f} screen left; Omni-Man x={start['omniman']['x']:.0f} screen right. "
        f"End state: Naruto x={end['naruto']['x']:.0f} screen left; Omni-Man x={end['omniman']['x']:.0f} screen right. "
        "Keep their action axis and clear negative space across cuts.",
        *sequence.timeline,
        "Movement: lead foot loads, rear heel releases, pelvis drives the torso, shoulder follows, forearm and hand trace a curved "
        "attack or defense path; the partner reacts at the correct contact or miss, then recovers asymmetrically. "
        "Body motion must continue through camera cuts. No frozen fighters under camera motion.",
        f"Camera and shot sizes: {camera_lines}. These are actual cuts between distinct viewpoints, not one fixed side camera. "
        "Track travel only where it reveals force, maintain readable fists and contact, and keep the fighters large enough for a phone.",
        f"Ability behavior: {sequence.ability}",
        f"Transition: {sequence.transition}",
        "Canonical result: Omni-Man's final recorded heavy strike KOs Naruto. The hand-held Rasengan editorial attempt misses, "
        "causes zero damage, and is never thrown. Only the recorded wind shuriken and Energy Orb are projectiles.",
    ]
    return "\n\n".join(rows) + "\n"


def _negative(sequence) -> str:
    return (
        "No copied reference characters, exact shots, social-media UI, captions or logos. "
        "No photorealism, intricate comic rendering, detailed fabric or armor, over-rendered musculature, "
        "complex city, texture noise, extra fingers/limbs, missing punching arm, hand through torso, "
        "frozen figures, camera-only movement, floating feet, skating, flailing, torso folding, "
        "axis reversal, swapped screen lanes, extra hit, altered winner, excessive impact flash, "
        "detached or thrown Rasengan, Rasengan beam or Rasengan damage. "
        + ("No Rasengan before its editorial preparation." if sequence.index < 7 else
           "The Rasengan remains attached to Naruto's hand and does not contact Omni-Man.")
        + "\n"
    )


def _continuity(key) -> dict:
    state = _state(key)
    state["arena"] = "same sparse pale 2D street, faint lane and curb, no detailed city"
    state["lighting"] = "soft pale key with only two or three flat costume tones"
    # V3 camera grammar is stored separately because cuts need not inherit the
    # original v2 camera_x and zoom values.
    state.pop("camera_x")
    state.pop("zoom")
    return state


def _contact_sheet(output: Path) -> None:
    sheet = Image.new("RGB", (180 * 5, 320 * len(SEQUENCES)), (237, 239, 241))
    for row, sequence in enumerate(SEQUENCES):
        samples = [0, *[cue.time + .07 for cue in CAMERAS[sequence.index][1:3]],
                   sequence.duration * .65, sequence.duration]
        for column, time in enumerate(samples):
            image = frame_at(sequence.keys, sequence.index, min(time, sequence.duration), size=(180, 320))
            sheet.paste(image, (column * 180, row * 320))
    review = output / "review"
    review.mkdir(exist_ok=True)
    sheet.save(review / "motion_camera_contact_sheet.jpg", quality=85)


def build(output: Path = DEFAULT_OUTPUT, *, fps: int = 15) -> tuple[Path, dict]:
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Refusing to overwrite existing Seedance package: {output}")
    if not 3 <= fps <= 30:
        raise ValueError("Motion-reference FPS must be between 3 and 30")
    for name in REFERENCE_NAMES:
        if not (ART_SOURCE / name).is_file():
            raise FileNotFoundError(ART_SOURCE / name)
    replay = load_replay(SOURCE)
    plan, beats = build_plan(replay)
    output.mkdir(parents=True, exist_ok=True)
    shared = output / "shared_references"
    shared.mkdir()
    for name in REFERENCE_NAMES:
        shutil.copyfile(ART_SOURCE / name, shared / name)
    internal = output / "internal"
    internal.mkdir()
    shutil.copyfile(SOURCE, internal / "source_replay.json")
    write_json(internal / "episode_plan_28_shots.json", plan)
    write_json(internal / "fight_beats.json", beats)
    write_json(internal / "sequence_shot_map.json", [
        {"sequence": seq.index, "source_shots": [f"shot_{i:03d}" for i in range(seq.shot_first, seq.shot_last + 1)],
         "target_generation_seconds": seq.duration} for seq in SEQUENCES])
    write_json(output / "camera_plan.json", {f"sequence_{seq.index:02d}": [cue.__dict__ for cue in CAMERAS[seq.index]]
                                          for seq in SEQUENCES})
    motion_root = output / "motion_refs"
    motion_root.mkdir()
    for seq, motion_name in zip(SEQUENCES, MOTION_NAMES, strict=True):
        folder = output / "sequences" / f"sequence_{seq.index:02d}"
        folder.mkdir(parents=True)
        frame_at(seq.keys, seq.index, 0, size=(720, 1280)).save(folder / "start_frame.png")
        frame_at(seq.keys, seq.index, seq.duration, size=(720, 1280)).save(folder / "end_frame.png")
        metadata = motion_video(seq.keys, seq.index, seq.duration, motion_root / motion_name, fps=fps)
        (folder / "sequence_prompt.txt").write_text(_prompt(seq), encoding="utf-8")
        (folder / "sequence_negative_prompt.txt").write_text(_negative(seq), encoding="utf-8")
        write_json(folder / "continuity_start.json", _continuity(seq.keys[0]))
        write_json(folder / "continuity_end.json", _continuity(seq.keys[-1]))
        identities, style = _selected_references(seq.index)
        write_json(folder / "reference_manifest.json", {
            "sequence_id": f"sequence_{seq.index:02d}", "target_duration_seconds": seq.duration,
            "source_shot_ids": [f"shot_{i:03d}" for i in range(seq.shot_first, seq.shot_last + 1)],
            "start_frame": "start_frame.png", "end_frame": "end_frame.png",
            "motion_reference": "motion_reference.mp4", "motion_reference_master": motion_name,
            "motion_reference_role": "original lower-detail body/camera/cut guide; not production footage or canonical combat evidence",
            "identity_references": [f"../../shared_references/{name}" for name in identities],
            "style_reference": f"../../shared_references/{style}",
            "environment_reference": "../../shared_references/style_matched_environment.png",
            "optional_private_video_reference": {
                "name": "ExampleVideo1.MP4", "bundled": False,
                "role": "camera, pacing, impact timing and flat 2D style only; never exact shots or identities",
                "replaces_sequence_motion_reference": False,
            },
            "camera_cues": [cue.__dict__ for cue in CAMERAS[seq.index]],
            "upload_image_count": 8, "upload_video_count": 1,
            "motion_metadata": metadata, "provider_calls": 0,
        })
        (folder / "review_checklist.md").write_text(
            f"# Sequence {seq.index:02d}: {seq.name}\n\n"
            "- [ ] The separate camera viewpoints read as motivated cuts at normal speed\n"
            "- [ ] Naruto stays screen-left and Omni-Man screen-right across the fighting axis\n"
            "- [ ] Characters are flat, anatomically readable and immediately recognizable\n"
            "- [ ] Support feet, hands, actual contact or visible miss are readable\n"
            "- [ ] Rasengan remains attached to Naruto's palm and fails without damage\n"
            "- [ ] Only the recorded final Omni-Man heavy strike KOs Naruto\n", encoding="utf-8")
    _contact_sheet(output)
    review = output / "review"
    playlist = review / "motion_concat.txt"
    playlist.write_text("".join(f"file '../motion_refs/{name}'\n" for name in MOTION_NAMES), encoding="utf-8")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(playlist), "-c", "copy", str(review / "episode_motion_animatic.mp4")], check=True)
    write_json(output / "provenance.json", {
        "source_replay_checksum": SOURCE_CHECKSUM, "canonical_event_sha256": EVENT_SHA,
        "recorded_outcome": plan.outcome, "simulation_changed": False, "provider_calls": 0,
        "previous_package": "outputs/seedance_ready/naruto_vs_omniman_seedance25_v2",
        "noncanonical_editorial_staging": "failed hand-held Rasengan attempt; no contact or added damage",
        "identity_source": "local Naruto and Omni-Man identity boards only",
        "visual_assets": "ten original simplified flat 2D reference stills in assets/seedance/seed289_60s/style_matched_v3",
        "private_example_video": "creative style, motion and camera reference only; not copied or bundled",
        "motion_guides": "locally rendered flat 2D articulated blocking with original camera cuts; not generated final motion",
        "motion_reference_delivery": "720x1280 Lanczos upload masters; 360x640 individual masters removed after validation",
    })
    _documents(output)
    upgrade_motion_references(output)
    status = validate_v3(output)
    _readiness(output, status)
    return output, status


def validate_v3(output: Path) -> dict:
    output = output.resolve()
    issues: list[str] = []
    shared = output / "shared_references"
    names = {path.name for path in shared.glob("*.png")}
    if names != set(REFERENCE_NAMES):
        issues.append(f"Shared visual references differ: {sorted(names ^ set(REFERENCE_NAMES))}")
    for name in REFERENCE_NAMES:
        try:
            with Image.open(shared / name) as image:
                image.verify()
        except (OSError, FileNotFoundError):
            issues.append(f"Missing/corrupt visual reference: {name}")
    durations: list[int] = []
    camera_distribution: Counter[str] = Counter()
    for seq in SEQUENCES:
        folder = output / "sequences" / f"sequence_{seq.index:02d}"
        required = ("start_frame.png", "end_frame.png", "motion_reference.mp4",
                    "sequence_prompt.txt", "sequence_negative_prompt.txt", "continuity_start.json",
                    "continuity_end.json", "reference_manifest.json", "review_checklist.md")
        missing = [name for name in required if not (folder / name).is_file()]
        issues.extend(f"sequence_{seq.index:02d}: missing {name}" for name in missing)
        if missing:
            continue
        manifest = json.loads((folder / "reference_manifest.json").read_text())
        durations.append(manifest["target_duration_seconds"])
        if manifest["target_duration_seconds"] != seq.duration:
            issues.append(f"sequence_{seq.index:02d}: duration changed")
        if manifest.get("camera_cues") != [cue.__dict__ for cue in CAMERAS[seq.index]]:
            issues.append(f"sequence_{seq.index:02d}: camera plan changed")
        if len(manifest["camera_cues"]) < 3 or manifest["camera_cues"][0]["time"] != 0:
            issues.append(f"sequence_{seq.index:02d}: no internal camera cuts")
        camera_distribution.update(cue["angle"] for cue in manifest["camera_cues"])
        refs = [*manifest["identity_references"], manifest["style_reference"], manifest["environment_reference"]]
        if len(manifest["identity_references"]) != 4 or manifest["upload_image_count"] != 8:
            issues.append(f"sequence_{seq.index:02d}: upload image count invalid")
        for ref in refs:
            path = (folder / ref).resolve()
            if not path.is_relative_to(shared) or not path.is_file():
                issues.append(f"sequence_{seq.index:02d}: missing or unsafe image reference {ref}")
        for name in ("start_frame.png", "end_frame.png"):
            with Image.open(folder / name) as image:
                if image.size != (720, 1280):
                    issues.append(f"sequence_{seq.index:02d}: {name} wrong dimensions")
        prompt = (folder / "sequence_prompt.txt").read_text()
        negative = (folder / "sequence_negative_prompt.txt").read_text()
        if EXACT_STYLE_SENTENCE not in prompt or "Camera and shot sizes:" not in prompt:
            issues.append(f"sequence_{seq.index:02d}: prompt lacks style/camera direction")
        if "Rasengan" not in negative or "photorealism" not in negative:
            issues.append(f"sequence_{seq.index:02d}: negative prompt incomplete")
        if json.loads((folder / "continuity_start.json").read_text()) != _continuity(seq.keys[0]):
            issues.append(f"sequence_{seq.index:02d}: start continuity changed")
        if json.loads((folder / "continuity_end.json").read_text()) != _continuity(seq.keys[-1]):
            issues.append(f"sequence_{seq.index:02d}: end continuity changed")
        if seq.index > 1:
            previous = output / "sequences" / f"sequence_{seq.index-1:02d}"
            if (previous / "end_frame.png").read_bytes() != (folder / "start_frame.png").read_bytes():
                issues.append(f"sequence_{seq.index:02d}: image handoff differs")
            if (previous / "continuity_end.json").read_bytes() != (folder / "continuity_start.json").read_bytes():
                issues.append(f"sequence_{seq.index:02d}: continuity handoff differs")
        try:
            probe = _ffprobe(folder / "motion_reference.mp4")
            if ((probe["width"], probe["height"]) != SEEDANCE_MOTION_SIZE
                    or probe["width"] * probe["height"] < SEEDANCE_MIN_PIXELS
                    or abs(probe["duration_seconds"] - seq.duration) > .005):
                issues.append(f"sequence_{seq.index:02d}: motion video dimensions/duration wrong")
        except (OSError, KeyError, ValueError, subprocess.CalledProcessError):
            issues.append(f"sequence_{seq.index:02d}: motion video unreadable")
        master = output / "motion_refs_seedance" / manifest["motion_reference_master"]
        if (manifest.get("motion_reference_master_directory") != "motion_refs_seedance"
                or not master.is_file()
                or _sha256(master) != _sha256(folder / "motion_reference.mp4")):
            issues.append(f"sequence_{seq.index:02d}: master motion video mismatch")
        else:
            if not master.samefile(folder / "motion_reference.mp4"):
                issues.append(f"sequence_{seq.index:02d}: upload is not space-saving hard link to master")
            if manifest.get("motion_reference_sha256") != _sha256(master):
                issues.append(f"sequence_{seq.index:02d}: motion SHA-256 does not match manifest")
        source_probe = manifest.get("motion_reference_original_probe")
        if (not isinstance(source_probe, dict)
                or (source_probe.get("width"), source_probe.get("height")) != (W, H)
                or not manifest.get("motion_reference_source_sha256")):
            issues.append(f"sequence_{seq.index:02d}: original timing/hash provenance missing")
        else:
            try:
                if not _matching_timing(source_probe, _motion_probe(folder / "motion_reference.mp4")):
                    issues.append(f"sequence_{seq.index:02d}: frame count/rate/duration changed on upscale")
            except (OSError, KeyError, ValueError, subprocess.CalledProcessError):
                issues.append(f"sequence_{seq.index:02d}: cannot compare original and upload timing")
        if (output / "motion_refs" / manifest["motion_reference_master"]).exists():
            issues.append(f"sequence_{seq.index:02d}: redundant 360x640 original still present")
    required_angles = {"low", "side", "three_quarter", "high", "overhead", "over_shoulder"}
    if not required_angles.issubset(camera_distribution):
        issues.append("Missing required camera viewpoints")
    if len(durations) != 9 or sum(durations) != 60:
        issues.append(f"Expected nine sequences totaling 60 seconds; got {durations}")
    replay_path = output / "internal/source_replay.json"
    if not replay_path.is_file():
        issues.append("Canonical replay missing")
    else:
        replay = load_replay(replay_path)
        plan, _ = build_plan(replay)
        if replay["checksum"] != SOURCE_CHECKSUM or plan.canonical_event_sha256 != EVENT_SHA or plan.outcome != replay["result"]:
            issues.append("Canonical replay, event hash or outcome changed")
    animatic = output / "review/episode_motion_animatic.mp4"
    if not animatic.is_file():
        issues.append("Stitched 60-second animatic missing")
    else:
        try:
            probe = _ffprobe(animatic)
            if (probe["width"], probe["height"]) != (W, H) or abs(probe["duration_seconds"] - 60) > .15:
                issues.append("Stitched animatic dimensions/duration wrong")
        except (OSError, KeyError, ValueError, subprocess.CalledProcessError):
            issues.append("Stitched animatic unreadable")
    compliance_path = output / "review/motion_resolution_compliance.json"
    if not compliance_path.is_file():
        issues.append("Dreamina motion-resolution report missing")
    else:
        compliance = json.loads(compliance_path.read_text())
        if (not compliance.get("all_compliant") or not compliance.get("originals_removed")
                or not compliance.get("sequence_files_hardlinked_to_masters")
                or len(compliance.get("references", [])) != len(SEQUENCES)):
            issues.append("Dreamina motion-resolution report is incomplete")
    status = {"ready_for_sequence_01_test": not issues, "final_production_approved": False,
              "issues": issues, "sequence_count": len(durations), "total_target_duration_seconds": sum(durations),
              "shared_reference_count": len(names), "motion_reference_count": len(list((output / "motion_refs_seedance").glob("*.mp4"))),
              "dreamina_motion_refs_compliant": not any("motion" in issue.lower() or "360" in issue for issue in issues),
              "camera_distribution": dict(camera_distribution), "source_replay_checksum": SOURCE_CHECKSUM,
              "canonical_event_sha256": EVENT_SHA, "provider_calls": 0, "generated_motion_reviewed": False}
    write_json(output / "validation_seedance25_v3.json", status)
    return status


def _documents(output: Path) -> None:
    rows = ["# Seedance 2.5 v3: minimal 2D, multiple camera angles", "",
            "This is a new 60-second, nine-sequence derivative of the same canonical seed-289 replay. It is an upload/test package, not a generated episode.", "",
            "1. Review `review/motion_camera_contact_sheet.jpg` and the full `review/episode_motion_animatic.mp4` at phone size.",
            "2. In Dreamina, choose vertical 9:16 and test `sequences/sequence_01` only. Load its start/end frames and the six image references in its manifest (four character, one scene-style, one environment).",
            "3. Use its 720×1280 `motion_reference.mp4` for body travel and **camera cuts**. Paste its positive and negative prompts. The private ExampleVideo1 recording is optional inspiration only if Dreamina permits video references; it is not bundled and must never replace the sequence motion guide.",
            "4. Review generated sequence 01 at normal speed: actual viewpoint changes, no frozen fighter, stable identities, readable anatomy, no missing striking limb and no copied social UI.",
            "5. Continue only after that test succeeds. Keep each approved end frame aligned with the next start and document any replacement. Reject a clip with an airborne Rasengan or an added hit.", "",
            "| Sequence | Seconds | Camera views |", "|---|---:|---|" ]
    for seq in SEQUENCES:
        views = ", ".join(dict.fromkeys(cue.angle.replace("_", "-") for cue in CAMERAS[seq.index]))
        rows.append(f"| {seq.index:02d} {seq.name} | {seq.duration} | {views} |")
    rows += ["", "The nine motion uploads meet Dreamina's 409,600-pixel minimum: each is 720×1280 (921,600 pixels). See `review/motion_resolution_compliance.md`. The individual 360×640 source guides are removed after validation to save space; the separate 360×640 stitched review animatic is not for upload.",
             "", "The source video guided broad camera grammar and minimal animation style only. Its exact characters, poses, UI and cuts are not reproduced. The generated stills are simpler than a detailed comic illustration: flat costume color masses, sparse pale ground, readable face marks and body silhouettes.",
             "", "The 28-shot attribution and event hash are unchanged. The hand-held Rasengan entry is an editorial attempt that misses; the final heavy strike alone records Omni-Man's KO. Motion-guide quality is not proof of generated-motion quality. No provider call has been made.", ""]
    (output / "seedance25_manual_workflow.md").write_text("\n".join(rows), encoding="utf-8")
    write_json(output / "review/camera_distribution.json", {
        "angle_counts": dict(Counter(cue.angle for cues in CAMERAS.values() for cue in cues)),
        "sequence_cuts": {f"{index:02d}": [cue.__dict__ for cue in cues] for index, cues in CAMERAS.items()},
        "axis_rule": "Naruto left; Omni-Man right; camera elevates and pushes in but does not reverse screen lanes",
    })


def _readiness(output: Path, status: dict) -> None:
    (output / "seedance25_readiness.md").write_text(
        "# V3 visual and camera readiness\n\n"
        f"**{'Technically ready for sequence-01 generation test' if status['ready_for_sequence_01_test'] else 'Blocked'}.** "
        f"{status['sequence_count']} sequences, {status['total_target_duration_seconds']} seconds, "
        f"{status['shared_reference_count']} flat style-matched stills, {status['motion_reference_count']} Dreamina-compliant 720×1280 multi-angle guides. "
        f"Validation issues: {len(status['issues'])}.\n\n"
        "Compared with v2, the visual reference layer now has minimal recognizable faces and solid body masses in the pale, sparse aesthetic of the private example. "
        "The motion guides contain explicit cuts among wide, low, side, high, overhead, over-shoulder and three-quarter views. "
        "They are useful blocking guides, not finished martial-arts animation; their drawing remains schematic.\n\n"
        "**Generated motion, identity stability, contact, and camera execution remain unverified.** Test sequence 01 in Dreamina and inspect its actual clip at normal speed before claiming parity with the example or proceeding through the upload queue. "
        "The nine-sequence package preserves the replay/event hash and winner; no paid API was called.\n\n"
        + ("\n".join(f"- {issue}" for issue in status["issues"]) if status["issues"] else "No structural validation issues.") + "\n",
        encoding="utf-8",
    )
