"""Build deterministic V4 review contact sheets from diagnostic frames."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "outputs/blender_combat_v4_humanoid/review"
FRAMES = REVIEW / "frames"
SELECTED = (145, 158, 163, 165, 172, 184, 210, 245, 271, 277, 287, 300)


def contact_sheet(label: str, output: Path, columns: int = 4) -> None:
    images = [(frame, Image.open(FRAMES / f"{label}_{frame:03d}.png").convert("RGB")) for frame in SELECTED]
    thumb_width = 400 if label == "static" else 225
    thumb_height = 300 if label == "static" else 400
    header = 58
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + header)), "#17191d")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=22)
    captions = {
        145: "counter setup",
        158: "anticipation",
        163: "contact",
        165: "hit stop",
        172: "reaction",
        184: "launch",
        210: "tumble",
        245: "descent",
        271: "pre-landing",
        277: "compression",
        287: "recoil / skid",
        300: "settle",
    }
    for index, (frame, image) in enumerate(images):
        image.thumbnail((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        x = (index % columns) * thumb_width + (thumb_width - image.width) // 2
        y = (index // columns) * (thumb_height + header)
        sheet.paste(image, (x, y))
        draw.text((x + 10, y + thumb_height + 8), f"f{frame}  {captions[frame]}", fill="white", font=font)
    sheet.save(output, optimize=True)


def main() -> None:
    contact_sheet("static", REVIEW / "motion-contact-sheet.png")
    contact_sheet("cinematic", REVIEW / "cinematic-contact-sheet.png")


if __name__ == "__main__":
    main()
