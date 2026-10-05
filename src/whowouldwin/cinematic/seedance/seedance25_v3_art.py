"""Original, minimal 2D camera/blocking guides for the Seedance v3 edit.

These drawings describe screen direction, bodily intent and motivated cuts. They
are not generated footage or a substitute for reviewing Seedance's actual motion.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import subprocess

from PIL import Image, ImageDraw

from .seedance25_art import Key, Pose, interpolate

W, H = 360, 640
PAPER = (247, 248, 249)
INK = (36, 40, 49)
ORANGE = (245, 128, 39)
ORANGE_SHADE = (220, 94, 32)
BLACK = (40, 45, 52)
RED = (205, 47, 49)
RED_SHADE = (165, 41, 45)
WHITE = (238, 240, 238)
BLUE = (67, 189, 236)
SKIN = (241, 190, 151)


@dataclass(frozen=True)
class CameraCue:
    time: float
    angle: str
    framing: str
    focus: str = "both"


# Cuts occur inside a sequence, not merely between uploads. The left/right
# fighting axis is preserved even when elevation and shot size change.
CAMERAS: dict[int, tuple[CameraCue, ...]] = {
    1: (CameraCue(0, "low", "wide"), CameraCue(1.5, "over_shoulder", "medium", "omniman"), CameraCue(3.5, "low", "medium", "omniman")),
    2: (CameraCue(0, "low", "medium", "omniman"), CameraCue(.15, "side", "medium"), CameraCue(2.75, "three_quarter", "close"), CameraCue(4.1, "high", "medium", "naruto")),
    3: (CameraCue(0, "high", "medium", "naruto"), CameraCue(.15, "side", "medium"), CameraCue(3.45, "low", "medium", "omniman"), CameraCue(4.45, "three_quarter", "close"), CameraCue(5.6, "high", "medium")),
    4: (CameraCue(0, "high", "medium"), CameraCue(2.0, "overhead", "wide"), CameraCue(3.6, "side", "medium"), CameraCue(5.15, "three_quarter", "close", "omniman")),
    5: (CameraCue(0, "three_quarter", "close", "omniman"), CameraCue(.15, "over_shoulder", "medium", "naruto"), CameraCue(1.8, "three_quarter", "medium"), CameraCue(4.35, "three_quarter", "close"), CameraCue(5.55, "side", "medium")),
    6: (CameraCue(0, "side", "medium"), CameraCue(.15, "three_quarter", "medium"), CameraCue(2.0, "high", "medium"), CameraCue(4.75, "side", "medium"), CameraCue(6.05, "low", "close")),
    7: (CameraCue(0, "low", "close"), CameraCue(.15, "low", "medium"), CameraCue(1.0, "overhead", "wide"), CameraCue(3.0, "high", "close", "naruto"), CameraCue(4.85, "three_quarter", "medium")),
    8: (CameraCue(0, "three_quarter", "medium"), CameraCue(.15, "side", "medium"), CameraCue(2.3, "low", "medium"), CameraCue(3.55, "overhead", "wide"), CameraCue(4.9, "three_quarter", "close"), CameraCue(6.05, "over_shoulder", "medium", "omniman")),
    9: (CameraCue(0, "over_shoulder", "medium", "omniman"), CameraCue(.15, "low", "medium"), CameraCue(.85, "three_quarter", "close"), CameraCue(1.85, "high", "medium"), CameraCue(3.0, "overhead", "wide"), CameraCue(4.7, "low", "wide")),
}


def camera_at(sequence_index: int, time: float) -> CameraCue:
    return next(cue for cue in reversed(CAMERAS[sequence_index]) if time >= cue.time)


def _segment(draw: ImageDraw.ImageDraw, a: tuple[float, float], b: tuple[float, float],
             wide: float, narrow: float, fill: tuple[int, int, int],
             shade: tuple[int, int, int]) -> None:
    """A tapered limb mass, with one flat facet rather than outlined stick lines."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = max(1.0, math.hypot(dx, dy))
    nx, ny = -dy / length, dx / length
    poly = [(a[0] + nx * wide, a[1] + ny * wide),
            (b[0] + nx * narrow, b[1] + ny * narrow),
            (b[0] - nx * narrow, b[1] - ny * narrow),
            (a[0] - nx * wide, a[1] - ny * wide)]
    draw.polygon(poly, fill=fill)
    draw.polygon((poly[0], poly[1], b, a), fill=shade)
    if fill == WHITE:
        draw.line((*poly, poly[0]), fill=(184, 189, 193), width=1)


def _circle(draw: ImageDraw.ImageDraw, xy: tuple[float, float], r: float,
            color: tuple[int, int, int]) -> None:
    x, y = xy
    draw.ellipse((x-r, y-r, x+r, y+r), fill=color)


def _background(draw: ImageDraw.ImageDraw, cue: CameraCue) -> None:
    draw.rectangle((0, 0, W, H), fill=PAPER)
    if cue.angle == "overhead":
        draw.ellipse((-140, 150, 500, 530), outline=(225, 229, 234), width=3)
        draw.line((0, 340, W, 340), fill=(219, 225, 231), width=4)
        return
    floor = 500 if cue.angle != "low" else 528
    draw.line((0, floor, W, floor), fill=(215, 220, 225), width=2)
    for offset in (-190, 115, 320):
        x = offset
        draw.line((x, floor + 5, x + 28, H), fill=(232, 235, 238), width=2)
    if cue.angle == "low":
        draw.polygon(((0, floor), (W, floor), (W, H), (0, H)), fill=(240, 242, 244))
        draw.line((0, floor, W, floor), fill=(218, 222, 226), width=2)
    elif cue.angle == "high":
        draw.line((25, 430, 335, 475), fill=(230, 232, 235), width=3)


def _view(cue: CameraCue, naruto: Pose, omniman: Pose) -> tuple[float, float]:
    midpoint = (naruto.x + omniman.x) / 2
    target = naruto.x if cue.focus == "naruto" else omniman.x if cue.focus == "omniman" else midpoint
    # Bias toward both subjects so reaction and contact remain readable on a phone.
    focus = midpoint * .65 + target * .35
    span = max(78, omniman.x - naruto.x)
    if cue.framing == "wide":
        zoom = min(1.16, 248 / span)
    elif cue.framing == "close":
        zoom = min(1.95, 296 / span)
    else:
        zoom = min(1.52, 270 / span)
    return focus, zoom


def _draw_overhead(draw: ImageDraw.ImageDraw, actor: str, pose: Pose,
                   x: float, y: float, s: float, phase: float) -> None:
    facing = 1 if actor == "naruto" else -1
    coat = ORANGE if actor == "naruto" else WHITE
    accent = BLACK if actor == "naruto" else RED
    shoulder = 22 if actor == "naruto" else 28
    draw.ellipse((x-16*s, y-13*s, x+16*s, y+13*s), fill=(218, 221, 223))
    draw.polygon(((x-shoulder*s, y-8*s), (x+shoulder*s, y-8*s),
                  (x+15*s, y+28*s), (x-15*s, y+28*s)), fill=coat)
    draw.line((x, y, x+facing*8*s, y+18*s), fill=accent, width=max(2, round(4*s)))
    _circle(draw, (x, y-12*s), 13*s, SKIN)
    if actor == "naruto":
        for i in (-2,-1,0,1,2):
            draw.polygon(((x+i*6*s-4*s,y-17*s),(x+i*6*s,y-31*s),(x+i*6*s+5*s,y-18*s)), fill=(249,204,64))
    else:
        draw.polygon(((x-15*s,y-18*s),(x-11*s,y-28*s),(x+12*s,y-28*s),(x+16*s,y-17*s)), fill=BLACK)
        draw.polygon(((x+16*s,y-6*s),(x+facing*55*s,y+10*s),(x+25*s,y+39*s)), fill=RED_SHADE)
    extent = (28 + pose.reach*38)*s
    hand = (x+facing*extent, y-3*s-5*math.sin(phase)*s)
    elbow = (x+facing*(shoulder+18)*s, y+10*s)
    _segment(draw,(x+facing*shoulder*s,y),elbow,9*s,7*s,coat,accent)
    _segment(draw,elbow,hand,7*s,5*s,coat,accent)
    _circle(draw,hand,5*s,SKIN if actor=="naruto" else RED)
    other=(x-facing*34*s,y+4*s)
    _segment(draw,(x-facing*shoulder*s,y),other,8*s,5*s,coat,accent)
    _circle(draw,other,5*s,SKIN if actor=="naruto" else RED)
    if actor == "naruto" and pose.orb > .1:
        _circle(draw,(hand[0]+facing*8*s,hand[1]),(6+6*pose.orb)*s,BLUE)


def _foreground_shoulder(draw: ImageDraw.ImageDraw, actor: str) -> None:
    """A large cropped foreground silhouette makes OTS a different viewpoint."""
    if actor == "naruto":
        draw.polygon(((-35, 403), (32, 372), (95, 420), (122, 640), (-35, 640)), fill=BLACK)
        draw.polygon(((-35, 472), (45, 464), (92, 514), (122, 640), (-35, 640)), fill=ORANGE)
        _circle(draw,(14,365),32,SKIN)
        for spike in range(-2,3):
            x=15+spike*15
            draw.polygon(((x-12,347),(x,306-abs(spike)*5),(x+13,348)),fill=(249,204,65))
        draw.rectangle((-16,341,44,354),fill=BLACK)
    else:
        draw.polygon(((375,405),(302,381),(271,463),(250,640),(390,640)),fill=WHITE)
        draw.polygon(((359,410),(305,394),(293,460),(251,640),(390,640)),fill=RED)
        _circle(draw,(346,353),35,SKIN)
        draw.polygon(((313,340),(325,310),(363,309),(376,337)),fill=BLACK)
        draw.line((335,370,361,370),fill=BLACK,width=6)
        draw.polygon(((317,390),(355,406),(400,455),(396,640),(330,640)),fill=RED_SHADE)


def _figure(draw: ImageDraw.ImageDraw, actor: str, pose: Pose, cue: CameraCue,
            focus: float, zoom: float, time: float) -> None:
    facing = 1 if actor == "naruto" else -1
    scale = zoom * (.98 if actor == "naruto" else 1.18)
    x = W/2+(pose.x-focus)*zoom
    ground = 510 if cue.angle != "low" else 536
    y = ground-pose.lift*zoom
    # Derive secondary articulation from the authored pose so two sequence
    # boundaries render the exact same image despite their local clock reset.
    phase = pose.x*.09+pose.reach*1.8+(0 if actor=="naruto" else 1.7)
    if cue.angle == "overhead":
        _draw_overhead(draw,actor,pose,x,310+(pose.x-focus)*.15,scale,phase)
        return
    if pose.down > .75:
        draw.ellipse((x-43*scale,y-12*scale,x+43*scale,y+11*scale),fill=ORANGE if actor=="naruto" else RED)
        _circle(draw,(x-38*scale,y-6*scale),11*scale,SKIN)
        return
    shortening=.77 if cue.angle=="high" else 1.08 if cue.angle=="low" else 1
    crouch=pose.crouch*28*scale
    pelvis=(x+pose.lean*8*scale,y-62*scale*shortening+crouch)
    chest=(x+pose.lean*26*scale,y-112*scale*shortening+crouch)
    neck=(chest[0]+pose.lean*3*scale,chest[1]-14*scale)
    head=(neck[0],neck[1]-22*scale)
    shoulder=(22 if actor=="naruto" else 30)*scale
    waist=(14 if actor=="naruto" else 20)*scale
    near=chest[0]+facing*shoulder
    far=chest[0]-facing*shoulder
    leg_color=ORANGE if actor=="naruto" else RED
    leg_shade=ORANGE_SHADE if actor=="naruto" else RED_SHADE
    torso=BLACK if actor=="naruto" else WHITE
    sleeve=BLACK if actor=="naruto" else WHITE
    sleeve_shade=(58,62,70) if actor=="naruto" else (210,215,217)
    # The leg phase changes only during travel/release; support remains legible.
    stride=(19+pose.stride*15)*scale
    for side in (-1,1):
        footx=x+side*stride
        release=pose.support not in ("both", "front" if side==facing else "rear")
        footy=y-(4+5*abs(math.sin(phase)))*scale if release else y
        if pose.lift>6:
            footy=y+(side*8)*scale
            footx=x-facing*(18+side*8)*scale
        foot=(footx,footy)
        knee=(pelvis[0]+(footx-pelvis[0])*.52+side*8*scale,
              pelvis[1]+(footy-pelvis[1])*.53-4*scale)
        _segment(draw,(pelvis[0]+side*waist*.48,pelvis[1]),knee,11*scale,8*scale,leg_color,leg_shade)
        _segment(draw,knee,foot,8*scale,5*scale,leg_color,leg_shade)
        draw.ellipse((footx-11*scale,footy-4*scale,footx+12*scale,footy+5*scale),fill=BLACK if actor=="naruto" else WHITE)
        if not release and pose.lift<6:
            draw.ellipse((footx-11*scale,footy+4*scale,footx+14*scale,footy+7*scale),fill=(198,203,210))
    if actor=="omniman":
        trail=(50+min(35,pose.lift*.55))*scale
        draw.polygon(((far-4*scale,chest[1]-5*scale),(near+3*scale,chest[1]-5*scale),
                      (x-facing*trail,pelvis[1]+33*scale),(x-facing*(trail+12*scale),pelvis[1]+9*scale)),fill=RED_SHADE)
        draw.polygon(((near,chest[1]),(x-facing*trail,pelvis[1]+33*scale),
                      (x-facing*(trail-13*scale),pelvis[1]+12*scale)),fill=RED)
    # Far arm is visible, bent into a distinct guard rather than disappearing.
    far_shoulder=(far,chest[1]+3*scale)
    far_elbow=(far-facing*(13+5*pose.guard)*scale,chest[1]+26*scale)
    far_hand=(chest[0]-facing*(15+pose.guard*8)*scale,chest[1]+(16-29*pose.guard)*scale)
    _segment(draw,far_shoulder,far_elbow,10*scale,7*scale,sleeve,sleeve_shade)
    _segment(draw,far_elbow,far_hand,7*scale,5*scale,sleeve,sleeve_shade)
    _circle(draw,far_hand,6*scale,SKIN if actor=="naruto" else RED)
    draw.polygon(((far,chest[1]-9*scale),(near,chest[1]-9*scale),
                  (pelvis[0]+waist,pelvis[1]),(pelvis[0]-waist,pelvis[1])),
                 fill=torso,outline=(184,189,193) if actor=="omniman" else None)
    draw.polygon(((chest[0],chest[1]-8*scale),(near,chest[1]-8*scale),
                  (pelvis[0]+waist,pelvis[1]),(pelvis[0]+4*scale,pelvis[1])),
                 fill=sleeve_shade if actor=="naruto" else (219,222,223))
    if actor=="naruto":
        draw.polygon(((pelvis[0]-waist,pelvis[1]-27*scale),(pelvis[0]+waist,pelvis[1]-27*scale),
                      (pelvis[0]+waist,pelvis[1])),fill=ORANGE)
    else:
        draw.ellipse((chest[0]-16*scale,chest[1]+4*scale,chest[0]+16*scale,chest[1]+23*scale),fill=RED)
        draw.line((chest[0],chest[1]+13*scale,pelvis[0],pelvis[1]),fill=RED,width=max(2,round(4*scale)))
    _segment(draw,(chest[0],chest[1]-7*scale),neck,7*scale,5*scale,SKIN,SKIN)
    near_shoulder=(near,chest[1]+3*scale)
    reach=pose.reach
    hand=(chest[0]+facing*(18+59*reach)*scale,
          chest[1]+(14-23*pose.guard+8*reach+5*math.sin(phase)*reach)*scale)
    elbow=(near_shoulder[0]+(hand[0]-near_shoulder[0])*.52,
           near_shoulder[1]+(hand[1]-near_shoulder[1])*.47+(16-12*reach)*scale)
    _segment(draw,near_shoulder,elbow,11*scale,8*scale,sleeve,sleeve_shade)
    _segment(draw,elbow,hand,8*scale,5.5*scale,sleeve,sleeve_shade)
    _circle(draw,hand,6*scale,SKIN if actor=="naruto" else RED)
    _circle(draw,head,16*scale,SKIN)
    if actor=="naruto":
        for i in (-2,-1,0,1,2):
            hx=head[0]+i*7*scale
            draw.polygon(((hx-7*scale,head[1]-10*scale),(hx,head[1]-(24+abs(i)*3)*scale),
                          (hx+8*scale,head[1]-10*scale)),fill=(249,204,65))
        draw.rectangle((head[0]-15*scale,head[1]-11*scale,head[0]+15*scale,head[1]-4*scale),fill=BLACK)
        draw.rectangle((head[0]-6*scale,head[1]-11*scale,head[0]+6*scale,head[1]-4*scale),fill=(180,183,182))
        for side in (-1,1):
            draw.line((head[0]+side*7*scale,head[1]+7*scale,
                       head[0]+side*13*scale,head[1]+8*scale),fill=ORANGE_SHADE,width=max(1,round(scale)))
    else:
        draw.polygon(((head[0]-17*scale,head[1]-5*scale),(head[0]-12*scale,head[1]-24*scale),
                      (head[0]+10*scale,head[1]-25*scale),(head[0]+17*scale,head[1]-4*scale)),fill=BLACK)
        draw.line((head[0]-6*scale,head[1]+8*scale,head[0]+7*scale,head[1]+8*scale),fill=BLACK,width=max(2,round(3*scale)))
    # Facial marks remain minimal; expression comes from brows and the pose.
    if cue.angle!="side":
        for side in (-1,1):
            ex=head[0]+side*6*scale
            _circle(draw,(ex,head[1]),1.5*scale,INK)
            draw.line((ex-3*scale,head[1]-4*scale,ex+3*scale,head[1]-5*scale),fill=INK,width=max(1,round(scale)))
    else:
        _circle(draw,(head[0]+facing*7*scale,head[1]),1.7*scale,INK)
    if actor=="naruto" and pose.orb>.05:
        orb=(hand[0]+facing*9*scale,hand[1]-4*scale)
        radius=(5+9*pose.orb)*scale
        draw.ellipse((orb[0]-radius,orb[1]-radius,orb[0]+radius,orb[1]+radius),
                     fill=BLUE,outline=(185,229,243),width=max(1,round(2*scale)))
        draw.arc((orb[0]-radius*.7,orb[1]-radius*.7,orb[0]+radius*.7,orb[1]+radius*.7),20,285,
                 fill=PAPER,width=max(1,round(2*scale)))


def frame_at(keys: tuple[Key, ...], sequence_index: int, time: float,
             *, size: tuple[int,int]=(W,H)) -> Image.Image:
    naruto, omniman, _, _, beat = interpolate(keys,time)
    cue=camera_at(sequence_index,time)
    focus,zoom=_view(cue,naruto,omniman)
    image=Image.new("RGB",(W,H),PAPER)
    draw=ImageDraw.Draw(image)
    _background(draw,cue)
    before=interpolate(keys,max(0,time-.1))
    after=interpolate(keys,min(keys[-1].time,time+.1))
    for index, pose in enumerate((naruto,omniman)):
        speed=(after[index].x-before[index].x)/max(.01,min(keys[-1].time,time+.1)-max(0,time-.1))
        if 0 < time < keys[-1].time and abs(speed)>14:
            px=W/2+(pose.x-focus)*zoom
            direction=1 if speed>0 else -1
            py=394 if cue.angle!="overhead" else 310
            for offset in (-21,0,21):
                draw.line((px-direction*29,py+offset,px-direction*min(105,28+abs(speed)*.6),py+offset-4),
                          fill=(218,224,230),width=2)
    if beat in ("projectile miss","energy counter","projectile hit"):
        px=W/2+(naruto.x+(omniman.x-naruto.x)*.55-focus)*zoom
        py=341 if cue.angle!="overhead" else 305
        if beat=="projectile miss":
            for a in range(0,360,90):
                dx,dy=math.cos(math.radians(a)),math.sin(math.radians(a))
                draw.line((px,py,px+dx*15,py+dy*15),fill=(104,190,213),width=4)
        else:
            _circle(draw,(px,py),4,BLUE)
    # Order changes at close contact to keep both the Rasengan and decisive fist visible.
    if cue.angle == "over_shoulder":
        target = cue.focus if cue.focus in ("naruto", "omniman") else "omniman"
        foreground = "naruto" if target == "omniman" else "omniman"
        _figure(draw,target,naruto if target=="naruto" else omniman,cue,focus,zoom,time)
        _foreground_shoulder(draw,foreground)
    else:
        order=("omniman","naruto") if naruto.orb>.2 and omniman.reach<.45 else ("naruto","omniman")
        for actor in order:
            _figure(draw,actor,naruto if actor=="naruto" else omniman,cue,focus,zoom,time)
    if beat=="impact":
        cx=W/2+(naruto.x+(omniman.x-naruto.x)*.48-focus)*zoom
        cy=340 if cue.angle!="overhead" else 310
        for a in range(0,360,60):
            dx,dy=math.cos(math.radians(a)),math.sin(math.radians(a))
            draw.line((cx+dx*9,cy+dy*9,cx+dx*19,cy+dy*19),fill=(148,155,161),width=2)
    if size!=(W,H):
        image=image.resize(size,Image.Resampling.BICUBIC)
    return image


def motion_video(keys: tuple[Key,...], sequence_index: int, duration: float,
                 output: Path, *, fps: int=15) -> dict:
    output.parent.mkdir(parents=True,exist_ok=True)
    frames=round(duration*fps)
    command=["ffmpeg","-loglevel","error","-y","-f","rawvideo","-pixel_format","rgb24",
             "-video_size",f"{W}x{H}","-framerate",str(fps),"-i","-","-an",
             "-c:v","libx264","-preset","veryfast","-crf","22","-pix_fmt","yuv420p",str(output)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        assert process.stdin is not None
        for index in range(frames):
            process.stdin.write(frame_at(keys,sequence_index,index/fps).tobytes())
        process.stdin.close()
        assert process.stderr is not None
        error=process.stderr.read().decode("utf-8",errors="replace")
        if process.wait()!=0:
            raise RuntimeError(f"FFmpeg failed: {error}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    return {"frame_count":frames,"fps":fps,"duration_seconds":frames/fps,
            "purpose":"original flat-anatomy blocking, movement and multi-angle cut guide only",
            "camera_cues":[cue.__dict__ for cue in CAMERAS[sequence_index]]}
