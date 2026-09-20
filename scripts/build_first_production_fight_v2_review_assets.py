"""Assemble labeled V2 collision-review sheets from Blender-rendered stills."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/first_production_fight_v2"


def main() -> None:
    report_path = OUTPUT / "review/collision_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    required = [289, 296, 303, 316, 332, 336, 357, 360, 362, 365, 368, 371, 375, 379]
    frames = list(dict.fromkeys(report["worst_frames"] + required))
    source = OUTPUT / "review/collision_frames"
    if not source.exists() or not any(source.glob("*.png")):
        source = OUTPUT / "review/motion_frames"
    cards: list[Image.Image] = []
    issues_by_frame: dict[int, list[dict]] = {}
    for issue in report["all_issues"]:
        issues_by_frame.setdefault(issue["frame"], []).append(issue)
    for frame in frames:
        path = source / f"frame_{frame:04d}.png"
        if not path.exists():
            continue
        image = Image.open(path).convert("RGB")
        draw = ImageDraw.Draw(image)
        frame_issues = issues_by_frame.get(frame, [])
        unintentional = [item for item in frame_issues if not item["intentional"]]
        deepest = max((item["penetration_depth"] for item in unintentional), default=0.0)
        draw.rectangle((0, 0, image.width, 42), fill=(6, 8, 12))
        draw.text((8, 5), f"frame {frame}  unsupported={len(unintentional)}  max={deepest:.3f}", fill=(255, 255, 255))
        if unintentional:
            pair = " / ".join(unintentional[0]["proxy_pair"])
            draw.text((8, 23), pair, fill=(255, 120, 90))
        else:
            draw.text((8, 23), "intentional contact or clear", fill=(90, 230, 150))
        cards.append(image)
    if not cards:
        raise SystemExit("No review frames are available; render the Blender review stills first")
    width, height = cards[0].size
    columns = 3
    rows = (len(cards) + columns - 1) // columns
    sheet = Image.new("RGB", (width * columns, height * rows), (10, 12, 16))
    for index, card in enumerate(cards):
        sheet.paste(card, ((index % columns) * width, (index // columns) * height))
    target = OUTPUT / "review/collision_contact_sheet.png"
    sheet.save(target)
    print(target)


if __name__ == "__main__":
    main()
