"""Local deterministic comic-layout storyboards. No model, network or combat execution."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import hashlib
import math
from PIL import Image, ImageDraw, ImageFont
from .schemas import DirectorSettings, Shot, ShotType, VisualProfile


@dataclass(frozen=True)
class RenderContext:
    project: Path
    settings: DirectorSettings
    visuals: dict[str, VisualProfile]
    names: dict[str, str]


@dataclass(frozen=True)
class StoryboardFrame:
    shot_id: str
    path: Path
    width: int
    height: int
    sha256: str


class StoryboardRenderer(Protocol):
    def render(self, shot: Shot, context: RenderContext) -> StoryboardFrame: ...


def font(size: int, bold=False):
    # Pillow's bundled font avoids machine-specific font discovery in fixtures.
    return ImageFont.load_default(size=max(9, size))


def wrapped(draw, text, x, y, width, *, size, color, line_limit=5):
    face = font(size)
    words = text.split()
    line = ""
    lines = []
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=face) > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    if len(lines) > line_limit:
        lines = lines[:line_limit]
        lines[-1] = lines[-1].rstrip(".,") + "…"
    for line in lines:
        draw.text((x, y), line, font=face, fill=color)
        y += size * 1.35
    return y


def figure(draw, x, y, scale, color, pose="guard", facing=1, face_only=False):
    """An expressive blocking silhouette, deliberately labelled as a mock asset."""

    def p(a, b):
        return (x + a * scale * facing, y + b * scale)

    ink = "#0B1422"
    light = "#EDE8DD"
    width = max(2, round(scale * 0.055))
    if face_only:
        draw.polygon(
            [
                p(-0.62, -1.05),
                p(0.35, -1.18),
                p(0.67, -0.6),
                p(0.51, 0.38),
                p(0.05, 0.71),
                p(-0.55, 0.4),
            ],
            fill=color,
            outline=ink,
            width=width,
        )
        draw.polygon(
            [
                p(-0.72, -0.55),
                p(-0.76, -1.2),
                p(-0.28, -1.05),
                p(-0.07, -1.45),
                p(0.15, -1.12),
                p(0.59, -1.2),
                p(0.55, -0.72),
            ],
            fill=ink,
        )
        draw.line([p(-0.35, -0.38), p(-0.06, -0.3)], fill=ink, width=width * 2)
        draw.line([p(0.15, -0.28), p(0.43, -0.4)], fill=ink, width=width * 2)
        draw.line([p(-0.14, 0.2), p(0.31, 0.13)], fill=light, width=width)
        return
    draw.ellipse(
        (
            [p(-0.24, -2.13), p(0.24, -1.61)]
            if facing == 1
            else [p(0.24, -2.13), p(-0.24, -1.61)]
        ),
        fill=color,
        outline=ink,
        width=width,
    )
    draw.polygon(
        [p(-0.38, -1.5), p(0.32, -1.5), p(0.4, -0.76), p(0.22, -0.3), p(-0.25, -0.3)],
        fill=color,
        outline=ink,
        width=width,
    )
    draw.polygon(
        [p(-0.25, -0.36), p(0.02, -0.26), p(-0.16, 0.57), p(-0.42, 0.63)], fill=ink
    )
    draw.polygon(
        [p(0.06, -0.28), p(0.27, -0.36), p(0.5, 0.52), p(0.23, 0.61)], fill=ink
    )
    arms = [
        (-0.35, -1.36, -0.63, -0.9, -0.4, -0.65),
        (0.31, -1.32, 0.55, -0.98, 0.75, -1.5),
    ]
    if pose == "attack":
        arms = [
            (-0.35, -1.35, -0.55, -0.8, -0.25, -0.55),
            (0.3, -1.3, 0.84, -1.37, 1.36, -1.35),
        ]
    if pose == "power":
        arms = [
            (-0.35, -1.35, -0.65, -1.1, -0.8, -0.57),
            (0.3, -1.3, 0.62, -1.1, 0.75, -0.57),
        ]
    for a, b, c, d, e, f in arms:
        draw.line([p(a, b), p(c, d), p(e, f)], fill=ink, width=round(scale * 0.27))
        draw.line([p(a, b), p(c, d), p(e, f)], fill=color, width=round(scale * 0.18))
        px, py = p(e, f)
        radius = scale * 0.11
        draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color)


class MockStoryboardRenderer:
    def render(self, shot: Shot, context: RenderContext) -> StoryboardFrame:
        width, height = context.settings.width, context.settings.height
        image = Image.new("RGB", (width, height))
        d = ImageDraw.Draw(image)
        u = width / 1080
        for y in range(height):
            t = y / height
            d.line(
                (0, y, width, y),
                fill=(int(13 + 13 * t), int(22 + 15 * t), int(36 + 18 * t)),
            )
        accent = "#E5C58D"
        white = "#F4EEE4"
        muted = "#90A8BC"
        margin = int(width * 0.065)
        top = height * 0.18
        bottom = height * 0.76
        scene_h = bottom - top
        # Etched skyline and perspective floor: consistent stage, different shot blocking.
        seed = int(hashlib.sha256(shot.shot_id.encode()).hexdigest()[:8], 16)
        for i in range(15):
            x = i * width / 14
            roof = top + scene_h * (0.25 + ((seed + i * 31) % 37) / 100)
            d.rectangle(
                (x, roof, x + width * 0.065, bottom),
                fill="#1C3047",
                outline="#38506A",
                width=max(1, int(u)),
            )
            for yy in range(int(roof + 15 * u), int(bottom), max(10, int(35 * u))):
                d.line(
                    (x + 12 * u, yy, x + 19 * u, yy),
                    fill="#6D7373",
                    width=max(1, int(2 * u)),
                )
        for i in range(9):
            d.line(
                (width * 0.5, top + scene_h * 0.75, (i - 2) * width * 0.25, bottom),
                fill="#476078",
                width=max(1, int(2 * u)),
            )
        d.line(
            (margin, top, width - margin, top), fill=accent, width=max(1, int(2 * u))
        )
        d.line(
            (margin, bottom, width - margin, bottom),
            fill=accent,
            width=max(1, int(2 * u)),
        )
        colors = {key: context.visuals[key].color_palette[0] for key in shot.subjects}
        close = shot.shot_type in {
            ShotType.CLOSE_UP,
            ShotType.EXTREME_CLOSE_UP,
            ShotType.REACTION,
        }
        for j, key in enumerate(shot.subjects):
            point = shot.subject_positions[key]
            x = point.x * width
            y = top + point.y * scene_h
            factor = 0.18 * width if j == 0 else 0.12 * width
            if shot.shot_type == ShotType.OVER_SHOULDER and j == 0:
                x = width * 0.05
                y = bottom + width * 0.06
                factor = width * 0.34
            if shot.shot_type in {ShotType.POV, ShotType.LOW_ANGLE}:
                factor = width * 0.27
                y = bottom - width * 0.16
            if shot.shot_type in {ShotType.AERIAL, ShotType.HIGH_ANGLE}:
                factor = width * 0.13
                y = top + scene_h * (0.4 + j * 0.3)
            if close:
                factor = width * (
                    0.6 if shot.shot_type == ShotType.EXTREME_CLOSE_UP else 0.4
                )
                x = width * 0.5
                y = top + scene_h * 0.58
            if not close:
                y += width * 0.14
            state = shot.continuity_state.characters[key]
            if state.transformation:
                for radius in (factor * 1.4, factor * 1.55):
                    d.ellipse(
                        (
                            x - radius,
                            y - factor - radius,
                            x + radius,
                            y - factor + radius,
                        ),
                        outline=colors[key],
                        width=max(2, int(u * 4)),
                    )
            pose = (
                "attack"
                if shot.shot_type
                in {
                    ShotType.IMPACT,
                    ShotType.FINISHER,
                    ShotType.MEDIUM_ACTION,
                    ShotType.POV,
                }
                else (
                    "power"
                    if shot.shot_type in {ShotType.TRANSFORMATION, ShotType.VICTORY}
                    else "guard"
                )
            )
            figure(d, x, y, factor, colors[key], pose, 1 if j == 0 else -1, close)
            name = context.names[key].upper()
            d.text(
                (margin, top + (j * 38 + 20) * u),
                name,
                font=font(round(26 * u)),
                fill=colors[key],
            )
        if shot.shot_type in {ShotType.IMPACT, ShotType.FINISHER}:
            cx, cy = width * 0.62, top + scene_h * 0.5
            for k in range(14):
                angle = k * math.tau / 14
                d.line(
                    (
                        cx + math.cos(angle) * width * 0.12,
                        cy + math.sin(angle) * width * 0.12,
                        cx + math.cos(angle) * width * 0.42,
                        cy + math.sin(angle) * width * 0.42,
                    ),
                    fill=accent,
                    width=max(2, int(3 * u)),
                )
        if (
            "pan" in shot.camera_motion
            or "track" in shot.camera_motion
            or "follow" in shot.camera_motion
        ):
            yy = bottom - 35 * u
            d.line(
                (margin, yy, width - margin, yy), fill=accent, width=max(2, int(3 * u))
            )
            d.polygon(
                [
                    (width - margin, yy),
                    (width - margin - 20 * u, yy - 9 * u),
                    (width - margin - 20 * u, yy + 9 * u),
                ],
                fill=accent,
            )
        # Fixed, generous phone-safe annotation areas. They identify this as previs.
        d.rectangle((0, 0, width, top - 5 * u), fill="#0D1725")
        d.text(
            (margin, height * 0.045),
            "WHO WOULD WIN  /  SHOT LAB",
            font=font(round(27 * u)),
            fill=accent,
        )
        d.text(
            (margin, height * 0.085),
            f"{shot.shot_id.upper()}  ·  {shot.duration_seconds:.2f}s  ·  V{shot.version}",
            font=font(round(30 * u)),
            fill=white,
        )
        d.text(
            (margin, height * 0.12),
            shot.shot_type.value.replace("_", " "),
            font=font(round(43 * u)),
            fill=white,
        )
        d.rectangle((0, bottom + 2 * u, width, height), fill="#0D1725")
        y = wrapped(
            d,
            shot.action_description,
            margin,
            bottom + 30 * u,
            width - 2 * margin,
            size=round(31 * u),
            color=white,
            line_limit=4,
        )
        wrapped(
            d,
            shot.camera_motion.upper(),
            margin,
            max(y + 15 * u, height * 0.875),
            width - 2 * margin,
            size=round(21 * u),
            color=accent,
            line_limit=2,
        )
        d.text(
            (margin, height * 0.935),
            f"SOURCE {shot.simulation_start:.2f}–{shot.simulation_end:.2f}s  /  MOCK • NO GENERATED FOOTAGE",
            font=font(round(17 * u)),
            fill=muted,
        )
        path = context.project / "storyboard" / f"{shot.shot_id}-v{shot.version}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        return StoryboardFrame(
            shot.shot_id,
            path,
            width,
            height,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )


def contact_sheet(frames: list[StoryboardFrame], output: Path, columns=4) -> Path:
    tile_w = 270
    tile_h = round(tile_w * frames[0].height / frames[0].width) + 28
    sheet = Image.new(
        "RGB",
        (columns * tile_w, ((len(frames) + columns - 1) // columns) * tile_h),
        "#101A28",
    )
    d = ImageDraw.Draw(sheet)
    for i, frame in enumerate(frames):
        image = Image.open(frame.path).resize(
            (tile_w, tile_h - 28), Image.Resampling.LANCZOS
        )
        x = i % columns * tile_w
        y = i // columns * tile_h
        sheet.paste(image, (x, y))
        d.text((x + 8, y + tile_h - 23), frame.shot_id, font=font(15), fill="#F4EEE4")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return output
