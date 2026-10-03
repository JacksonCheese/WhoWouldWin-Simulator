"""Five-sequence Dreamina Seedance 2.5 package from canonical seed-289 events.

The twenty-eight-shot editorial plan stays internal. Upload assets are twelve
flat identity/style references, two boundary frames, and one white-model motion
reference per sequence. No video provider is called by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

from PIL import Image, ImageDraw

from whowouldwin.simulation.replay import load_replay
from .longform_seed289 import EVENT_SHA, SOURCE_CHECKSUM, build_plan
from .package import write_json
from .seedance25_art import Key, Pose, frame_at, motion_video, reference_images


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT = ROOT / "outputs/seedance_ready/naruto_vs_omniman_seedance25"
SOURCE = ROOT / "assets/seedance/seed289_60s/source_replay.json"
SHARED_NAMES = (
    "naruto_simple_front.png", "naruto_simple_three_quarter.png",
    "naruto_simple_action_pose.png", "naruto_simple_silhouette.png",
    "omniman_simple_front.png", "omniman_simple_three_quarter.png",
    "omniman_simple_action_pose.png", "omniman_simple_silhouette.png",
    "simplified_style_reference.png", "simple_blue_hour_environment.png",
    "rasengan_simple_reference.png", "flight_and_impact_simple_reference.png",
)
COMMON_NEGATIVE = (
    "No detailed comic shading, photorealism, realistic skin, fabric texture, poster poses, complex faces, "
    "cluttered city, gliding, skating, floating feet, random teleportation, flailing arms, rubber limbs, "
    "folded torso, tangled hands, missing or duplicated limbs, frozen bodies under a moving camera, "
    "overblown glow, hidden contact, new damage, altered winner, design drift, axis reversal, "
    "subtitles, logos, text copied from the motion guide, or thrown Rasengan. "
    "The Rasengan is a hand-held melee attack and never becomes a projectile."
)


@dataclass(frozen=True)
class Sequence:
    index: int
    name: str
    shot_first: int
    shot_last: int
    duration: int
    keys: tuple[Key, ...]
    identity_refs: tuple[str, str, str, str]
    ability_ref: str | None
    timeline: tuple[str, ...]
    camera: str
    ability: str
    transition: str


N0, O0 = Pose(104, guard=.65, support="both"), Pose(260, guard=.7, support="both")
N1, O1 = Pose(98, guard=.9, crouch=.2, support="both"), Pose(179, lift=28, lean=-.5, reach=.2, support="none")
N2, O2 = Pose(98, guard=.7, crouch=.25, support="both"), Pose(230, guard=.75, support="both")
N3, O3 = Pose(105, guard=.7, support="both"), Pose(228, guard=.7, support="both")
N4, O4 = Pose(124, crouch=.2, reach=.35, orb=1, support="rear"), Pose(220, guard=.45, reach=.15, support="both")
N5, O5 = Pose(75, down=1, support="none"), Pose(250, guard=.4, support="both")


SEQUENCES = (
    Sequence(1, "Faceoff, tension and initial charge", 1, 6, 14,
             (Key(0, N0, O0, zoom=.90, beat="faceoff"),
              Key(2, Pose(104, crouch=.2, guard=.8, support="rear"), Pose(260, crouch=.2, guard=.65, support="rear"), zoom=.94, beat="load"),
              Key(5, Pose(89, crouch=.5, guard=.85, support="front"), Pose(260, crouch=.25, lean=-.3, support="rear"), zoom=.99, beat="blink outside"),
              Key(8, Pose(96, guard=.9, support="both"), Pose(260, crouch=.5, lean=-.45, reach=.25, support="rear"), zoom=1.04, beat="flight load"),
              Key(11, Pose(98, guard=.9, support="both"), Pose(232, lift=36, lean=-.7, reach=.65, support="none"), camera_x=169, zoom=1.06, beat="takeoff"),
              Key(12.8, Pose(98, guard=.9, crouch=.2, support="both"), Pose(183, lift=32, lean=-.55, reach=.2, support="none"), camera_x=166, zoom=1.05, beat="flight blitz"),
              Key(14, N1, O1, camera_x=166, zoom=1.05, beat="charge approach")),
             ("naruto_simple_front.png", "naruto_simple_three_quarter.png", "omniman_simple_front.png", "omniman_simple_action_pose.png"),
             "flight_and_impact_simple_reference.png",
             ("0–4 seconds: A low wide confrontation; Naruto loads a rear foot while Omni-Man coils through his legs and shoulders.",
              "4–9 seconds: Naruto blinks to the outside lane as recorded; keep the shifted support foot visible. Omni-Man plants and gathers force.",
              "9–14 seconds: Omni-Man's cape lags as he accelerates right-to-left in flight. Track his path, ending before contact with a visible gap."),
             "Begin wide and low, creep into Naruto's read, then pan late behind Omni-Man's flight path; remain south of the action axis.",
             "Only the recorded blink and flight charge begin; no extra hit in this sequence.",
             "End on Omni-Man airborne one body-length from Naruto; the next sequence starts at this exact spacing."),
    Sequence(2, "Opening attack, evasion and grounded recovery", 7, 10, 9,
             (Key(0, N1, O1, camera_x=166, zoom=1.05, beat="approach"),
              Key(1.2, Pose(92, crouch=.55, lean=-.5, guard=1, support="rear"), Pose(145, lift=12, lean=-.7, reach=.9, support="none"), camera_x=155, zoom=1.13, beat="impact"),
              Key(2.5, Pose(69, crouch=.7, lean=-.25, guard=.8, support="front"), Pose(177, lift=25, reach=.2, support="none"), camera_x=145, zoom=1.02, beat="grounded catch"),
              Key(4.5, Pose(78, crouch=.25, reach=.9, stride=.6, support="rear"), Pose(223, lift=4, guard=.7, support="both"), camera_x=158, zoom=.98, beat="projectile miss"),
              Key(6, Pose(83, guard=.75, support="both"), Pose(205, crouch=.2, guard=.6, support="rear"), zoom=1.03, beat="heavy load"),
              Key(7.3, Pose(91, crouch=.5, lean=-.5, guard=1, support="rear"), Pose(143, lean=-.6, reach=1, stride=.8, support="front"), camera_x=150, zoom=1.12, beat="impact"),
              Key(9, N2, O2, zoom=.98, beat="separate")),
             ("naruto_simple_action_pose.png", "naruto_simple_silhouette.png", "omniman_simple_action_pose.png", "omniman_simple_silhouette.png"),
             "flight_and_impact_simple_reference.png",
             ("0–3 seconds: The recorded flying shoulder touches Naruto once. Naruto compresses, slides into a bent-knee catch, plants, and recovers; Omni-Man brakes in air.",
              "3–6 seconds: Naruto drives from his rear foot and throws the recorded four-bladed wind shuriken; it visibly misses Omni-Man. Keep it distinct from Rasengan.",
              "6–9 seconds: Omni-Man lands and rotates hip, chest, then shoulder into one recorded heavy strike. Naruto's guard and torso take the hit, then both regain spacing."),
             "Switch from a medium side attack lane to a grounded catch angle and back to a three-quarter impact; show contact before any camera kick.",
             "Charged-vortex projectile resembles a small four-bladed Rasenshuriken and misses. It is not a thrown Rasengan.",
             "End with Naruto staggered but planted on the left and Omni-Man reset on the right."),
    Sequence(3, "Close exchange, counter and repositioning", 11, 18, 18,
             (Key(0, N2, O2, zoom=.98, beat="reset"),
              Key(2, Pose(98, crouch=.35, guard=.8, support="both"), Pose(225, guard=.6, support="both"), zoom=1.04, beat="chakra surge"),
              Key(4, Pose(78, crouch=.6, lean=-.7, guard=.8, support="front"), Pose(179, reach=1, stride=.6, support="rear"), camera_x=156, zoom=1.08, beat="jab miss"),
              Key(6, Pose(91, reach=.9, stride=.4, support="rear"), Pose(213, crouch=.3, lean=-.4, guard=.4, support="both"), zoom=1.03, beat="energy counter"),
              Key(8, Pose(112, crouch=.3, guard=.9, support="rear"), Pose(169, reach=.8, stride=.6, support="front"), camera_x=151, zoom=1.08, beat="grapple"),
              Key(10, Pose(104, crouch=.35, lean=-.4, guard=.8, support="front"), Pose(185, reach=.15, guard=.7, support="both"), zoom=1.02, beat="pivot"),
              Key(12, Pose(110, crouch=.5, guard=1, support="both"), Pose(157, lean=-.55, reach=1, support="rear"), camera_x=153, zoom=1.12, beat="impact"),
              Key(14, Pose(88, crouch=.6, guard=.8, support="front"), Pose(190, guard=.7, support="both"), zoom=1.01, beat="guard recoil"),
              Key(16, Pose(80, crouch=.6, lean=-.5, guard=.8, support="front"), Pose(180, reach=.85, support="rear"), zoom=1.06, beat="narrow dodge"),
              Key(18, N3, O3, zoom=.98, beat="outside lane")),
             ("naruto_simple_action_pose.png", "naruto_simple_silhouette.png", "omniman_simple_action_pose.png", "omniman_simple_silhouette.png"),
             None,
             ("0–5 seconds: Naruto's recorded chakra surge tightens his stance. Omni-Man jabs; Naruto releases his trailing heel and slips outside the fist's line.",
              "5–10 seconds: Naruto plants and fires one tiny straight cyan Energy Orb projectile, which hits Omni-Man. Omni-Man then closes and grips Naruto's upper arm; Naruto braces and pivots out.",
              "10–14 seconds: Omni-Man's heavy strike meets Naruto's planted bent forearm. Show physical redirection and guarded compression, not a second clean knockout.",
              "14–18 seconds: Naruto's guard recoils, then he narrowly dodges a jab and regains outside space. Both hands retract and feet reset."),
             "Alternate over-shoulder, high repositioning and steady medium contact views; never cross the established screen-left Naruto/screen-right Omni-Man axis.",
             "The Energy Orb is a simple straight ranged pellet with no swirl. No Rasengan appears here; the recorded grapple and block remain distinct.",
             "End with both separated and grounded, Naruto left and Omni-Man right, ready for the second charge."),
    Sequence(4, "Second charge and failed Rasengan entry", 19, 25, 15,
             (Key(0, N3, O3, zoom=.98, beat="setup"),
              Key(2, Pose(98, guard=.9, support="both"), Pose(190, lift=25, lean=-.6, reach=.6, support="none"), camera_x=160, zoom=1.04, beat="charge launch"),
              Key(4, Pose(80, crouch=.65, lean=-.6, guard=1, support="rear"), Pose(137, lift=10, lean=-.65, reach=.9, support="none"), camera_x=153, zoom=1.11, beat="impact"),
              Key(6, Pose(83, crouch=.65, guard=.8, support="front"), Pose(211, lift=15, guard=.6, support="none"), zoom=1.0, beat="grounded catch"),
              Key(8, Pose(100, crouch=.4, guard=.5, orb=.25, support="rear"), Pose(220, guard=.7, support="both"), zoom=1.05, beat="hand preparation"),
              Key(10, Pose(108, crouch=.25, reach=.25, orb=1, support="both"), Pose(222, guard=.65, support="both"), zoom=1.12, beat="Rasengan formed"),
              Key(12, Pose(130, crouch=.28, reach=.35, orb=1, stride=.65, support="rear"), Pose(222, guard=.6, support="rear"), camera_x=171, zoom=1.06, beat="melee entry"),
              Key(15, N4, O4, camera_x=177, zoom=1.09, beat="near miss")),
             ("naruto_simple_front.png", "naruto_simple_action_pose.png", "omniman_simple_front.png", "omniman_simple_action_pose.png"),
             "rasengan_simple_reference.png",
             ("0–5 seconds: Omni-Man banks into the recorded second flight charge and touches Naruto's guard. Naruto compresses and recoils toward the curb.",
              "5–10 seconds: Naruto catches on a bent support leg, creates distance, stabilizes, and gathers a compact rotating blue Rasengan in his open palm.",
              "10–15 seconds: This authorized editorial attempt is noncanonical and non-damaging. Naruto pushes off and enters for a hand-held melee strike. Omni-Man reads it and shifts just outside the hand path; the orb stops short without touching him."),
             "Use a side tracking shot for the charge, a grounded catch view, then a high three-quarter hand close-up and medium entry. Keep the south-side action axis.",
             "Rasengan remains attached to Naruto's palm throughout; no throw, detached blue orb, projectile, impact or damage to Omni-Man.",
             "End on a clear near-contact gap with Naruto's orb in his hand and Omni-Man's right fist loading for the recorded reply."),
    Sequence(5, "Final heavy strike, fall and aftermath", 26, 28, 6,
             (Key(0, N4, O4, camera_x=177, zoom=1.09, beat="intercept"),
              Key(1.4, Pose(138, crouch=.55, lean=-.55, guard=.15, orb=.55, support="rear"),
                  Pose(205, lean=-.65, reach=.5, stride=.8, support="rear"), camera_x=166, zoom=1.14, beat="impact"),
              Key(2.2, Pose(113, crouch=.72, lean=-.8, guard=.2, orb=0, support="rear"),
                  Pose(204, reach=.85, guard=.1, support="front"), camera_x=164, zoom=1.12, beat="KO recoil"),
              Key(4, Pose(78, down=.85, support="none"), Pose(226, reach=.2, guard=.3, support="both"), zoom=1.0, beat="fall"),
              Key(6, N5, O5, zoom=.88, beat="recorded aftermath")),
             ("naruto_simple_action_pose.png", "naruto_simple_silhouette.png", "omniman_simple_action_pose.png", "omniman_simple_silhouette.png"),
             "rasengan_simple_reference.png",
             ("0–2 seconds: Omni-Man's right foot, hip, chest and shoulder drive his recorded heavy fist into Naruto's upper torso. Show surface contact before one brief graphic impact accent. Naruto's hand-held Rasengan collapses harmlessly; it never hits.",
              "2–4 seconds: Naruto's torso compresses and recoils as the recorded KO occurs. Omni-Man follows through then retracts; Naruto loses leg support and falls.",
              "4–6 seconds: Hold a wide quiet aftermath: Naruto down on the left, Omni-Man upright breathing on the right, no extra attack or Naruto recovery."),
             "Use one clear low three-quarter contact insert, follow Naruto downward without hiding the fist, then widen to street scale and stop moving.",
             "The heavy strike is the decisive recorded KO. The unused Rasengan stays in Naruto's hand until it dissipates without contact.",
             "Clean hold to end; no following sequence or extra winner beat."),
)


def _json_pose(pose: Pose) -> dict:
    return {name: getattr(pose, name) for name in pose.__dataclass_fields__}


def _state(key: Key) -> dict:
    return {"naruto": _json_pose(key.naruto), "omniman": _json_pose(key.omniman),
            "camera_x": key.camera_x, "zoom": key.zoom,
            "screen_lanes": {"naruto": "left", "omniman": "right"},
            "arena": "same flat blue-hour street, center road stripe, left curb, right streetlight",
            "lighting": "soft screen-left key; no complex cinematic relighting"}


def _prompt(sequence: Sequence) -> str:
    start, end = _state(sequence.keys[0]), _state(sequence.keys[-1])
    rows = [f"Dreamina Seedance 2.5, vertical 9:16, {sequence.duration} seconds. {sequence.name}.",
            "Reference hierarchy: the two character boards for each fighter define identity and proportions; "
            "the style and environment boards define flat color and street landmarks; start/end frames define blocking; "
            "motion_reference.mp4 controls paths, support-foot phases, timing and camera beats. Do not copy any guide marks into the final video.",
            f"Start state: Naruto x={start['naruto']['x']:.0f} on screen left; Omni-Man x={start['omniman']['x']:.0f} on screen right. "
            f"End state: Naruto x={end['naruto']['x']:.0f} left; Omni-Man x={end['omniman']['x']:.0f} right. "
            "Keep one south-side action axis and the same center stripe, left curb and right streetlight.",
            *sequence.timeline,
            "Movement: visible foot loading, heel release, planted catch, pelvis-to-chest-to-shoulder acceleration, curved hand paths, "
            "clear contact or miss, torso compression, and asymmetric recovery. Motion comes from bodies, not camera-only movement.",
            f"Camera and shot sizes: {sequence.camera}",
            "Lighting and look: sparse blue-hour background, stable screen-left soft key, flat orange/charcoal Naruto and broad red/off-white caped Omni-Man, "
            "simple heads, clear hands and feet, bold outlines, very little internal shading.",
            f"Ability behavior: {sequence.ability}",
            f"Transition: {sequence.transition}",
            "Recorded winner remains Omni-Man by heavy strike; the hand-held failed Rasengan attempt is editorial staging only and changes no combat event or damage."]
    return "\n\n".join(rows) + "\n"


def _negative(sequence: Sequence) -> str:
    extra = (" No Rasengan before its preparation sequence." if sequence.index < 4 else
             " No detached Rasengan orb or Rasengan contact; no energy blast from Naruto's hand-held Rasengan.")
    return COMMON_NEGATIVE + extra + "\n"


def _ffprobe(path: Path) -> dict:
    data = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height,avg_frame_rate,nb_frames", "-show_entries", "format=duration", "-of", "json", str(path),
    ], text=True))
    stream = data["streams"][0]
    return {"width": stream["width"], "height": stream["height"],
            "fps": stream["avg_frame_rate"], "frame_count": int(stream.get("nb_frames", 0)),
            "duration_seconds": float(data["format"]["duration"])}


def build(output: Path = DEFAULT_OUTPUT, *, fps: int = 15) -> tuple[Path, dict]:
    """Build a new directory; never overwrite the validated 28-shot package."""
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Refusing to overwrite existing Seedance 2.5 package: {output}")
    if fps < 3 or fps > 30:
        raise ValueError("Motion-reference FPS must be between 3 and 30")
    replay = load_replay(SOURCE)
    plan, beats = build_plan(replay)
    output.mkdir(parents=True, exist_ok=True)
    shared = output / "shared_references"
    reference_images(shared)
    if {p.name for p in shared.glob("*.png")} != set(SHARED_NAMES):
        raise ValueError("Shared reference set must contain exactly twelve images")
    internal = output / "internal"
    internal.mkdir(exist_ok=True)
    shutil.copyfile(SOURCE, internal / "source_replay.json")
    write_json(internal / "episode_plan_28_shots.json", plan)
    write_json(internal / "fight_beats.json", beats)
    write_json(internal / "sequence_shot_map.json", [
        {"sequence": s.index, "source_shots": [f"shot_{i:03d}" for i in range(s.shot_first, s.shot_last + 1)],
         "source_editorial_seconds": sum(plan.shots[i - 1].duration_seconds for i in range(s.shot_first, s.shot_last + 1)),
         "target_generation_seconds": s.duration} for s in SEQUENCES])
    refs = output / "motion_refs"
    refs.mkdir(exist_ok=True)
    for seq in SEQUENCES:
        folder = output / "sequences" / f"sequence_{seq.index:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        frame_at(seq.keys, 0, size=(720, 1280)).save(folder / "start_frame.png")
        frame_at(seq.keys, seq.duration, size=(720, 1280)).save(folder / "end_frame.png")
        filename = ["motion_ref_01_faceoff_and_charge.mp4", "motion_ref_02_opening_attack_and_evasion.mp4",
                    "motion_ref_03_close_exchange.mp4", "motion_ref_04_ability_preparation.mp4",
                    "motion_ref_05_final_clash_and_aftermath.mp4"][seq.index - 1]
        motion_metadata = motion_video(seq.keys, seq.duration, refs / filename, fps=fps)
        shutil.copyfile(refs / filename, folder / "motion_reference.mp4")
        (folder / "sequence_prompt.txt").write_text(_prompt(seq), encoding="utf-8")
        (folder / "sequence_negative_prompt.txt").write_text(_negative(seq), encoding="utf-8")
        write_json(folder / "continuity_start.json", _state(seq.keys[0]))
        write_json(folder / "continuity_end.json", _state(seq.keys[-1]))
        names = [*seq.identity_refs, "simplified_style_reference.png", "simple_blue_hour_environment.png"]
        if seq.ability_ref:
            names.append(seq.ability_ref)
        manifest = {
            "sequence_id": f"sequence_{seq.index:02d}", "target_duration_seconds": seq.duration,
            "source_shot_ids": [f"shot_{i:03d}" for i in range(seq.shot_first, seq.shot_last + 1)],
            "start_frame": "start_frame.png", "end_frame": "end_frame.png", "motion_reference": "motion_reference.mp4",
            "motion_reference_role": "white-model blocking, body trajectory, support, contact timing and camera path only",
            "identity_references": [f"../../shared_references/{name}" for name in seq.identity_refs],
            "style_reference": "../../shared_references/simplified_style_reference.png",
            "environment_reference": "../../shared_references/simple_blue_hour_environment.png",
            "ability_reference": f"../../shared_references/{seq.ability_ref}" if seq.ability_ref else None,
            "upload_image_count": 2 + len(names), "upload_video_count": 1,
            "motion_metadata": motion_metadata, "provider_calls": 0,
        }
        write_json(folder / "reference_manifest.json", manifest)
        (folder / "review_checklist.md").write_text(
            f"# Sequence {seq.index:02d} review\n\n"
            "- [ ] Both fighters retain simple colors, proportions and screen lanes\n"
            "- [ ] Motion follows the reference path at normal speed, with visible support-foot phases\n"
            "- [ ] Anticipation, contact or miss, reaction and recovery remain readable\n"
            "- [ ] No limb disappears; no glide, folded torso or camera-only motion\n"
            "- [ ] Same sparse street, screen-left light and south-side action axis\n"
            "- [ ] Next sequence begins from this sequence's approved end state\n"
            "- [ ] Rasengan, if present, stays in Naruto's hand and causes no added damage\n"
            "- [ ] Recorded heavy strike alone ends the fight\n", encoding="utf-8")
    _documents(output, plan)
    _review_sheet(output)
    status = validate(output)
    _readiness(output, status)
    return output, status


def _review_sheet(output: Path) -> None:
    thumbs = []
    for seq in SEQUENCES:
        for ratio in (0, .25, .5, .75, 1):
            thumb = frame_at(seq.keys, seq.duration * ratio, size=(180, 320))
            thumbs.append(thumb)
    sheet = Image.new("RGB", (180 * 5, 320 * 5), (20, 25, 34))
    for i, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((i % 5) * 180, (i // 5) * 320))
    review = output / "review"
    review.mkdir(exist_ok=True)
    sheet.save(review / "motion_contact_sheet.jpg", quality=86)


def _documents(output: Path, plan) -> None:
    guide = [
        "# Dreamina Seedance 2.5 manual workflow", "",
        "The five folders under `sequences/` are the upload units. The 28-shot source plan stays in `internal/` and is **not** a 28-upload queue. No Seedance call has been made.", "",
        "Dreamina's current [official how-to](https://dreamina.capcut.com/seedance/how-to-use-seedance-2-5) describes AI Video → Seedance 2.5 → Omni reference mode → `+` to add images/video and a structured prompt; its [motion-reference guide](https://dreamina.capcut.com/seedance/seedance-2-5-motion-reference-guide) describes using a reference video as a motion/white-model guide. Controls and access may vary by account or region; confirm them in your workspace before spending credits.", "",
        "## Test sequence 01 first", "",
        "1. Open Dreamina AI Video, select **Seedance 2.5**, and choose a vertical **9:16** output. If available, use Omni reference/reference-to-video mode. Open `sequences/sequence_01/`.",
        "2. Use `start_frame.png` as the opening image and `end_frame.png` as the ending image when the selected mode accepts both. Do not substitute an old polished shot keyframe.",
        "3. Open `reference_manifest.json`. Add only its four identity images (two per fighter), one style image, one environment image, and optional single ability image from `shared_references/`. Keep the total small; the limit is 2+2+1+1+1 images plus start/end frames.",
        "4. Add `motion_reference.mp4` from that same sequence as a **video/motion reference**, not a finished clip or character-identity source. If Dreamina labels uploaded assets with `@` identifiers, bind the motion reference to movement/timing and the stills to identity/style in the prompt. If your account cannot combine motion reference with start/end frames, record that limitation and test one supported mode; do not assume the controls exist.",
        "5. Paste `sequence_prompt.txt` and `sequence_negative_prompt.txt` from the same folder. Target its `target_duration_seconds` in `reference_manifest.json` (14, 9, 18, 15, or 6 seconds). If the UI offers only fixed lengths, choose the nearest supported length and trim in editing rather than stretching the action.",
        "6. Generate **only sequence 01**, then watch it at normal speed. Reject gliding, missing hands, body freezes, camera-axis flips, detailed redesigns or unrecorded contact. Change only the failed variable (reference role, camera, timing, or prompt) and regenerate that sequence.",
        "7. Once sequence 01 is approved, proceed in order through 02–05. Use the previous approved end frame as a continuity check against the next sequence's `start_frame.png`; if needed, replace the next start frame with the actual approved last frame after review, documenting the change. Match the same street, screen lanes, colors and light.",
        "8. Use Dreamina's **extension** only when a generated sequence is approved but a short continuation is genuinely needed; extend from its approved final video/frame, with identity and motion constraints unchanged. It is not required merely because a sequence boundary exists. The [official extension guide](https://dreamina.capcut.com/seedance/seedance-2-5-video-extension) describes extending a clip, but exact UI availability may vary.",
        "9. Download each approved clip separately. Assemble in order with hard cuts or brief motivated transitions; review cuts at phone size. Do not claim parity with the two samples until at least sequence 01 has been generated and reviewed at normal speed.", "",
        "## Sequence targets", "",
        "| Folder | Duration | Motion file | Ability board |", "|---|---:|---|---|",
    ]
    for seq in SEQUENCES:
        guide.append(f"| `sequences/sequence_{seq.index:02d}/` | {seq.duration}s | `motion_reference.mp4` | `{seq.ability_ref or 'none'}` |")
    guide += ["", "The first supplied sample favors simple silhouettes and short pose/cut rhythm; the second adds longer force arcs and controlled effects. These are pacing and readability references only. Do not upload their extracted frames or copy their exact poses. The final style remains deliberately simpler than the old 28 polished keyframes.", ""]
    (output / "seedance25_manual_workflow.md").write_text("\n".join(guide), encoding="utf-8")
    write_json(output / "provenance.json", {
        "source_replay_checksum": SOURCE_CHECKSUM, "canonical_event_sha256": EVENT_SHA,
        "recorded_outcome": plan.outcome, "simulation_changed": False,
        "noncanonical_editorial_staging": "failed hand-held Rasengan preparation/entry only; zero added contact or damage",
        "source_28_shot_plan": "internal/episode_plan_28_shots.json", "provider_calls": 0,
        "reference_art": "deterministic original flat figure blockouts created locally by seedance25_art.py",
        "reference_videos": "locally rendered schematic motion guides, not paid generated animation",
    })


def validate(output: Path) -> dict:
    output = output.resolve()
    issues: list[str] = []
    shared = output / "shared_references"
    files = {p.name for p in shared.glob("*.png")}
    if files != set(SHARED_NAMES):
        issues.append(f"Shared reference set differs from required twelve: {sorted(files ^ set(SHARED_NAMES))}")
    for name in SHARED_NAMES:
        path = shared / name
        if not path.is_file():
            issues.append(f"Missing shared reference: {name}")
            continue
        try:
            with Image.open(path) as image:
                image.verify()
        except OSError:
            issues.append(f"Invalid shared image: {name}")
    durations = []
    for seq in SEQUENCES:
        folder = output / "sequences" / f"sequence_{seq.index:02d}"
        needed = ("start_frame.png", "end_frame.png", "motion_reference.mp4", "sequence_prompt.txt",
                  "sequence_negative_prompt.txt", "continuity_start.json", "continuity_end.json",
                  "reference_manifest.json", "review_checklist.md")
        issues.extend(f"sequence_{seq.index:02d}: missing {name}" for name in needed if not (folder / name).is_file())
        if not all((folder / name).is_file() for name in needed):
            continue
        manifest = json.loads((folder / "reference_manifest.json").read_text(encoding="utf-8"))
        durations.append(manifest["target_duration_seconds"])
        if manifest["target_duration_seconds"] != seq.duration or len(manifest["identity_references"]) != 4:
            issues.append(f"sequence_{seq.index:02d}: invalid duration or identity reference count")
        if manifest["upload_image_count"] > 9 or manifest["upload_video_count"] != 1:
            issues.append(f"sequence_{seq.index:02d}: exceeds restrained input budget")
        identity_names = [Path(name).name for name in manifest["identity_references"]]
        if (sum(name.startswith("naruto_") for name in identity_names) != 2 or
                sum(name.startswith("omniman_") for name in identity_names) != 2):
            issues.append(f"sequence_{seq.index:02d}: identity references must contain two per fighter")
        references = [*manifest["identity_references"], manifest["style_reference"], manifest["environment_reference"]]
        if manifest["ability_reference"]:
            references.append(manifest["ability_reference"])
        for relative in references:
            reference = (folder / relative).resolve()
            if not reference.is_relative_to(shared) or not reference.is_file():
                issues.append(f"sequence_{seq.index:02d}: missing or unsafe reference {relative}")
        for name in ("start_frame.png", "end_frame.png"):
            try:
                with Image.open(folder / name) as image:
                    if image.size != (720, 1280):
                        issues.append(f"sequence_{seq.index:02d}: {name} not 720x1280")
            except OSError:
                issues.append(f"sequence_{seq.index:02d}: corrupt {name}")
        if not (folder / "sequence_prompt.txt").read_text().strip() or not (folder / "sequence_negative_prompt.txt").read_text().strip():
            issues.append(f"sequence_{seq.index:02d}: empty prompt")
        if not all(token in (folder / "sequence_prompt.txt").read_text() for token in ("seconds", "Start state", "End state", "Movement:", "Camera and shot sizes:", "Lighting and look:", "Ability behavior:", "Transition:")):
            issues.append(f"sequence_{seq.index:02d}: incomplete sequence prompt")
        start = json.loads((folder / "continuity_start.json").read_text())
        end = json.loads((folder / "continuity_end.json").read_text())
        if start != _state(seq.keys[0]) or end != _state(seq.keys[-1]):
            issues.append(f"sequence_{seq.index:02d}: continuity metadata differs from authored animatic")
        if seq.index > 1:
            previous = json.loads((output / "sequences" / f"sequence_{seq.index-1:02d}" / "continuity_end.json").read_text())
            if previous != start:
                issues.append(f"sequence_{seq.index:02d}: boundary pose differs from previous sequence")
            previous_frame = output / "sequences" / f"sequence_{seq.index-1:02d}" / "end_frame.png"
            if previous_frame.is_file() and previous_frame.read_bytes() != (folder / "start_frame.png").read_bytes():
                issues.append(f"sequence_{seq.index:02d}: boundary images differ from previous sequence")
        try:
            probe = _ffprobe(folder / "motion_reference.mp4")
            if (probe["width"], probe["height"]) != (360, 640) or abs(probe["duration_seconds"] - seq.duration) > .15:
                issues.append(f"sequence_{seq.index:02d}: motion-reference video dimensions/duration mismatch")
        except (OSError, KeyError, ValueError, subprocess.CalledProcessError):
            issues.append(f"sequence_{seq.index:02d}: unreadable motion reference")
        master = output / "motion_refs" / ["motion_ref_01_faceoff_and_charge.mp4", "motion_ref_02_opening_attack_and_evasion.mp4", "motion_ref_03_close_exchange.mp4", "motion_ref_04_ability_preparation.mp4", "motion_ref_05_final_clash_and_aftermath.mp4"][seq.index - 1]
        if not master.is_file():
            issues.append(f"sequence_{seq.index:02d}: named master motion reference missing")
        elif hashlib.sha256((folder / "motion_reference.mp4").read_bytes()).digest() != hashlib.sha256(master.read_bytes()).digest():
            issues.append(f"sequence_{seq.index:02d}: motion reference differs from named master")
    if sum(durations) != 62 or len(durations) != 5:
        issues.append(f"Sequence durations must total 62 seconds, got {durations}")
    replay_path = output / "internal/source_replay.json"
    if replay_path.is_file():
        replay = load_replay(replay_path)
        if replay["checksum"] != SOURCE_CHECKSUM:
            issues.append("Canonical replay checksum changed")
        plan, _ = build_plan(replay)
        if plan.canonical_event_sha256 != EVENT_SHA or plan.outcome != replay["result"]:
            issues.append("Canonical event stream or outcome changed")
    else:
        issues.append("Canonical replay missing")
    status = {"ready_for_sequence_01_test": not issues, "final_production_approved": False,
              "issues": issues, "sequence_count": len(durations), "total_target_duration_seconds": sum(durations),
              "shared_reference_count": len(files), "motion_reference_count": len(list((output / "motion_refs").glob("*.mp4"))),
              "source_replay_checksum": SOURCE_CHECKSUM, "canonical_event_sha256": EVENT_SHA,
              "provider_calls": 0, "motion_generation_reviewed": False}
    write_json(output / "validation_seedance25.json", status)
    return status


def _readiness(output: Path, status: dict) -> None:
    decision = "READY for a controlled sequence-01 test" if status["ready_for_sequence_01_test"] else "BLOCKED"
    (output / "seedance25_readiness.md").write_text(
        "# Dreamina Seedance 2.5 readiness\n\n"
        f"**{decision}.** Five sequence folders target {status['total_target_duration_seconds']} seconds. "
        f"Twelve shared flat references, {status['motion_reference_count']} motion-reference videos, "
        "ten boundary frames, sequence prompts, continuity records and upload manifests are present. "
        f"Validation issues: {len(status['issues'])}.\n\n"
        "The twelve references were redrawn as locally generated flat vector-like figures, with simple spiky hair/headband, a broad mustached cape silhouette, clear hands/feet, block colors, sparse blue-hour street, and no rendered fabric or detailed face. They are materially simpler than the previous polished comic keyframes. The motion clips are low-detail authored blocking guides, not finished fight animation. Start/end states agree across all four sequence boundaries. The 28-shot plan stays internal and the canonical replay/event hash are unchanged.\n\n"
        "The motion guide uses deliberate foot loads, takeoff, travel, guarded contact, recoil and recovery; the camera shifts only to reveal those actions. The final sequence carries the strongest recorded impact and KO. Naruto's failed Rasengan attempt is hand-held, noncanonical editorial staging without a hit. The package uses local Pillow and FFmpeg, no Blender or paid Seedance API.\n\n"
        "**Not final-production-ready.** Identity preservation, true fluidity, contact, foot skating, camera follow, transition quality and any UI-specific reference behavior remain unverified until a Dreamina Seedance 2.5 clip is generated. Test sequence 01 first and watch it at normal speed; reject and regenerate if the body or camera behavior deviates. Do not claim sample-video parity yet.\n\n"
        + ("\n".join(f"- {issue}" for issue in status["issues"]) + "\n" if status["issues"] else "No missing local files or structural validation errors.\n"),
        encoding="utf-8",
    )
