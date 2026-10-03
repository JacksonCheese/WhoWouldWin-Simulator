"""Flat vector-like identity boards and honest white-model motion animatics.

These are staging references, not synthetic combat outcomes or production footage.
The same simple figure construction is reused in every board and motion clip.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
import math
import subprocess

from PIL import Image, ImageDraw


W, H = 360, 640
ORANGE = (242, 125, 39)
CHARCOAL = (32, 37, 49)
RED = (202, 48, 50)
OFFWHITE = (239, 239, 231)
INK = (17, 25, 39)
BLUE = (70, 192, 249)


@dataclass(frozen=True)
class Pose:
    x: float
    lift: float = 0
    lean: float = 0
    crouch: float = 0
    reach: float = 0
    guard: float = 0.5
    stride: float = 0.25
    orb: float = 0
    down: float = 0
    support: str = "both"


@dataclass(frozen=True)
class Key:
    time: float
    naruto: Pose
    omniman: Pose
    camera_x: float = 180
    zoom: float = 1
    beat: str = ""


def _mix(a: Pose, b: Pose, t: float) -> Pose:
    data = {field.name: (getattr(a, field.name) if t < 0.5 else getattr(b, field.name))
            if field.name == "support" else getattr(a, field.name) + (getattr(b, field.name) - getattr(a, field.name)) * t
            for field in fields(Pose)}
    return Pose(**data)


def interpolate(keys: tuple[Key, ...], time: float) -> tuple[Pose, Pose, float, float, str]:
    if time <= keys[0].time:
        key = keys[0]
        return key.naruto, key.omniman, key.camera_x, key.zoom, key.beat
    if time >= keys[-1].time:
        key = keys[-1]
        return key.naruto, key.omniman, key.camera_x, key.zoom, key.beat
    for left, right in zip(keys, keys[1:]):
        if left.time <= time <= right.time:
            u = (time - left.time) / (right.time - left.time)
            # Smooth support phases and explosive, legible travel between authored keys.
            ease = u * u * (3 - 2 * u)
            beat = right.beat if abs(time - right.time) < 0.13 else ""
            return (_mix(left.naruto, right.naruto, ease), _mix(left.omniman, right.omniman, ease),
                    left.camera_x + (right.camera_x - left.camera_x) * ease,
                    left.zoom + (right.zoom - left.zoom) * ease, beat)
    raise AssertionError("unreachable motion time")


def _world_to_screen(x: float, y: float, camera_x: float, zoom: float) -> tuple[float, float]:
    return ((x - camera_x) * zoom + W / 2, (y - 450) * zoom + 450)


def _ellipse(draw: ImageDraw.ImageDraw, center: tuple[float, float], radii: tuple[float, float], fill, outline=INK, width=2):
    x, y = center
    rx, ry = radii
    draw.ellipse((x - rx, y - ry, x + rx, y + ry), fill=fill, outline=outline, width=width)


def _environment(draw: ImageDraw.ImageDraw, camera_x: float, zoom: float) -> None:
    draw.rectangle((0, 0, W, 640), fill=(39, 66, 113))
    draw.polygon([(0, 0), (0, 435), (75, 435), (75, 130), (50, 130), (50, 90)], fill=(36, 57, 89))
    draw.polygon([(W, 0), (W, 440), (290, 440), (290, 140), (315, 140), (315, 75)], fill=(34, 54, 85))
    draw.rectangle((0, 455, W, H), fill=(48, 66, 88))
    draw.line((0, 455, W, 455), fill=(102, 112, 128), width=3)
    # One repeated landmark and lane marking make the five clips spatially legible.
    stripe_x = 180 + (180 - camera_x) * 0.3
    draw.polygon([(stripe_x - 2, 465), (stripe_x + 2, 465), (stripe_x + 8, H), (stripe_x - 8, H)], fill=(148, 158, 167))
    draw.line((315, 310, 315, 455), fill=(75, 83, 99), width=5)
    draw.line((315, 310, 291, 310), fill=(75, 83, 99), width=5)
    draw.rectangle((280, 305, 298, 312), fill=(230, 182, 99))
    for x in (16, 38, 322, 340):
        for y in (220, 290, 360):
            draw.rectangle((x, y, x + 7, y + 12), fill=(58, 78, 111))


def _figure(draw: ImageDraw.ImageDraw, actor: str, pose: Pose, camera_x: float, zoom: float,
            *, silhouette: bool = False, front: bool = False) -> None:
    facing = 1 if actor == "naruto" else -1
    scale = (1 if actor == "naruto" else 1.17) * zoom
    root_x, root_y = _world_to_screen(pose.x, 520 - pose.lift, camera_x, zoom)
    if pose.down > 0.6:
        body = INK if silhouette else ORANGE if actor == "naruto" else RED
        _ellipse(draw, (root_x, root_y - 15 * scale), (37 * scale, 12 * scale), body)
        _ellipse(draw, (root_x - 40 * scale, root_y - 18 * scale), (13 * scale, 12 * scale),
                 INK if silhouette else (239, 196, 145))
        return
    bend = pose.crouch * 27 * scale
    pelvis = (root_x + pose.lean * 8 * scale, root_y - 67 * scale + bend)
    chest = (root_x + pose.lean * 23 * scale, root_y - 115 * scale + bend)
    head = (chest[0] + pose.lean * 4 * scale, chest[1] - 40 * scale)
    shoulder_half = (21 if actor == "naruto" else 29) * scale
    torso_color = INK if silhouette else CHARCOAL if actor == "naruto" else OFFWHITE
    leg_color = INK if silhouette else ORANGE if actor == "naruto" else RED
    skin = INK if silhouette else (239, 196, 145)
    if actor == "omniman":
        cape = INK if silhouette else (155, 38, 48)
        trail = 72 * scale + pose.lift * 0.23
        draw.polygon([(chest[0] - 16 * scale, chest[1] - 7 * scale),
                      (chest[0] + 18 * scale, chest[1] - 7 * scale),
                      (chest[0] - facing * trail, pelvis[1] + 34 * scale),
                      (chest[0] - facing * (trail + 18 * scale), pelvis[1] + 10 * scale)],
                     fill=cape)
    stride = (20 + pose.stride * 18) * scale
    for direction in (-1, 1):
        if pose.lift > 5:
            foot = (pelvis[0] - facing * (18 + direction * 9) * scale,
                    root_y + (9 + direction * 8) * scale)
        else:
            foot = (root_x + direction * stride, root_y)
        knee = ((pelvis[0] + foot[0]) / 2 + direction * 8 * scale,
                (pelvis[1] + foot[1]) / 2)
        draw.line((pelvis, knee, foot), fill=INK, width=max(4, int(18 * scale)))
        draw.line((pelvis, knee, foot), fill=leg_color, width=max(3, int(14 * scale)))
        if not silhouette:
            shoe = CHARCOAL if actor == "naruto" else OFFWHITE
            _ellipse(draw, (foot[0] + facing * 5 * scale, foot[1]), (12 * scale, 5 * scale), shoe)
        if pose.lift < 5 and pose.support in {"both", "front" if direction == facing else "rear"}:
            draw.ellipse((foot[0] - 13 * scale, foot[1] + 3 * scale,
                          foot[0] + 13 * scale, foot[1] + 7 * scale), fill=(20, 35, 54))
    draw.polygon([(chest[0] - shoulder_half, chest[1] - 4 * scale),
                  (chest[0] + shoulder_half, chest[1] - 4 * scale),
                  (pelvis[0] + 17 * scale, pelvis[1]),
                  (pelvis[0] - 17 * scale, pelvis[1])], fill=torso_color, outline=INK)
    # A continuous neck keeps the graphic head attached in every action pose.
    draw.line((chest[0], chest[1] - 5 * scale, head[0], head[1] + 13 * scale),
              fill=INK if silhouette else skin, width=max(4, int(12 * scale)))
    if not silhouette:
        if actor == "naruto":
            draw.polygon([(pelvis[0] - 16 * scale, pelvis[1] - 30 * scale),
                          (pelvis[0] + 16 * scale, pelvis[1] - 30 * scale),
                          (pelvis[0] + 14 * scale, pelvis[1] - 3 * scale),
                          (pelvis[0] - 14 * scale, pelvis[1] - 3 * scale)], fill=ORANGE)
        else:
            _ellipse(draw, (chest[0], chest[1] + 13 * scale), (17 * scale, 10 * scale), RED, outline=None)
            draw.line((chest[0], chest[1] + 6 * scale, chest[0], pelvis[1]), fill=RED, width=max(2, int(5 * scale)))
    # The far arm stays separate from the torso; the near arm carries attack/ability intent.
    far_shoulder = (chest[0] - facing * shoulder_half, chest[1] + 3 * scale)
    far_hand = (chest[0] - facing * (14 + pose.guard * 3) * scale,
                chest[1] + (13 - pose.guard * 23) * scale)
    far_elbow = (far_shoulder[0] - facing * 10 * scale, far_shoulder[1] + 21 * scale)
    arm_color = INK if silhouette else CHARCOAL if actor == "naruto" else OFFWHITE
    draw.line((far_shoulder, far_elbow, far_hand), fill=INK, width=max(4, int(14 * scale)))
    draw.line((far_shoulder, far_elbow, far_hand), fill=arm_color, width=max(3, int(10 * scale)))
    near_shoulder = (chest[0] + facing * shoulder_half, chest[1] + 3 * scale)
    extension = pose.reach
    if front:
        near_hand = (chest[0] + shoulder_half + 15 * scale,
                     chest[1] + 43 * scale)
    else:
        near_hand = (chest[0] + facing * (15 + 63 * extension) * scale,
                     chest[1] + (18 - 22 * pose.guard + 7 * extension) * scale)
    near_elbow = ((near_shoulder[0] + near_hand[0]) / 2,
                  (near_shoulder[1] + near_hand[1]) / 2 + 14 * scale * (1 - extension))
    draw.line((near_shoulder, near_elbow, near_hand), fill=INK, width=max(4, int(15 * scale)))
    draw.line((near_shoulder, near_elbow, near_hand), fill=arm_color, width=max(3, int(11 * scale)))
    hand_color = INK if silhouette else skin if actor == "naruto" else RED
    _ellipse(draw, near_hand, (6 * scale, 6 * scale), hand_color)
    _ellipse(draw, far_hand, (5 * scale, 5 * scale), hand_color)
    _ellipse(draw, head, (17 * scale, 19 * scale), skin)
    if actor == "naruto":
        hair = INK if silhouette else (247, 209, 70)
        for offset in (-17, -8, 2, 12, 21):
            x = head[0] + offset * scale
            draw.polygon([(x - 8 * scale, head[1] - 12 * scale),
                          (x, head[1] - (31 + (offset % 3) * 3) * scale),
                          (x + 8 * scale, head[1] - 12 * scale)], fill=hair)
        if not silhouette:
            draw.rectangle((head[0] - 17 * scale, head[1] - 11 * scale,
                            head[0] + 17 * scale, head[1] - 3 * scale), fill=CHARCOAL)
            draw.rectangle((head[0] - 7 * scale, head[1] - 11 * scale,
                            head[0] + 7 * scale, head[1] - 3 * scale), fill=(167, 172, 173))
            for side in (-1, 1):
                draw.line((head[0] + side * 8 * scale, head[1] + 6 * scale,
                           head[0] + side * 14 * scale, head[1] + 8 * scale), fill=INK, width=1)
    else:
        hair = INK if silhouette else (25, 27, 34)
        draw.polygon([(head[0] - 17 * scale, head[1] - 5 * scale),
                      (head[0] - 12 * scale, head[1] - 25 * scale),
                      (head[0] + 10 * scale, head[1] - 27 * scale),
                      (head[0] + 18 * scale, head[1] - 5 * scale)], fill=hair)
        if not silhouette:
            draw.line((head[0] - 6 * scale, head[1] + 8 * scale,
                       head[0] + 7 * scale, head[1] + 8 * scale), fill=INK, width=max(2, int(4 * scale)))
    if not silhouette:
        eye_x = head[0] + (0 if front else facing * 7 * scale)
        _ellipse(draw, (eye_x, head[1]), (2 * scale, 2 * scale), INK, outline=None)
    if pose.orb > 0.03 and actor == "naruto" and not silhouette:
        # Hand-attached melee Rasengan: no standalone projectile path is drawn.
        orb = (near_hand[0] + facing * 7 * scale, near_hand[1] - 6 * scale)
        radius = (7 + 10 * pose.orb) * scale
        _ellipse(draw, orb, (radius, radius), BLUE, outline=(213, 243, 253), width=max(1, int(2 * scale)))
        draw.arc((orb[0] - radius * 0.7, orb[1] - radius * 0.7,
                  orb[0] + radius * 0.7, orb[1] + radius * 0.7), 35, 290,
                 fill=(240, 251, 254), width=max(1, int(2 * scale)))


def scene(naruto: Pose, omniman: Pose, camera_x: float = 180, zoom: float = 1,
          *, beat: str = "", size: tuple[int, int] = (W, H)) -> Image.Image:
    image = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(image)
    _environment(draw, camera_x, zoom)
    # The hand-held Rasengan must remain visible in front of the target's edge.
    # Omni-Man's decisive punch is instead drawn on the near layer.
    if naruto.orb > 0.12 and not (omniman.reach > 0.4 and naruto.orb < 0.8):
        _figure(draw, "omniman", omniman, camera_x, zoom)
        _figure(draw, "naruto", naruto, camera_x, zoom)
    else:
        _figure(draw, "naruto", naruto, camera_x, zoom)
        _figure(draw, "omniman", omniman, camera_x, zoom)
    if beat == "projectile miss":
        # A four-bladed wind shuriken travels away from Naruto; never Rasengan.
        x, y = _world_to_screen((naruto.x + omniman.x) * 0.54, 366, camera_x, zoom)
        for angle in (0, 90, 180, 270):
            dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            draw.line((x, y, x + dx * 13, y + dy * 13), fill=(198, 239, 246), width=5)
        _ellipse(draw, (x, y), (4, 4), (55, 170, 218), outline=None)
    elif beat == "energy counter":
        x, y = _world_to_screen((naruto.x + omniman.x) / 2, 370, camera_x, zoom)
        _ellipse(draw, (x, y), (5, 5), BLUE, outline=None)
    if beat == "impact":
        nx, _ = _world_to_screen(naruto.x, 0, camera_x, zoom)
        ox, _ = _world_to_screen(omniman.x, 0, camera_x, zoom)
        x, y = (nx + ox) / 2, 380
        for a in range(0, 360, 45):
            dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a))
            draw.line((x + dx * 8, y + dy * 8, x + dx * 20, y + dy * 20), fill=OFFWHITE, width=2)
    if size != (W, H):
        image = image.resize(size, Image.Resampling.BICUBIC)
    return image


def frame_at(keys: tuple[Key, ...], time: float, *, size=(W, H)) -> Image.Image:
    naruto, omniman, camera_x, zoom, beat = interpolate(keys, time)
    return scene(naruto, omniman, camera_x, zoom, beat=beat, size=size)


def reference_images(folder: Path) -> None:
    """Render exactly twelve flat reference PNGs, with no legacy poster art."""
    folder.mkdir(parents=True, exist_ok=True)
    for actor in ("naruto", "omniman"):
        for view in ("front", "three_quarter", "action_pose", "silhouette"):
            image = Image.new("RGB", (W, H), (232, 235, 229))
            draw = ImageDraw.Draw(image)
            if view == "front":
                pose = Pose(x=180, guard=0, stride=0.18)
            elif view == "three_quarter":
                pose = Pose(x=180, lean=0.2, guard=0.5, stride=0.3)
            elif view == "action_pose":
                pose = Pose(x=180, lift=22 if actor == "omniman" else 0,
                            lean=0.7, crouch=0.25 if actor == "naruto" else 0,
                            reach=0.8, stride=0.65, support="rear")
            else:
                pose = Pose(x=180, guard=0.7, stride=0.35)
            _figure(draw, actor, pose, 180, 1.32, silhouette=view == "silhouette", front=view == "front")
            image.resize((720, 1280), Image.Resampling.BICUBIC).save(folder / f"{actor}_simple_{view}.png")
    scene(Pose(104, guard=0.6), Pose(255, guard=0.7), size=(720, 1280)).save(folder / "simplified_style_reference.png")
    image = Image.new("RGB", (W, H))
    _environment(ImageDraw.Draw(image), 180, 1)
    image.resize((720, 1280), Image.Resampling.BICUBIC).save(folder / "simple_blue_hour_environment.png")
    scene(Pose(123, crouch=0.25, reach=0.4, orb=1, support="rear"),
          Pose(260, guard=0.8), size=(720, 1280)).save(folder / "rasengan_simple_reference.png")
    scene(Pose(105, crouch=0.55, guard=1),
          Pose(223, lift=38, lean=-0.6, reach=0.9, stride=0.8, support="none"),
          size=(720, 1280)).save(folder / "flight_and_impact_simple_reference.png")


def motion_video(keys: tuple[Key, ...], duration: float, output: Path, fps: int = 15) -> dict:
    """Stream authored blockout frames directly into FFmpeg; no render-frame cache."""
    output.parent.mkdir(parents=True, exist_ok=True)
    frames = round(duration * fps)
    command = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pixel_format", "rgb24",
               "-video_size", f"{W}x{H}", "-framerate", str(fps), "-i", "-", "-an",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", str(output)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert process.stdin is not None
        for index in range(frames):
            process.stdin.write(frame_at(keys, index / fps).tobytes())
        process.stdin.close()
        assert process.stderr is not None
        error = process.stderr.read().decode("utf-8", errors="replace")
        if process.wait() != 0:
            raise RuntimeError(f"FFmpeg failed for {output}: {error}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    return {"frame_count": frames, "fps": fps, "duration_seconds": frames / fps,
            "purpose": "schematic motion, spacing, support and camera guidance; not production animation"}
