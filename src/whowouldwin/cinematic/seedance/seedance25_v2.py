"""A faster nine-sequence edit of the canonical seed-289 Seedance 2.5 package.

Each short clip has a concrete combat beat. No new damaging event is invented;
the one editorial Rasengan entry remains a failed hand-held melee attempt.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from whowouldwin.simulation.replay import load_replay

from .longform_seed289 import EVENT_SHA, SOURCE_CHECKSUM, build_plan
from .package import write_json
from .seedance25 import (ROOT, SOURCE, SHARED_NAMES, Sequence, _ffprobe, _negative,
                         _prompt, _review_sheet, _state, validate)
from .seedance25_art import Key, Pose, frame_at, motion_video, reference_images


DEFAULT_OUTPUT = ROOT / "outputs/seedance_ready/naruto_vs_omniman_seedance25_v2"

N0, O0 = Pose(104, guard=.65), Pose(260, guard=.7)
N1, O1 = Pose(88, crouch=.35, guard=.9, support="front"), Pose(260, crouch=.5, guard=.6, support="rear")
N2, O2 = Pose(70, crouch=.55, guard=.8, support="front"), Pose(187, lift=16, guard=.55, support="none")
N3, O3 = Pose(86, crouch=.42, guard=.85, support="both"), Pose(225, guard=.65, support="both")
N4, O4 = Pose(107, reach=.5, guard=.65, support="front"), Pose(215, guard=.55, support="rear")
N5, O5 = Pose(101, crouch=.4, guard=1, support="both"), Pose(184, reach=.2, guard=.5, support="both")
N6, O6 = Pose(78, crouch=.65, guard=.85, support="front"), Pose(190, lift=18, guard=.6, support="none")
N7, O7 = Pose(103, crouch=.25, reach=.2, orb=1, support="both"), Pose(220, guard=.7, support="both")
N8, O8 = Pose(124, crouch=.2, reach=.35, orb=1, support="rear"), Pose(220, guard=.45, reach=.15, support="both")
N9, O9 = Pose(75, down=1, support="none"), Pose(250, guard=.4, support="both")

FIGHT_REFS = ("naruto_simple_action_pose.png", "naruto_simple_silhouette.png",
              "omniman_simple_action_pose.png", "omniman_simple_silhouette.png")
FRONT_REFS = ("naruto_simple_front.png", "naruto_simple_three_quarter.png",
              "omniman_simple_front.png", "omniman_simple_three_quarter.png")

SEQUENCES: tuple[Sequence, ...] = (
    Sequence(1, "Faceoff, blink and flight load", 1, 4, 5,
             (Key(0, N0, O0, zoom=.9, beat="faceoff"),
              Key(1, Pose(103, crouch=.18, guard=.8, support="rear"), Pose(260, crouch=.12, guard=.7, support="rear"), zoom=.94, beat="read shoulder"),
              Key(2.3, Pose(83, crouch=.55, lean=-.45, guard=.9, support="front"), Pose(260, crouch=.2, guard=.7, support="rear"), zoom=1.0, beat="blink outside"),
              Key(3.7, Pose(88, crouch=.35, guard=.9, support="front"), Pose(260, crouch=.58, lean=-.45, guard=.6, support="rear"), zoom=1.04, beat="flight load"),
              Key(5, N1, O1, zoom=1.04, beat="takeoff poised")),
             FRONT_REFS, "flight_and_impact_simple_reference.png",
             ("0–1 seconds: Low wide faceoff; both shift weight instead of holding still.",
              "1–3 seconds: Naruto releases his trailing heel and uses the recorded blink to the outside lane; no contact.",
              "3–5 seconds: Omni-Man coils through boot, hip, chest and cape for his recorded dash; end before takeoff."),
             "Low wide establishes the axis; a short push-in follows Naruto's lateral blink, then a low medium shows Omni-Man loading.",
             "No attack lands. Blink and dash preparation are recorded actions.",
             "Cut on Omni-Man's boot push-off into sequence 02."),
    Sequence(2, "Flight charge, one hit and grounded catch", 5, 8, 7,
             (Key(0, N1, O1, zoom=1.04, beat="push-off"),
              Key(.9, Pose(88, guard=.9, support="both"), Pose(224, lift=34, lean=-.7, reach=.4, support="none"), camera_x=171, zoom=1.06, beat="flight takeoff"),
              Key(2.1, Pose(90, crouch=.28, guard=1, support="rear"), Pose(178, lift=24, lean=-.7, reach=.5, support="none"), camera_x=157, zoom=1.08, beat="charge lane"),
              Key(3.2, Pose(88, crouch=.6, lean=-.5, guard=1, support="rear"), Pose(150, lift=12, lean=-.6, reach=.65, support="none"), camera_x=152, zoom=1.12, beat="impact"),
              Key(4.2, Pose(65, crouch=.72, lean=-.25, guard=.7, support="front"), Pose(172, lift=24, reach=.1, support="none"), camera_x=148, zoom=1.02, beat="grounded catch"),
              Key(7, N2, O2, zoom=.98, beat="recovery")),
             FIGHT_REFS, "flight_and_impact_simple_reference.png",
             ("0–2 seconds: Omni-Man launches explosively right-to-left in flight; Naruto braces with both hands visible.",
              "2–4 seconds: One recorded shoulder charge touches Naruto's guarded torso. Show contact then immediate compression; do not add another blow.",
              "4–7 seconds: Naruto catches on a planted bent leg and recovers while Omni-Man brakes above the street."),
             "Track the launch from a low side lane, cut to a three-quarter contact view, then lower to see Naruto's support foot catch.",
             "One recorded flight-charge hit only, followed by recoil and recovery.",
             "End with Naruto grounded left and Omni-Man braking right."),
    Sequence(3, "Thrown wind shuriken and heavy reply", 9, 10, 7,
             (Key(0, N2, O2, zoom=.98, beat="recovery"),
              Key(1.1, Pose(77, crouch=.5, lean=-.3, reach=.65, stride=.45, support="rear"), Pose(207, lift=8, guard=.65, support="none"), zoom=1.03, beat="projectile windup"),
              Key(2.3, Pose(85, crouch=.35, reach=.95, support="front"), Pose(231, lift=3, lean=-.25, guard=.65, support="both"), zoom=1.06, beat="projectile miss"),
              Key(3.5, Pose(86, guard=.9, support="both"), Pose(215, crouch=.35, lean=-.45, guard=.6, support="rear"), zoom=1.04, beat="heavy load"),
              Key(4.7, Pose(91, crouch=.55, lean=-.5, guard=1, support="rear"), Pose(161, lean=-.5, reach=.45, stride=.7, support="front"), camera_x=153, zoom=1.12, beat="impact"),
              Key(5.6, Pose(72, crouch=.68, lean=-.7, guard=.5, support="front"), Pose(177, reach=.6, support="front"), camera_x=151, zoom=1.04, beat="heavy recoil"),
              Key(7, N3, O3, zoom=.98, beat="reset")),
             FIGHT_REFS, "flight_and_impact_simple_reference.png",
             ("0–3 seconds: Naruto pushes from his rear foot and throws the recorded four-bladed wind shuriken. It passes Omni-Man without touching him.",
              "3–5 seconds: Omni-Man lets it miss, plants, and turns hip then shoulder into one recorded heavy right. The fist meets Naruto's guard and upper torso.",
              "5–7 seconds: Naruto compresses and recoils, then both fighters reset their feet. No extra hit."),
             "Side profile proves the projectile misses; cut across to a medium three-quarter contact angle, then hold both fighters in frame for recoil.",
             "A small four-bladed Rasenshuriken-like projectile may be thrown. It is never the hand-held Rasengan.",
             "End on a brief planted reset; no extended stare-down."),
    Sequence(4, "Chakra surge, jab slip and Energy Orb hit", 11, 13, 7,
             (Key(0, N3, O3, zoom=.98, beat="reset"),
              Key(1, Pose(95, crouch=.45, guard=.85, support="both"), Pose(220, guard=.7, support="both"), zoom=1.03, beat="chakra surge"),
              Key(2.2, Pose(72, crouch=.6, lean=-.7, guard=.8, support="front"), Pose(178, reach=.85, stride=.45, support="rear"), camera_x=152, zoom=1.08, beat="jab miss"),
              Key(3.4, Pose(83, crouch=.4, guard=.7, support="rear"), Pose(194, reach=.55, guard=.4, support="both"), zoom=1.03, beat="outside plant"),
              Key(4.5, Pose(103, crouch=.35, reach=.85, stride=.4, support="front"), Pose(203, guard=.5, support="rear"), zoom=1.06, beat="energy counter"),
              Key(5.3, Pose(107, reach=.6, support="front"), Pose(211, crouch=.3, lean=.3, guard=.4, support="rear"), zoom=1.03, beat="projectile hit"),
              Key(7, N4, O4, zoom=.98, beat="press advantage")),
             FIGHT_REFS, None,
             ("0–2 seconds: Naruto's recorded Chakra Surge tightens his stance and outlines him with restrained blue. Omni-Man probes forward.",
              "2–4 seconds: Omni-Man jabs; Naruto slips outside with a planted lead foot and released trailing heel. The fist visibly misses.",
              "4–7 seconds: Naruto plants and fires one tiny straight cyan Energy Orb pellet. It crosses the gap and hits Omni-Man once, then both move immediately into the next range."),
             "Shift from a high slip angle to a side projectile lane, then a short medium reaction. Keep screen-left Naruto and screen-right Omni-Man.",
             "The Energy Orb is a plain straight projectile, not Rasengan and not a large beam.",
             "Follow Omni-Man's recoil into a fast closing step, with no idle hold."),
    Sequence(5, "Grapple, escape and blocked heavy strike", 14, 16, 7,
             (Key(0, N4, O4, zoom=.98, beat="press advantage"),
              Key(1.1, Pose(111, crouch=.3, guard=.7, support="rear"), Pose(177, lean=-.35, reach=.55, stride=.45, support="front"), camera_x=156, zoom=1.07, beat="close range"),
              Key(2.1, Pose(109, crouch=.38, guard=.9, support="both"), Pose(166, reach=.45, guard=.25, support="front"), camera_x=152, zoom=1.12, beat="grapple"),
              Key(3.4, Pose(100, crouch=.5, lean=-.35, guard=.85, support="front"), Pose(179, reach=.2, guard=.6, support="both"), zoom=1.04, beat="pivot escape"),
              Key(4.6, Pose(102, crouch=.5, guard=1, support="both"), Pose(159, lean=-.55, reach=.55, stride=.5, support="rear"), camera_x=152, zoom=1.1, beat="impact"),
              Key(5.5, Pose(90, crouch=.62, guard=.9, support="front"), Pose(173, reach=.4, guard=.5, support="front"), zoom=1.03, beat="guard recoil"),
              Key(7, N5, O5, zoom=.98, beat="retract")),
             FIGHT_REFS, None,
             ("0–2 seconds: Omni-Man closes from the right and establishes one recorded upper-arm grapple; Naruto braces rather than freezing.",
              "2–4 seconds: Naruto pivots around a support foot and regains an outside angle as Omni-Man lets go and reloads.",
              "4–7 seconds: Omni-Man's recorded heavy strike meets Naruto's bent forearm block. Show forearm redirection, compression and a quick fist retraction; no knockout."),
             "A medium over-shoulder approach becomes a stable three-quarter grapple/block composition. Keep both arms visible at contact.",
             "No extra projectile, Rasengan or new damage is introduced in the grapple/block exchange.",
             "Leave the block immediately for the next jab and charge, avoiding a held pose."),
    Sequence(6, "Jab miss and second flight charge", 17, 20, 7,
             (Key(0, N5, O5, zoom=.98, beat="retract"),
              Key(1.1, Pose(92, crouch=.38, guard=.82, support="both"), Pose(194, reach=.1, guard=.65, support="both"), zoom=1.0, beat="pressure reset"),
              Key(2.2, Pose(73, crouch=.62, lean=-.65, guard=.8, support="front"), Pose(163, reach=.82, stride=.5, support="rear"), camera_x=149, zoom=1.08, beat="jab miss"),
              Key(3.3, Pose(79, crouch=.38, guard=.9, support="rear"), Pose(187, reach=.2, guard=.55, support="both"), zoom=1.01, beat="jab follow-through"),
              Key(4.5, Pose(80, guard=1, support="both"), Pose(215, crouch=.5, lean=-.5, support="rear"), zoom=1.04, beat="second charge load"),
              Key(5.4, Pose(79, crouch=.3, guard=1, support="rear"), Pose(169, lift=31, lean=-.7, reach=.3, support="none"), camera_x=152, zoom=1.08, beat="flight blitz"),
              Key(6.2, Pose(78, crouch=.7, lean=-.5, guard=1, support="rear"), Pose(139, lift=12, lean=-.65, reach=.6, support="none"), camera_x=149, zoom=1.12, beat="impact"),
              Key(7, N6, O6, zoom=1.02, beat="charge recoil")),
             FIGHT_REFS, "flight_and_impact_simple_reference.png",
             ("0–3 seconds: Omni-Man retracts from the block and jabs again. Naruto drops his center and slips outside; this fist misses cleanly.",
              "3–5 seconds: Omni-Man follows the missed line, then plants and compresses for his recorded second flight charge. Naruto raises his guard.",
              "5–7 seconds: Omni-Man accelerates into one recorded charge hit. Show shoulder surface contact, Naruto's compression and Omni-Man's brake."),
             "A high dodge insert returns to a low side launch lane, then cuts to three-quarter contact with both silhouettes clear.",
             "Only the second recorded charge hits; the preceding jab misses.",
             "End on Naruto recoiling toward the left, ready for a grounded catch."),
    Sequence(7, "Grounded catch and hand-held Rasengan formation", 21, 22, 6,
             (Key(0, N6, O6, zoom=1.02, beat="charge recoil"),
              Key(1.1, Pose(67, crouch=.72, lean=-.25, guard=.7, support="front"), Pose(210, lift=6, guard=.6, support="none"), camera_x=157, zoom=1.01, beat="grounded catch"),
              Key(2.2, Pose(82, crouch=.5, guard=.65, support="rear"), Pose(220, guard=.65, support="both"), zoom=1.03, beat="create distance"),
              Key(3.3, Pose(92, crouch=.42, guard=.3, orb=.25, support="rear"), Pose(220, guard=.7, support="both"), zoom=1.08, beat="hand preparation"),
              Key(4.6, Pose(101, crouch=.3, reach=.15, orb=.7, support="both"), Pose(220, guard=.7, support="both"), zoom=1.11, beat="Rasengan spin"),
              Key(6, N7, O7, zoom=1.09, beat="Rasengan formed")),
             FRONT_REFS, "rasengan_simple_reference.png",
             ("0–2 seconds: Naruto catches the charge on a bent support leg; heel and chest settle rather than sliding.",
              "2–4 seconds: He creates short distance and draws both hands together while Omni-Man squares up on the right.",
              "4–6 seconds: A compact rotating blue Rasengan forms in Naruto's open palm. This is preparation, not a hit or projectile."),
             "Start medium with feet visible; push to a brief high three-quarter hand view, then return to both fighters in frame.",
             "Rasengan stays attached to Naruto's palm and is never thrown.",
             "Cut on Naruto's first leg-driven step into the attempted entry."),
    Sequence(8, "Failed Rasengan entry and Omni-Man's loaded reply", 23, 25, 7,
             (Key(0, N7, O7, zoom=1.09, beat="Rasengan formed"),
              Key(1.1, Pose(105, crouch=.32, reach=.22, orb=1, support="rear"), Pose(222, crouch=.2, guard=.55, support="rear"), zoom=1.08, beat="Omni reads hand"),
              Key(2.4, Pose(111, crouch=.4, reach=.28, orb=1, stride=.5, support="rear"), Pose(222, guard=.6, support="front"), camera_x=169, zoom=1.06, beat="Rasengan entry"),
              Key(3.8, Pose(120, crouch=.28, reach=.34, orb=1, stride=.6, support="front"), Pose(218, lean=.2, guard=.45, support="rear"), camera_x=171, zoom=1.1, beat="outside slip"),
              Key(5, N8, Pose(220, guard=.5, reach=.1, support="rear"), camera_x=174, zoom=1.12, beat="near miss"),
              Key(6.1, N8, Pose(209, crouch=.28, lean=-.35, guard=.35, reach=.12, support="rear"), camera_x=168, zoom=1.11, beat="heavy reply load"),
              Key(7, N8, O8, camera_x=177, zoom=1.09, beat="intercept poised")),
             ("naruto_simple_front.png", "naruto_simple_action_pose.png", "omniman_simple_front.png", "omniman_simple_action_pose.png"),
             "rasengan_simple_reference.png",
             ("0–2 seconds: Omni-Man reads the blue energy and loads his recorded finishing heavy strike while Naruto's rear foot pushes off.",
              "2–5 seconds: Naruto enters with Rasengan in his bent hand. Omni-Man shifts outside the path; the orb stops short of his torso without touching or damaging him.",
              "5–7 seconds: Omni-Man redirects the near miss and brings his right fist into the reply lane. Do not land it yet."),
             "Track a side-profile hand path, cut to a medium three-quarter near-miss with a visible gap, then show Omni-Man's loaded shoulder.",
             "Failed editorial Rasengan attempt is noncanonical and non-damaging; it remains hand-held and never becomes a beam or thrown orb.",
             "Continue directly into the recorded heavy strike, preserving the exact near-miss spacing."),
    Sequence(9, "Decisive heavy strike, fall and aftermath", 26, 28, 7,
             (Key(0, N8, O8, camera_x=177, zoom=1.09, beat="intercept poised"),
              Key(1, Pose(138, crouch=.55, lean=-.55, guard=.15, orb=.5, support="rear"), Pose(205, lean=-.65, reach=.5, stride=.8, support="rear"), camera_x=166, zoom=1.14, beat="impact"),
              Key(1.7, Pose(112, crouch=.72, lean=-.8, guard=.2, orb=0, support="rear"), Pose(204, reach=.7, guard=.1, support="front"), camera_x=164, zoom=1.12, beat="KO recoil"),
              Key(3, Pose(78, down=.78, support="none"), Pose(226, reach=.25, guard=.3, support="both"), zoom=1.01, beat="fall"),
              Key(4.8, Pose(75, down=1, support="none"), Pose(241, guard=.42, support="both"), zoom=.94, beat="settle"),
              Key(7, N9, O9, zoom=.88, beat="recorded aftermath")),
             FIGHT_REFS, "rasengan_simple_reference.png",
             ("0–2 seconds: Omni-Man's rear foot, pelvis, chest and right shoulder drive the recorded heavy fist into Naruto's upper torso. Show contact, then a brief small graphic impact accent. The unused Rasengan collapses harmlessly.",
              "2–5 seconds: Naruto compresses, recoils, loses support and falls. Omni-Man follows through and retracts; no second strike or recovery.",
              "5–7 seconds: Widen to the recorded quiet outcome: Naruto down left, Omni-Man upright right, no new action."),
             "Low three-quarter impact insert shows the fist, then track Naruto's fall and widen to an unambiguous aftermath.",
             "The recorded heavy strike alone produces the KO. Rasengan never hits Omni-Man or leaves Naruto's hand.",
             "Clean hold to end; no next sequence."),
)

MOTION_NAMES = (
    "motion_ref_01_faceoff_blink.mp4", "motion_ref_02_flight_charge.mp4",
    "motion_ref_03_projectile_heavy.mp4", "motion_ref_04_surge_slip_counter.mp4",
    "motion_ref_05_grapple_block.mp4", "motion_ref_06_jab_second_charge.mp4",
    "motion_ref_07_catch_rasengan.mp4", "motion_ref_08_failed_entry.mp4",
    "motion_ref_09_final_ko.mp4",
)


def build(output: Path = DEFAULT_OUTPUT, *, fps: int = 15) -> tuple[Path, dict]:
    """Build a new paced package; never mutate the original five-sequence edit."""
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Refusing to overwrite existing Seedance package: {output}")
    if not 3 <= fps <= 30:
        raise ValueError("Motion-reference FPS must be between 3 and 30")
    replay = load_replay(SOURCE)
    plan, beats = build_plan(replay)
    output.mkdir(parents=True, exist_ok=True)
    shared = output / "shared_references"
    reference_images(shared)
    if {p.name for p in shared.glob("*.png")} != set(SHARED_NAMES):
        raise ValueError("Exactly twelve shared graphic references are required")
    internal = output / "internal"
    internal.mkdir()
    shutil.copyfile(SOURCE, internal / "source_replay.json")
    write_json(internal / "episode_plan_28_shots.json", plan)
    write_json(internal / "fight_beats.json", beats)
    write_json(internal / "sequence_shot_map.json", [
        {"sequence": seq.index,
         "source_shots": [f"shot_{index:03d}" for index in range(seq.shot_first, seq.shot_last + 1)],
         "target_generation_seconds": seq.duration}
        for seq in SEQUENCES
    ])
    motion_root = output / "motion_refs"
    motion_root.mkdir()
    for seq, motion_name in zip(SEQUENCES, MOTION_NAMES, strict=True):
        folder = output / "sequences" / f"sequence_{seq.index:02d}"
        folder.mkdir(parents=True)
        frame_at(seq.keys, 0, size=(720, 1280)).save(folder / "start_frame.png")
        frame_at(seq.keys, seq.duration, size=(720, 1280)).save(folder / "end_frame.png")
        motion_metadata = motion_video(seq.keys, seq.duration, motion_root / motion_name, fps=fps)
        shutil.copyfile(motion_root / motion_name, folder / "motion_reference.mp4")
        (folder / "sequence_prompt.txt").write_text(_prompt(seq), encoding="utf-8")
        (folder / "sequence_negative_prompt.txt").write_text(_negative(seq), encoding="utf-8")
        write_json(folder / "continuity_start.json", _state(seq.keys[0]))
        write_json(folder / "continuity_end.json", _state(seq.keys[-1]))
        write_json(folder / "reference_manifest.json", {
            "sequence_id": f"sequence_{seq.index:02d}",
            "target_duration_seconds": seq.duration,
            "source_shot_ids": [f"shot_{index:03d}" for index in range(seq.shot_first, seq.shot_last + 1)],
            "start_frame": "start_frame.png", "end_frame": "end_frame.png",
            "motion_reference": "motion_reference.mp4", "motion_reference_master": motion_name,
            "motion_reference_role": "schematic movement and timing only, never canonical combat evidence",
            "identity_references": [f"../../shared_references/{name}" for name in seq.identity_refs],
            "style_reference": "../../shared_references/simplified_style_reference.png",
            "environment_reference": "../../shared_references/simple_blue_hour_environment.png",
            "ability_reference": f"../../shared_references/{seq.ability_ref}" if seq.ability_ref else None,
            "upload_image_count": 8 + (1 if seq.ability_ref else 0), "upload_video_count": 1,
            "motion_metadata": motion_metadata, "provider_calls": 0,
        })
        (folder / "review_checklist.md").write_text(
            f"# Sequence {seq.index:02d}: {seq.name}\n\n"
            "- [ ] One clear recorded combat beat or consequence leads this short clip\n"
            "- [ ] Feet load, push, plant and recover without skating\n"
            "- [ ] Hands and contact or miss remain visible at normal speed\n"
            "- [ ] The fighters retain their left/right screen lanes and flat designs\n"
            "- [ ] The next sequence starts from this approved end state\n"
            "- [ ] No new damage or altered outcome; Rasengan remains hand-held and misses\n",
            encoding="utf-8",
        )
    _review_sheet(output, SEQUENCES)
    _assemble_review_animatic(output)
    write_json(output / "provenance.json", {
        "source_replay_checksum": SOURCE_CHECKSUM, "canonical_event_sha256": EVENT_SHA,
        "recorded_outcome": plan.outcome, "simulation_changed": False,
        "previous_local_package": "outputs/seedance_ready/naruto_vs_omniman_seedance25",
        "noncanonical_editorial_staging": "failed hand-held Rasengan attempt only; no added contact or damage",
        "source_28_shot_plan": "internal/episode_plan_28_shots.json", "provider_calls": 0,
        "art_and_motion": "locally authored flat graphic references and schematic MP4 animatics",
    })
    _documents(output)
    status = validate_v2(output)
    _readiness(output, status)
    return output, status


def validate_v2(output: Path) -> dict:
    """Validate the nine uploads and the continuous pacing-review asset."""
    output = output.resolve()
    status = validate(output, sequences=SEQUENCES, target_seconds=60)
    animatic = output / "review/episode_motion_animatic.mp4"
    if not animatic.is_file():
        status["issues"].append("Missing stitched 60-second motion animatic")
    else:
        try:
            probe = _ffprobe(animatic)
            if (probe["width"], probe["height"]) != (360, 640) or abs(probe["duration_seconds"] - 60) > .15:
                status["issues"].append("Stitched motion animatic has wrong dimensions or duration")
        except (OSError, KeyError, ValueError, subprocess.CalledProcessError):
            status["issues"].append("Stitched motion animatic is unreadable")
    status["ready_for_sequence_01_test"] = not status["issues"]
    write_json(output / "validation_seedance25.json", status)
    return status


def _assemble_review_animatic(output: Path) -> None:
    """Concatenate the nine identical-format local guides for pacing review."""
    review = output / "review"
    review.mkdir(exist_ok=True)
    playlist = review / "motion_concat.txt"
    playlist.write_text("".join(f"file '../motion_refs/{name}'\n" for name in MOTION_NAMES), encoding="utf-8")
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", str(playlist), "-c", "copy", str(review / "episode_motion_animatic.mp4"),
    ], check=True)


def _documents(output: Path) -> None:
    rows = ["# Faster Dreamina Seedance 2.5 manual workflow", "",
            "This is a separate nine-sequence edit of the same canonical seed-289 fight. It targets 60 seconds and keeps the prior five-sequence package untouched. No provider has been called.", "",
            "1. Open Dreamina AI Video, select Seedance 2.5 and vertical 9:16. Use its reference mode if your account offers it.",
            "2. Test `sequences/sequence_01/` first. Use its `start_frame.png` and `end_frame.png` where both are accepted.",
            "3. Upload only the shared images named in that folder's `reference_manifest.json`: two Naruto, two Omni-Man, one style, one environment, and one ability board only when listed.",
            "4. Add that folder's `motion_reference.mp4` as motion/video guidance, not as finished footage. Paste `sequence_prompt.txt` and `sequence_negative_prompt.txt` into the appropriate controls.",
            "5. Target the duration in the manifest. If the UI offers only fixed lengths, use the nearest supported length, then trim in editing. Do not stretch a slow clip just to fill time.",
            "6. Watch sequence 01 at normal speed. Reject frozen bodies, gliding, missing arms, axis reversal, extra hits, or an airborne Rasengan. Regenerate only the failed sequence.",
            "7. Generate sequences 02–09 in order. Compare each approved end frame to the next start frame; use the approved output frame as continuity input if supported and document any replacement.",
            "8. Use extension only for an approved clip that genuinely needs a short continuation. The short sequence boundaries are intentional edit points, not invitations to invent attacks.", "",
            "| Sequence | Target | Dominant beat |", "|---|---:|---|" ]
    for seq in SEQUENCES:
        rows.append(f"| `sequence_{seq.index:02d}` | {seq.duration}s | {seq.name} |")
    rows += ["", "The 28-shot plan in `internal/` remains source attribution, not 28 separate uploads. The final heavy strike is the recorded KO. Naruto's failed Rasengan is a noncanonical editorial attempt and never becomes a projectile or damaging hit.",
             "", "Review `review/episode_motion_animatic.mp4` to assess the complete 60-second pacing before uploading. This stitched clip is a schematic motion guide, not a generated episode.",
             "", "A locally validated package is ready for **testing**, not publication. Fluidity, character stability, reference-mode compatibility and cuts must be judged after Dreamina generates clips.", ""]
    (output / "seedance25_manual_workflow.md").write_text("\n".join(rows), encoding="utf-8")
    pacing = {
        "previous_package": {"sequence_count": 5, "target_seconds": 62,
                             "durations": [14, 9, 18, 15, 6], "longest_sequence_seconds": 18},
        "new_package": {"sequence_count": len(SEQUENCES), "target_seconds": sum(seq.duration for seq in SEQUENCES),
                        "durations": [seq.duration for seq in SEQUENCES],
                        "longest_sequence_seconds": max(seq.duration for seq in SEQUENCES)},
        "editorial_rule": "Each sequence carries a recorded action, defense, impact or direct consequence; no extra hit is invented.",
    }
    write_json(output / "review/pacing_comparison.json", pacing)
    (output / "review/pacing_comparison.md").write_text(
        "# Pacing comparison\n\n"
        "The first Seedance 2.5 version grouped 62 seconds into five clips (14, 9, 18, 15, 6 seconds). "
        "This derivative uses nine clips (5, 7, 7, 7, 7, 7, 6, 7, 7 seconds), totaling 60 seconds. "
        "The longest uninterrupted generation falls from 18 to 7 seconds. Opening charge, projectile/heavy reply, "
        "surge/slip/counter, grapple/block, jab/second charge, and the KO now have distinct upload units. "
        "The hand-held failed Rasengan attempt is explicitly editorial and non-damaging. "
        "This is a denser edit of recorded events, not a claim that the 7.55-second simulated fight physically lasted 60 seconds.\n",
        encoding="utf-8",
    )


def _readiness(output: Path, status: dict) -> None:
    (output / "seedance25_readiness.md").write_text(
        "# Nine-sequence Seedance 2.5 readiness\n\n"
        f"**{'READY for sequence-01 test' if status['ready_for_sequence_01_test'] else 'BLOCKED'}.** "
        f"{status['sequence_count']} sequences target {status['total_target_duration_seconds']} seconds; "
        f"{status['shared_reference_count']} shared flat references and {status['motion_reference_count']} local motion animatics. "
        f"Local validation issues: {len(status['issues'])}.\n\n"
        "The canonical replay checksum, event hash and Omni-Man heavy-strike KO are unchanged. "
        "The only noncanonical action is a failed, non-damaging hand-held Rasengan entry. "
        "These low-detail animatics communicate timing and trajectories; Dreamina motion quality, anatomy, continuity and account-specific reference behavior remain unverified. "
        "Test sequence 01 first at normal speed. No paid API, Blender scene or final rendered episode was used.\n\n"
        + ("\n".join(f"- {issue}" for issue in status["issues"]) + "\n" if status["issues"] else "No structural package issues.\n"),
        encoding="utf-8",
    )
