"""Verify final media and provenance without claiming aesthetic approval."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/first_production_fight_astra_final"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    scene_hash = digest(OUT / "scene.blend")
    audit = json.loads((OUT / "review/saved-scene-audit.json").read_text())
    assert audit["scene_sha256"] == scene_hash, "Saved-scene audit is stale"
    for key in ("director_source_matches_saved_scene", "certified_source_scene_unchanged", "events_unchanged"):
        assert audit[key], key
    assert audit["frames_collision_validated"] == 540
    assert audit["unsupported_proxy_issues"] == 0
    renders = {}
    for label, size in (("preview", [360, 640]), ("quality-preview", [720, 1280])):
        folder = OUT / "renders" / label / "frames"
        provenance = json.loads((folder / "render-provenance.json").read_text())
        assert provenance["scene_sha256"] == scene_hash, label + " scene mismatch"
        assert provenance["resolution"] == size
        assert provenance["renderer_sha256"] == digest(ROOT / "scripts/render_director_final.py")
        missing = [i for i in range(1, 541) if not (folder / f"{i:04d}.png").exists()]
        assert not missing, (label, missing)
        frame_hashes = {f"{i:04d}.png": digest(folder / f"{i:04d}.png") for i in range(1, 541)}
        (OUT / "review" / f"{label}-frame-hashes.json").write_text(json.dumps(frame_hashes, indent=2))
        renders[label] = provenance
    media = []
    for relative, dimensions, expected_frames in (
        ("renders/preview/fight.mp4", (360, 640), 456),
        ("renders/quality-preview/fight.mp4", (720, 1280), 456),
        ("review/hero-impact-fast.mp4", (360, 640), 69),
        ("review/hero-impact.mp4", (720, 1280), 69),
    ):
        path = OUT / relative
        reader = imageio_ffmpeg.read_frames(str(path))
        metadata = next(reader)
        assert metadata["size"] == dimensions, (relative, metadata)
        assert metadata["fps"] == 30
        decoded = sum(1 for _ in reader)
        assert decoded == expected_frames, (relative, decoded)
        # Full decode catches corrupt/incomplete video packets, not bad animation.
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(path),
                        "-f", "null", "-"], check=True, capture_output=True)
        media.append({"path": relative, "sha256": digest(path), "bytes": path.stat().st_size,
                      "resolution": dimensions, "fps": 30, "decoded_frames": decoded,
                      "duration_seconds": decoded / 30, "decode_ok": True})
    payload = {
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "scene_sha256": scene_hash,
        "director_source_sha256": digest(ROOT / "scripts/blender_director_final.py"),
        "source_events_sha256": digest(OUT / "source/events.json"),
        "renders": renders,
        "media": media,
        "audit": audit,
        "visual_approval": "PENDING; numeric and decode checks are not animation approval",
        "normal_speed_human_viewing_certified": False,
    }
    (OUT / "review/delivery-provenance.json").write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
