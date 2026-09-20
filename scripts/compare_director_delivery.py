"""Compare matching source frames; captions distinguish source from output time."""
from pathlib import Path
import imageio_ffmpeg
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/first_production_fight_astra_final"
FRAMES = [56, 69, 106, 196, 286, 316, 354, 365, 371, 379, 406, 476]


def main():
    reader = imageio_ffmpeg.read_frames(str(ROOT / "outputs/first_production_fight_v2/renders/quality-preview/fight.mp4"))
    metadata = next(reader)
    assert metadata["fps"] == 30
    old = {}
    for frame, pixels in enumerate(reader, 1):
        if frame in FRAMES:
            old[frame] = Image.frombytes("RGB", metadata["size"], pixels)
    assert len(old) == len(FRAMES)
    for start in range(0, len(FRAMES), 4):
        chosen = FRAMES[start:start + 4]
        result = Image.new("RGB", (4 * 180, 690), "#17191f")
        draw = ImageDraw.Draw(result)
        for index, frame in enumerate(chosen):
            for row, img in enumerate((old[frame], Image.open(OUT / f"renders/quality-preview/frames/{frame:04d}.png"))):
                x, y = index * 180, row * 345
                result.paste(img.convert("RGB").resize((180, 320)), (x, y + 20))
                draw.text((x + 4, y + 4), f'{"V2" if row == 0 else "DIRECTOR"} | source {frame}', fill="white")
        # Each source pair uses one column; keep labels and images phone-readable.
        result.save(OUT / f"review/v2-director-comparison-{start//4+1:02d}.jpg")
    print("Created three comparisons of matching source frames.")


if __name__ == "__main__":
    main()
