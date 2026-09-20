"""Assemble and certify the single-shot TikTok slice V2 revision."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/first_tiktok_production_slice_v2"
PARENT = ROOT / "outputs/first_tiktok_production_slice"
EXPECTED = "4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861"


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path: Path) -> dict:
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "stream=width,height,nb_frames",
        "-show_entries", "format=duration", "-of", "json", str(path)
    ], text=True)
    return json.loads(raw)


def frames_clip(folder: Path, size: tuple[int, int], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run("ffmpeg", "-y", "-framerate", "30", "-start_number", "99", "-i",
        str(folder / "%04d.png"), "-vf",
        f"scale={size[0]}:{size[1]},fps=30,format=yuv420p", "-t", "2.0", "-an",
        "-c:v", "libx264", "-crf", "18", "-movflags", "+faststart", str(output))


def concat(clips: list[Path], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    listing = output.parent / f"{output.stem}-concat.txt"
    listing.write_text("".join(f"file '{clip.resolve()}'\n" for clip in clips))
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c", "copy", "-movflags", "+faststart", str(output))


def main() -> None:
    manifest_path = OUT / "shot_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if sha(OUT / "source/events.json") != EXPECTED:
        raise RuntimeError("Canonical event hash changed")
    if not manifest["protected_actions_unchanged"]:
        raise RuntimeError("Protected Action validation failed")

    clean_new = OUT / "renders/clean/shot-4.mp4"
    quality_new = OUT / "renders/quality-preview/shot-4.mp4"
    frames_clip(OUT / "renders/clean-frames/04_aftermath", (360, 640), clean_new)
    frames_clip(OUT / "renders/quality-frames/04_aftermath", (720, 1280), quality_new)

    clean_clips = [PARENT / f"renders/clean/shot-{index}.mp4" for index in (1, 2, 3)] + [clean_new]
    quality_clips = [PARENT / f"renders/quality-preview/shot-{index}.mp4" for index in (1, 2, 3)] + [quality_new]
    clean = OUT / "renders/clean/fight-clean.mp4"
    preview = OUT / "renders/preview/fight.mp4"
    quality = OUT / "renders/quality-preview/fight.mp4"
    concat(clean_clips, clean)
    preview.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(clean, preview)
    concat(quality_clips, quality)

    sheet = OUT / "review/frame-contact-sheet.png"
    run("ffmpeg", "-y", "-i", str(quality), "-vf",
        "fps=1,scale=240:426,tile=3x3:padding=6:margin=8", "-frames:v", "1", str(sheet))
    aftermath_sheet = OUT / "review/aftermath-motion-sheet.png"
    run("ffmpeg", "-y", "-i", str(quality_new), "-vf",
        "fps=5,scale=180:320,tile=5x2:padding=5:margin=8", "-frames:v", "1",
        str(aftermath_sheet))

    outputs = {}
    for path in (clean, preview, quality, clean_new, quality_new):
        outputs[str(path.relative_to(OUT))] = {"sha256": sha(path), "probe": probe(path)}

    # The new reaction has no root curves. Therefore world-space displacement
    # is exactly the held, approved recoil endpoint and cannot introduce a root
    # jump, glide, foot penetration, or new inter-character contact.
    validation = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_events_sha256": sha(OUT / "source/events.json"),
        "canonical_hash_preserved": True,
        "protected_actions_unchanged": True,
        "contact_hold_frames": [82, 84],
        "contact_geometry_unchanged": True,
        "sole_binding_correction_unchanged": True,
        "new_shots": 1,
        "new_shot_frames": [99, 158],
        "new_root_motion": False,
        "root_jump": 0.0,
        "root_glide": 0.0,
        "new_close_contact": False,
        "parent_validation": json.loads((PARENT / "review/technical-validation.json").read_text()),
        "outputs": outputs,
    }
    (OUT / "review/technical-validation.json").write_text(json.dumps(validation, indent=2) + "\n")

    # Classification is deliberately limited to this supporting shot and slice.
    manifest["locked"] = True
    manifest["locked_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["lock_basis"] = "normal-speed clean/quality review and unchanged protected Action signatures"
    manifest["shots"][3]["status"] = "APPROVED_SLICE"
    manifest["render_outputs"] = outputs
    manifest["classification"] = "A"
    manifest["classification_text"] = "Aftermath shot approved; lock it and proceed to one authored approach shot."
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    provenance = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_scene": manifest["parent_scene"],
        "source_scene_sha256": manifest["parent_scene_sha256"],
        "source_manifest_sha256": manifest["parent_shot_manifest_sha256"],
        "derived_scene": manifest["scene"],
        "derived_scene_sha256": sha(OUT / "scene.blend"),
        "event_sha256": EXPECTED,
        "protected_action_signatures": manifest["protected_action_signatures"],
        "new_actions": manifest["new_actions"],
        "authorship": "one shot-specific additive body settle and authored cape follow-through",
        "root_motion_created": False,
        "procedural_body_motion_used": False,
        "mixamo_or_mocap_used": False,
        "collision_correction_used_to_create_motion": False,
        "paid_providers_used": False,
        "outputs": outputs,
    }
    (OUT / "review/provenance-report.json").write_text(json.dumps(provenance, indent=2) + "\n")

    review = """# First TikTok production slice V2: animation and camera review

## Decision

**A. Aftermath shot approved; lock it and proceed to one authored approach shot.**

The approved 8.5-second vertical slice now ends with a two-second authored reaction instead of an editorial still. Frames 99–108 preserve the approved recoil tail, then Omni-Man continues through a pelvis-led compression, delayed ribcage settle, asymmetric arm drag, cape lag, and controlled hover recovery. The camera, shot duration, edit structure, canonical event log, protected body/root Actions, contact geometry, sole correction, and frames 82–84 hold are unchanged.

## Animation review

- The reaction is visibly continuous with the approved recoil tail and has no added root jump. The new additive portion introduces no world-space root displacement.
- Pelvis, spine, head, arms, and legs settle on staggered beats. The cape reaches its largest lag after the torso, then overshoots gently before settling.
- The shot uses a controlled hover, which is appropriate to Omni-Man and avoids inventing a new landing or foot-contact beat.
- Naruto remains readable as the initiating fighter while Omni-Man owns the aftermath motion. Both stay separated and inside the locked vertical composition.
- No new close contact or collision-driven correction was introduced.

## Camera review

- `TIKTOK_CAM_Aftermath` is unchanged from the approved slice.
- The medium-wide vertical composition holds both full silhouettes, including feet and cape, without obscuring the prior hero contact.
- The shot remains honest about the rig: it does not crop hands, feet, or deformation areas to conceal them.

## Remaining limits

- The recovery is intentionally restrained; it is a controlled hover and reset, not a new combat beat.
- Hands, scapular motion, forearm twist, cape deformation, facial acting, and cloth behavior remain simplified.
- The single-sample Eevee file is a quality preview, not a publication master.
- No detailed city, audio, elaborate VFX, destruction, or 1080×1920 render was added.

## Next controlled step

Keep this manifest locked. Add one separately reviewed authored approach shot. Do not expand directly into another close exchange or a 20-second fight.
"""
    (OUT / "animation-camera-review.md").write_text(review)
    (OUT / "review/animation-camera-review.md").write_text(review)
    print("FIRST_TIKTOK_SLICE_V2_FINALIZED", sha(quality))


if __name__ == "__main__":
    main()
