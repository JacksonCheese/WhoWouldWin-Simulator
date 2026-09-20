"""Encode normal-speed hero exchange videos and contact sheets."""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import imageio_ffmpeg
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "outputs/combat_motion_lab_hero_exchange"
VIEWS = ("preview", "side", "three-quarter", "front-diagonal", "top")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(folder: Path, target: Path):
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-framerate", "30",
        "-i", str(folder / "%04d.png"), "-frames:v", "120",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target),
    ], check=True, capture_output=True)


def sheet(folder: Path, target: Path):
    frames = (1, 8, 16, 23, 31, 38, 47, 56, 66, 76, 82, 85, 88, 93, 106, 120)
    width, height, label_height, columns = 180, 320, 20, 4
    rows = 4
    canvas = Image.new("RGB", (width * columns, (height + label_height) * rows), (18, 20, 24))
    draw = ImageDraw.Draw(canvas)
    for index, frame in enumerate(frames):
        image = Image.open(folder / f"{frame:04d}.png").convert("RGB").resize((width, height))
        x = index % columns * width
        y = index // columns * (height + label_height)
        canvas.paste(image, (x, y))
        draw.text((x + 5, y + height + 3), f"frame {frame}", fill="white")
    canvas.save(target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    media = []
    for view in VIEWS:
        folder = output / "renders" / view / "frames"
        missing = [frame for frame in range(1, 121) if not (folder / f"{frame:04d}.png").exists()]
        if missing:
            raise RuntimeError(f"{view}: {len(missing)} frames missing")
        target = output / ("clean-debug-preview.mp4" if view == "preview" else f"review/{view}.mp4")
        target.parent.mkdir(parents=True, exist_ok=True)
        encode(folder, target)
        reader = imageio_ffmpeg.read_frames(str(target))
        metadata = next(reader)
        count = sum(1 for _ in reader)
        if count != 120 or metadata["size"] != (360, 640) or metadata["fps"] != 30:
            raise RuntimeError((view, metadata, count))
        sheet(folder, output / f"review/{view}-contact-sheet.png")
        media.append({
            "view": view,
            "path": str(target.relative_to(output)),
            "sha256": digest(target),
            "frames": count,
            "duration_seconds": count / 30,
            "resolution": [360, 640],
        })
    payload = {
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "scene_sha256": digest(output / "scene.blend"),
        "events_sha256": digest(output / "source/events.json"),
        "normal_speed": True,
        "editorial_retime": False,
        "media": media,
    }
    (output / "review/delivery-provenance.json").write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
