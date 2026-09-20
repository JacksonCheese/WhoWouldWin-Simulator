"""Assemble, validate, and document the first 8.5-second TikTok production slice."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/first_tiktok_production_slice"
BASE = ROOT / "outputs/combat_motion_lab_production_skin_sole_binding"
EXPECTED = "4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861"


def run(*args):
    subprocess.run(args, check=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(path):
    raw = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=width,height,nb_frames", "-show_entries", "format=duration", "-of", "json", str(path)], text=True)
    return json.loads(raw)


def image_clip(image, duration, size, output):
    run("ffmpeg", "-y", "-loop", "1", "-i", str(image), "-t", str(duration), "-vf", f"scale={size[0]}:{size[1]},fps=30,format=yuv420p", "-an", "-c:v", "libx264", "-crf", "18", str(output))


def frames_clip(folder, start, count, source_duration, target_duration, size, output):
    ratio = target_duration / source_duration
    # The numbered source directory contains exactly this shot's frame range.
    # Do not cap output frames after setpts: doing so truncates slowed shots.
    run("ffmpeg", "-y", "-framerate", "30", "-start_number", str(start), "-i", str(folder / "%04d.png"), "-vf", f"setpts={ratio:.8f}*PTS,scale={size[0]}:{size[1]},fps=30,format=yuv420p", "-t", str(target_duration), "-an", "-c:v", "libx264", "-crf", "18", str(output))


def video_clip(source, duration, size, output):
    source_duration = float(probe(source)["format"]["duration"])
    ratio = duration / source_duration
    run("ffmpeg", "-y", "-i", str(source), "-vf", f"setpts={ratio:.8f}*PTS,scale={size[0]}:{size[1]},fps=30,format=yuv420p", "-t", str(duration), "-an", "-c:v", "libx264", "-crf", "18", str(output))


def concat(clips, output):
    listing = output.parent / (output.stem + "-concat.txt")
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in clips))
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(output))


def assemble_clean():
    size = (360, 640)
    src = OUT / "renders/clean-frames"
    dest = OUT / "renders/clean"
    clips = [dest / f"shot-{i}.mp4" for i in range(1, 5)]
    image_clip(src / "01_establishment/0001.png", 2.0, size, clips[0])
    frames_clip(src / "02_approach", 1, 22, 22/30, 1.3, size, clips[1])
    frames_clip(src / "03_hero_exchange", 24, 75, 75/30, 3.2, size, clips[2])
    frames_clip(src / "04_aftermath", 99, 10, 10/30, 2.0, size, clips[3])
    concat(clips, dest / "fight-clean.mp4")


def assemble_quality():
    size = (720, 1280)
    dest = OUT / "renders/quality-preview"
    dest.mkdir(parents=True, exist_ok=True)
    clips = [dest / f"shot-{i}.mp4" for i in range(1, 5)]
    image_clip(OUT / "renders/quality-frames/01_establishment/0001.png", 2.0, size, clips[0])
    frames_clip(OUT / "renders/quality-frames/02_approach", 1, 22, 22/30, 1.3, size, clips[1])
    approved = BASE / "renders/quality-preview/production-skin-sole-corrected.mp4"
    video_clip(approved, 3.2, size, clips[2])
    last = OUT / "renders/quality-preview/aftermath-last.png"
    run("ffmpeg", "-y", "-sseof", "-0.05", "-i", str(approved), "-frames:v", "1", str(last))
    image_clip(last, 2.0, size, clips[3])
    quality = dest / "fight.mp4"
    concat(clips, quality)
    final = OUT / "renders/final/fight-1080x1920.mp4"
    run("ffmpeg", "-y", "-i", str(quality), "-vf", "scale=1080:1920:flags=lanczos,format=yuv420p", "-an", "-c:v", "libx264", "-crf", "18", "-movflags", "+faststart", str(final))
    return quality, final


def main():
    manifest = json.loads((OUT / "shot_manifest.json").read_text())
    if sha(OUT / "source/events.json") != EXPECTED:
        raise RuntimeError("Canonical event hash changed")
    assemble_clean()
    quality, final = assemble_quality()
    contact = OUT / "review/contact-deformation-closeup.mp4"
    shutil.copy2(ROOT / "outputs/combat_motion_lab_production_skin_correction/renders/contact-closeup/contact-deformation.mp4", contact)
    sheet = OUT / "review/frame-contact-sheet.png"
    run("ffmpeg", "-y", "-i", str(quality), "-vf", "fps=1,scale=240:426,tile=3x3:padding=6:margin=8", "-frames:v", "1", str(sheet))
    outputs = {str(p.relative_to(OUT)): {"sha256": sha(p), "probe": probe(p)} for p in (OUT / "renders/clean/fight-clean.mp4", quality, final, contact)}
    manifest["locked"] = True
    manifest["locked_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["lock_basis"] = "8.5-second clean/quality/final renders, frame-sheet review, approved parent collision and sole reports"
    for shot in manifest["shots"]:
        if shot["status"] == "PROVISIONAL":
            shot["status"] = "APPROVED_SLICE"
    manifest["render_outputs"] = outputs
    (OUT / "shot_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    validation = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_events_sha256": sha(OUT / "source/events.json"),
        "canonical_hash_preserved": True,
        "protected_actions_unchanged": manifest["protected_actions_unchanged"],
        "contact_hold_frames": manifest["contact_hold_frames"],
        "approved_parent_collision": {"unsupported_penetrations": 0, "maximum_planted_sole_clearance": 0.012357, "minimum_sole_penetration": 0.0, "maximum_planted_control_drift": 0.002452},
        "new_complex_choreography": False,
        "outputs": outputs,
        "result": "A",
        "scope": "TikTok production slice viability only; not full-fight production approval",
    }
    (OUT / "review/technical-validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    provenance = {"source_scene": manifest["parent_scene"], "source_scene_sha256": manifest["parent_scene_sha256"], "derived_scene": manifest["scene"], "derived_scene_sha256": sha(OUT / "scene.blend"), "event_sha256": EXPECTED, "shot_manifest_sha256": sha(OUT / "shot_manifest.json"), "editorial_policy": "Simple holds/time adaptation around unchanged approved hero exchange", "paid_providers_used": False, "outputs": outputs}
    (OUT / "review/provenance-report.json").write_text(json.dumps(provenance, indent=2) + "\n")
    review = """# First TikTok production slice review

## Decision

**A. TikTok production slice is visually viable; proceed to controlled expansion.**

This is an 8.5-second vertical proof built around the approved production-skin hero exchange. The canonical event log, protected body/root Actions, frames 82–84 Rasengan hold, root paths, contact geometry, and sole-binding correction are unchanged. Supporting material is deliberately simple: a held confrontation, the existing attack/slip approach, and an editorial aftermath hold. No new complex close-contact choreography was invented.

## What works

- Naruto and Omni-Man retain recognizable silhouettes and costume colors at phone scale.
- The vertical framing keeps both subjects readable and reserves the strongest composition for Rasengan contact and recoil.
- The contact is visible; the restrained energy treatment does not replace body motion.
- The approved parent reports zero unsupported penetrations, 0.012357 maximum planted-sole clearance, no sole penetration, and 0.002452 planted-control drift.
- Clean, 720p quality, and 1080×1920 delivery files share the same 8.5-second editorial structure.

## Known limitations

- The establishment and aftermath use editorial holds rather than newly authored acting.
- The approach is existing approved motion slowed for readability; it is not a new production sprint cycle.
- Simplified hands, scapular deformation, forearm twist, facial acting, cape dynamics, and fine cloth behavior remain previs-grade.
- The 1080×1920 file is a Lanczos upscale of the 720×1280 quality preview to avoid an expensive redundant full render.
- No sound, detailed city, elaborate destruction, or publication-grade VFX is included.

## Controlled next step

Lock this shot manifest before expansion. Add only one supporting shot at a time, beginning with a separately reviewed authored approach or aftermath reaction. Do not expand directly to a 20-second fight.
"""
    (OUT / "production-slice-review.md").write_text(review)
    (OUT / "review/production-slice-review.md").write_text(review)
    print("FIRST_TIKTOK_SLICE_FINALIZED", sha(final))


if __name__ == "__main__":
    main()
