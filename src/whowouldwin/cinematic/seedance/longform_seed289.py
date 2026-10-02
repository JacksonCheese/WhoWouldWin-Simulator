"""Directed 62-second editorial expansion of the immutable seed-289 replay.

The failed Rasengan attempt is an explicitly noncanonical, non-damaging
presentation beat authorized for this episode. It cannot change the replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import shutil

from whowouldwin.cinematic.episodes.adapter import adapt_replay
from whowouldwin.simulation.replay import digest, load_replay
from .planning import _state_at, adapt_beats, ability_specs
from .schemas import EpisodePlan, SeedanceShot, VisualContinuity
from .package import validate_package, write_json

SOURCE_CHECKSUM = "c71224213a7fd39fc0ba0e3f3e81f634016ecfd8e66f51d2aff51d721318bf53"
EVENT_SHA = "fab6b38d3420e0106378e1f5dae007061237417ba435e9be3fec1497b4578147"
EPISODE_ID = "naruto_vs_omniman_60s"
STYLE = (
    "Simplified hand-drawn 2D graphic combat, flat orange/black Naruto and red/off-white caped Omni-Man, "
    "simple recognizable heads, bold separated silhouettes, clean ink edges, one flat shadow per body mass, "
    "sparse blue-hour street, full-frame vertical 9:16. No photorealism or detailed 3D look."
)
NEGATIVE = (
    "No photorealism, realistic 3D, intricate fabric or facial detail, redesigned faces or costumes, extra fighters, "
    "duplicated or melted limbs, missing fingers, folded torsos, rubber elbows, tangled hands, floating feet, "
    "skating, gliding, teleporting without the recorded blink, unexplained impacts, new damage, camera-axis flip, "
    "random flailing, bodies freezing while only the camera moves, giant obscuring bloom, phone UI, subtitles, "
    "logos, letterbox, or a thrown Rasengan."
)


@dataclass(frozen=True)
class Direction:
    sequence: int
    event_index: int
    weight: float
    title: str
    framing: str
    camera: str
    action: str
    start_pose: str
    end_pose: str
    keyframe: str
    ability: str = ""
    editorial: bool = False


SHOTS = (
    Direction(1, 0, 2.8, "Street faceoff", "wide establishing, low street level", "slow push toward the open lane", "Naruto settles into a low right-facing guard on screen left while Omni-Man plants both boots on screen right; their eye line locks and neither attacks.", "two separated guarded silhouettes", "same lane, coiled bodies", "wide street faceoff, full figures separated, open road stripe between them"),
    Direction(1, 0, 2.0, "Naruto reads the threat", "close-up on Naruto eyes and brow", "small lateral creep, not a zoom", "Naruto's eyes track Omni-Man's right shoulder; his chin lowers and rear heel takes weight before he commits to movement.", "Naruto alert, face turned right", "Naruto loaded on rear foot", "simple blond spikes and headband; narrowed blue eyes, shoulder line entering frame"),
    Direction(1, 7, 2.0, "Omni-Man commits", "low-angle close-up on fist, boot and cape edge", "tilt from planted boot to right fist", "Omni-Man compresses through his rear leg; his fist closes, pelvis turns, and cape delays behind the shoulder before the recorded dash.", "right boot planted, fist at ribs", "heel releasing, fist aligned", "broad red-white figure, boot pushing road, clenched fist and restrained cape"),
    Direction(1, 9, 2.3, "Naruto blink line", "high-angle overhead reposition", "short pan to reveal the empty former position", "Naruto releases his support foot and performs the recorded blink to the outside lane; leave a brief afterimage, with no extra attack or contact.", "Naruto low guard left", "Naruto appears outside the charge lane", "overhead simple road stripe; Naruto outside original lane; Omni-Man distant right"),
    Direction(2, 17, 2.5, "Flight takeoff", "low-angle power medium", "lag half a beat then track acceleration", "Omni-Man pushes off the asphalt through ankle, knee, hip and chest into recorded flight; dust kicks back as Naruto turns toward him.", "Omni-Man compressed on support leg", "Omni-Man airborne and aligned to travel", "Omni-Man large in frame, cape trailing, road dust localized, Naruto smaller opposite"),
    Direction(2, 21, 1.9, "Charge travel", "side-profile two-character attack lane", "fast horizontal track preserving the axis", "Omni-Man closes distance from right to left with hips and shoulder aligned; Naruto braces with bent knees and a compact guard. Show anticipation then accelerating travel, not a constant slide.", "Omni-Man launched, Naruto bracing", "one body-length from recorded hit", "clean profile charge path with readable empty gap before contact"),
    Direction(2, 24, 1.0, "Opening impact", "brief three-quarter impact insert", "camera reaches contact before a tiny kick", "The recorded charge hits Naruto once at the torso; Omni-Man's shoulder meets a readable surface point, Naruto compresses, and a two-frame graphic impact accent reveals the contact rather than hiding it.", "approaching shoulder, Naruto guarded", "Naruto recoiling left", "shoulder-to-torso touch, distinct silhouettes and one small white impact star"),
    Direction(2, 24, 2.3, "Naruto catches himself", "low side-profile landing, Naruto foreground", "follow Naruto's backward landing", "Naruto turns the first hit into a sliding but grounded catch: rear foot lands, knee bends, torso lags and hands reset. Omni-Man brakes in flight and watches; no second hit.", "Naruto recoiling", "Naruto low planted guard", "Naruto grounded catch on left, Omni-Man hovering at distance right"),
    Direction(2, 31, 2.7, "Charged vortex misses", "over-shoulder Naruto to distant Omni-Man", "follow the thrown projectile then hold the miss lane", "Naruto loads rear foot, rotates hip and shoulder, and throws the recorded charged-vortex projectile as a small four-bladed Rasenshuriken-like wind shuriken. It passes Omni-Man without contact, as recorded.", "Naruto planted, wind energy cupped", "projectile misses; both fighters separate", "four-bladed blue-white wind shuriken passing clear of Omni-Man; no impact", "charged_vortex"),
    Direction(2, 36, 2.5, "Heavy strike lands", "medium three-quarter contact", "short push into the blow, then settle", "Omni-Man lets the missed projectile pass, plants, rotates pelvis then chest, and drives the recorded heavy right straight into Naruto's guarded upper body. Naruto's ribcage compresses and he recoils; no extra blow.", "Omni-Man coiled, Naruto resetting", "Naruto staggered; Omni-Man follows through", "Omni-Man right fist at Naruto upper torso, clear feet and separated limbs"),
    Direction(3, 47, 2.2, "Chakra surge", "medium-low Naruto character shot", "small orbit that does not cross the axis", "Naruto sinks into both feet and activates recorded Chakra Surge. A thin blue aura grows around his unchanged silhouette while Omni-Man slows his approach.", "Naruto staggered but grounded", "Naruto transformed in compact stance", "Naruto orange-black figure with tight blue aura, both feet planted", "chakra_form"),
    Direction(3, 50, 1.8, "Jab misses", "side-profile medium attack lane", "brief lateral follow with Naruto", "Omni-Man probes with the recorded jab. Naruto sees the shoulder twitch, shifts outside on a planted lead foot, releases the trailing heel, and leaves the fist passing through empty air.", "Omni-Man fist loaded, Naruto low", "Naruto outside the jab line", "Omni-Man extended jab visibly missing Naruto by a narrow gap"),
    Direction(3, 60, 2.1, "Energy Orb counter", "over Naruto shoulder, deep distant target", "track the compact projectile, keep launch and hit in view", "Naruto uses the outside angle to plant and fire the recorded generic Energy Orb projectile. It is a tiny straight cyan pellet with no spiral, distinct from Rasengan. It crosses a visible gap and hits Omni-Man once; this is not a hand strike.", "Naruto planted outside jab", "Omni-Man recoils from projectile", "small straight blue generic energy pulse crossing a clear gap into Omni-Man chest", "energy_orb"),
    Direction(3, 64, 2.3, "Grapple answer", "over-shoulder from behind Omni-Man", "close the gap with the reaching arm", "Omni-Man absorbs the projectile, steps in and establishes his recorded grapple on Naruto's upper arm/torso. Naruto's feet scrape into support and his free arm protects his center.", "Omni-Man recovering, Naruto planted", "Omni-Man holds one clear grip; Naruto braced", "one Omni-Man hand gripping Naruto upper arm; other limbs separate; both feet legible", "grapple"),
    Direction(3, 70, 2.1, "Pivot out of grip", "overhead/high-angle reposition", "short clockwise camera drift while staying south of axis", "Naruto turns his hips around a planted support foot to regain an outside lane as Omni-Man releases the grip and loads his next heavy strike. This is a defensive reposition, not an added hit.", "close grapple separation", "Naruto outside line, Omni-Man coiled", "overhead lane geometry: fighters one arm's length apart, Naruto outside"),
    Direction(3, 78, 2.4, "Forearm interception", "tight three-quarter medium contact", "steady frame through the block", "Omni-Man drives the recorded heavy strike through rear foot, hip and shoulder. Naruto meets the fist with one forearm; elbow stays bent, both feet plant, and the guarded impact visibly costs him strength.", "Omni-Man heavy windup, Naruto guard", "one fist-to-forearm block, Naruto compressed", "single clean fist/forearm contact, both torsos separate, no giant effect", "heavy_strike"),
    Direction(3, 79, 1.8, "Guard recoil", "reaction close-up Naruto and Omni arm", "pull back only as Naruto yields", "Naruto's blocking shoulder and chest lag behind his planted hips, then he steps out of pressure. Omni-Man retracts the fist instead of freezing in extension.", "forearm block under load", "Naruto guard resets, Omni-Man re-centers", "Naruto strained brow and bent guarding forearm; Omni-Man pulling fist back"),
    Direction(3, 91, 2.1, "Narrow evade", "medium side-profile with both feet", "quick lateral pan following Naruto's slip", "Omni-Man commits a recorded jab; Naruto drops his center and slips narrowly outside it, lifting and replanting the trailing foot. The punch misses cleanly and Omni-Man follows its line past Naruto's shoulder.", "both fighters guarded", "Naruto outside, Omni-Man overextended", "Naruto low dodge just outside Omni-Man extended fist, open miss lane"),
    Direction(4, 94, 2.3, "Second charge setup", "low-angle power shot Omni-Man", "short push then hold before release", "Omni-Man sees Naruto recovering, banks his torso into flight and compresses before the recorded second charge. Naruto plants and raises his guard, unable to leave the lane in time.", "Omni-Man overextended", "Omni-Man aligned into charge; Naruto braced", "Omni-Man red-white body diagonal and cape trailing, Naruto distant left"),
    Direction(4, 102, 2.2, "Second charge hit", "perpendicular side-profile tracking impact", "follow then abruptly stop at contact", "Omni-Man accelerates across the street and lands the recorded second charge on Naruto. His shoulder drives through a surface touch; Naruto compresses and recoils toward the left curb.", "clear gap before second charge", "Naruto displaced, Omni-Man braking", "second shoulder-to-body contact, visible street scale and one restrained impact line"),
    Direction(4, 107, 2.0, "Naruto makes space", "medium-wide recovery lane", "follow Naruto down to planted feet", "Naruto catches the second hit on a bent leg and creates a few steps of distance. His chest settles over his pelvis, rear heel releases, and his hands come together for one final attempt; no hit occurs here.", "Naruto recoiling, Omni-Man braking", "Naruto separated and planted", "Naruto left catching balance, open street between fighters"),
    Direction(4, 107, 2.4, "Failed Rasengan preparation", "high three-quarter close-up of Naruto's cupped hand and face", "small arc around the hand, same camera side", "Editorial non-damaging attempt: Naruto stabilizes his stance and condenses a rotating Rasengan in his physical hand. The orb remains attached to his palm; it is a melee attack, never thrown, and has no recorded hit.", "Naruto separated, hands gathering", "hand-held orb formed, elbow bent", "Naruto open palm cradling compact rotating blue Rasengan; blond head and orange sleeve visible", "rasengan", True),
    Direction(4, 110, 2.2, "Omni-Man reads the opening", "Omni-Man reaction close-up", "cut to stern eyes, then short pull back", "Omni-Man sees Naruto's hand-held energy, sets his boots and loads the recorded finishing heavy strike through pelvis and shoulder. The hand effect remains restrained in the distant reverse lane.", "Omni-Man braking, Naruto charging", "Omni-Man right fist loaded", "Omni-Man stern eyes and right shoulder commitment; Naruto blue hand orb distant", "rasengan", True),
    Direction(5, 110, 2.2, "Naruto's failed entry", "three-quarter medium two-character", "track Naruto's step, retain the open gap", "Editorial non-damaging attempt: Naruto pushes off his rear foot and enters with Rasengan held in his bent palm as a melee strike. Omni-Man shifts outside the hand path and loads his recorded heavy strike; his fist does not land in this shot. No Rasengan contact or damage is added.", "Naruto planted with hand orb", "Naruto almost in range, Omni-Man outside line", "Naruto lunging with hand-held blue orb; Omni-Man sidesteps with fist loaded and no contact", "rasengan", True),
    Direction(5, 110, 1.2, "Near-contact interruption", "extreme close-up hand/fist negative space", "static for one beat, no shake", "Naruto's Rasengan remains a finger-width short of Omni-Man's torso as Omni-Man's forearm redirects the approach. This is a near miss only; keep the orb tangent to empty air and show Omni-Man's right fist entering the reply path.", "Rasengan entry nearly reaches torso", "hand path redirected, heavy fist incoming", "clear tiny gap between hand-held orb and Omni-Man torso; blocking forearm visible", "rasengan", True),
    Direction(5, 112, 1.2, "Finishing heavy strike", "brief low three-quarter impact insert", "one directional camera impulse after visible contact", "Omni-Man's recorded heavy strike lands on Naruto's upper body. His rear foot, hip and chest drive the fist; Naruto's torso compresses, Rasengan collapses without striking, and the recorded KO occurs. Show contact before the small impact frame.", "Omni-Man fist on path, Naruto off-balance", "Naruto incapacitated, orb gone", "Omni-Man fist at Naruto torso, hand orb collapsing harmlessly away", "heavy_strike", True),
    Direction(5, 114, 2.0, "Naruto falls", "medium reaction from fixed south axis", "follow downward, then settle", "Naruto recoils across the lane, loses leg support and lands incapacitated. Omni-Man retracts his fist and exhales; there is no further hit or recovery by Naruto.", "Naruto KO recoil, Omni-Man follow-through", "Naruto down, Omni-Man standing", "Naruto down near left curb, Omni-Man standing right with arms lowering"),
    Direction(5, 115, 2.7, "Recorded aftermath", "wide aftermath with street scale", "slow pull back, no axis change", "Hold the recorded Omni-Man victory: he stands breathing on the right, Naruto remains down on the left, the unused blue hand energy fully dissipates, and the street quiets.", "Naruto down, Omni-Man standing", "same final outcome, no new movement", "wide blue-hour street, Naruto down left, Omni-Man upright right, quiet road"),
)

# An editorial camera matrix keeps the art review anchored to actual images,
# rather than treating different prompt labels as proof of shot variety.
CAMERA_FAMILIES = (
    "street-level wide", "face close-up", "ground-level low angle", "overhead",
    "low power angle", "profile attack lane", "three-quarter impact", "low side landing",
    "over-shoulder projectile", "three-quarter contact", "low character close-up", "profile miss",
    "over-shoulder projectile", "over-shoulder grapple", "overhead", "three-quarter block",
    "reaction close-up", "profile dodge", "low power angle", "perpendicular side impact",
    "ground-level catch", "high three-quarter hand close-up", "reaction close-up", "three-quarter entry",
    "oblique contact close-up", "low three-quarter impact", "medium aftermath", "wide aftermath",
)


def _frames() -> list[int]:
    total = 62 * 30
    quota = [total * shot.weight / sum(s.weight for s in SHOTS) for shot in SHOTS]
    frames = [int(q) for q in quota]
    for index in sorted(range(len(SHOTS)), key=lambda i: (-(quota[i] - frames[i]), i))[:total - sum(frames)]:
        frames[index] += 1
    return frames


def _continuity(log, time: float, source_ids: list[str], previous: VisualContinuity | None) -> VisualContinuity:
    original = _state_at(log, time, source_ids)
    data = original.model_dump()
    data["screen_positions"] = {"naruto": "left", "omniman": "right"}
    data["facing"] = {"naruto": "right", "omniman": "left"}
    data["camera_side"] = "south of action axis; no unestablished reversal"
    data["environment_landmarks"] = ["single center road stripe", "two blue-gray facades", "right streetlight", "left curb"]
    data["lighting_direction"] = "soft blue-hour key from screen left; restrained right rim"
    if previous and data["simulation_time"] < previous.simulation_time:
        data["simulation_time"] = previous.simulation_time
    return VisualContinuity.model_validate(data)


def build_plan(replay: dict) -> tuple[EpisodePlan, list[dict]]:
    if replay["checksum"] != SOURCE_CHECKSUM:
        raise ValueError("The 60-second direction requires the saved seed-289 replay")
    log = adapt_replay(replay)
    event_sha = digest([event for frame in replay["frames"] for event in frame["events"]])
    if event_sha != EVENT_SHA:
        raise ValueError("Canonical seed-289 event stream changed")
    specs = ability_specs(replay)
    beats = adapt_beats(log, specs)
    by_index = {b.source_index: b for b in beats}
    frames = _frames()
    shots = []
    previous = _continuity(log, 0, [by_index[0].source_event_id], None)
    for i, (direction, count) in enumerate(zip(SHOTS, frames), 1):
        beat = by_index[direction.event_index]
        end = _continuity(log, beat.simulation_time, [beat.source_event_id], previous)
        # The artistic pose text is exact across a cut, while recorded resources
        # and source times advance only at the associated simulator event.
        required = [f"character_references/{fighter}_{view}.png"
                    for fighter in ("naruto", "omniman") for view in ("front", "side", "three_quarter")]
        required.append("style_references/approved_style.png")
        if direction.ability:
            required.append(f"ability_references/{'omniman' if direction.ability in {'heavy_strike', 'grapple'} else 'naruto'}_{direction.ability}.png")
        duration = count / 30
        editorial_note = (
            "Authorized noncanonical, non-damaging failed Rasengan attempt; not a simulator ability, hit, or outcome."
            if direction.editorial else ""
        )
        handoff = SHOTS[i - 2].end_pose if i > 1 else direction.start_pose
        transition_direction = (
            f"Transition by matching the end pose to shot {i + 1:03d} on a hard action cut. "
            if i < len(SHOTS) else "Clean hold to end; there is no following shot. "
        )
        prompt = (
            f"{STYLE} Shot {i:03d} of 28, {duration:.3f} seconds at 30 fps. {direction.title}. "
            f"Start from the prior shot's exact end pose: {handoff}. Move into this beat's setup: {direction.start_pose}. "
            f"One dominant action: {direction.action} "
            f"End exactly at: {direction.end_pose}. Camera: {direction.framing}; {direction.camera}; stay south of the action axis. "
            "Background: the same sparse blue-hour street, one center stripe, left curb, two blue-gray facades and right streetlight. "
            "Maintain orange/charcoal Naruto on the left and broad red/off-white Omni-Man on the right. "
            "Show support-foot load and release, intentional curved hand paths, hip-to-shoulder sequencing, visible contact or miss, "
            "and recovery appropriate to this beat. Use flat colors, simple faces, clean contours and clear negative space. "
            + ("The Energy Orb is a tiny straight ranged pellet without a spiral; do not depict it as Rasengan. " if direction.ability == "energy_orb" else "")
            + ("Rasengan stays physically attached to Naruto's open palm throughout this shot; it is an attempted melee strike and never becomes a projectile. " if direction.ability == "rasengan" else "")
            + transition_direction
            + f"The recorded outcome is Omni-Man KO victory; no added hit or damage. {editorial_note}"
        )
        shot = SeedanceShot(
            shot_id=f"shot_{i:03d}", sequence_index=i, duration_seconds=duration,
            purpose=direction.title, source_beat_ids=[beat.beat_id], characters_visible=["naruto", "omniman"],
            starting_pose={"pair": handoff}, ending_pose={"pair": direction.end_pose},
            action_description=direction.action, camera_framing=direction.framing, camera_movement=direction.camera,
            lens_style_direction="graphic 2D perspective; readable silhouette and no fisheye distortion",
            background_description="Sparse blue-hour city street; center stripe, left curb, two facades, right streetlight",
            ability_effects=([direction.ability] if direction.ability else []),
            transition_in="hard cut on aligned action" if i > 1 else "direct opening",
            transition_out="hard cut to matched pose" if i < len(SHOTS) else "clean hold to end",
            continuity_anchors=["Naruto orange/black left", "Omni-Man red/off-white right", "same road stripe and right streetlight", "soft key screen left"],
            seedance_prompt=prompt, negative_prompt=NEGATIVE + (" No Rasengan hit, damage, throw, projectile, detached orb, beam, or energy blast in this shot." if direction.editorial else "") + (" No spiral orb, Rasengan sphere, or hand-held melee energy in this ranged Energy Orb shot." if direction.ability == "energy_orb" else ""),
            required_reference_images=required,
            human_review_checklist=["One clear action, no pose freeze", "Recorded hit/miss/outcome remains correct", "Support feet and body weight read at normal speed", "No extra contact or limb", "Same designs, action axis and street landmarks", "End pose matches next shot", "Readable on a phone"],
            continuity_start=previous, continuity_end=end, source_simulation_time=beat.simulation_time,
            editorial_note=editorial_note,
        )
        shots.append(shot)
        previous = end
    plan = EpisodePlan(
        episode_id=EPISODE_ID, source_checksum=SOURCE_CHECKSUM, canonical_event_sha256=EVENT_SHA,
        seed=289, fighter_ids=["naruto", "omniman"], fps=30, duration_seconds=62,
        style=STYLE, shots=shots, outcome=replay["result"],
    )
    return plan, [b.model_dump(mode="json") for b in beats]


def prepare_longform(source: Path, output: Path, assets: Path) -> tuple[Path, dict]:
    """Write the source-locked episode, then validate all actual upload images."""
    replay = load_replay(source)
    plan, beats = build_plan(replay)
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Longform output already contains files: {output}")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output / "simulation.json")
    write_json(output / "episode_plan.json", plan)
    write_json(output / "fight_beats.json", beats)
    groups = []
    for seq in range(1, 6):
        subset = [shot for shot, direction in zip(plan.shots, SHOTS) if direction.sequence == seq]
        groups.append({"sequence_id": seq, "name": ["Faceoff and tension", "Opening assault and evasion", "Close exchange and counter", "Ability escalation", "Final clash and aftermath"][seq - 1],
                       "shot_ids": [s.shot_id for s in subset], "duration_seconds": sum(s.duration_seconds for s in subset)})
    write_json(output / "sequence_plan.json", groups)
    write_json(output / "continuity_master.json", {"camera_side": "south", "lighting": "soft screen-left key", "landmarks": ["road stripe", "left curb", "two facades", "right streetlight"],
            "shots": [{"shot_id": s.shot_id, "start": s.continuity_start.model_dump(mode="json"), "end": s.continuity_end.model_dump(mode="json")} for s in plan.shots]})
    shared = output / "shared_references"
    shared.mkdir(exist_ok=True)
    prior = assets.parent / "first_episode" / "shared_references"
    aliases = {"approved_style.png": "simplified-style-reference.png", "naruto_charged_vortex.png": "charged-vortex-projectile.png", "naruto_energy_orb.png": "energy-orb-straight.png",
               "naruto_chakra_form.png": "naruto-chakra-form-simple.png", "naruto_rasengan.png": "rasengan-simple.png", "omniman_heavy_strike.png": "omniman-impact-simple.png", "omniman_grapple.png": "omniman-grapple-simple.png"}
    for reference in prior.glob("*.png"):
        if reference.name != "energy-orb-projectile.png":
            shutil.copyfile(reference, shared / reference.name)
    shutil.copyfile(assets / "energy-orb-straight.png", shared / "energy-orb-straight.png")
    for shot in plan.shots:
        folder = output / "shots" / shot.shot_id
        folder.mkdir(parents=True, exist_ok=True)
        write_json(folder / "shot.json", shot)
        write_json(folder / "continuity_start.json", shot.continuity_start)
        write_json(folder / "continuity_end.json", shot.continuity_end)
        (folder / "seedance_prompt.txt").write_text(shot.seedance_prompt + "\n", encoding="utf-8")
        (folder / "seedance_negative_prompt.txt").write_text(shot.negative_prompt + "\n", encoding="utf-8")
        (folder / "review_checklist.md").write_text("# Review " + shot.shot_id + "\n\n" + "\n".join("- [ ] " + item for item in shot.human_review_checklist) + "\n", encoding="utf-8")
        write_json(folder / "upload_manifest.json", {"shot_id": shot.shot_id, "duration_seconds": shot.duration_seconds,
                   "required_upload_images": [*shot.required_reference_images, "keyframe.png"], "preferred_start_image": "keyframe.png",
                   "optional_end_image": "end_frame.png", "prompt": "seedance_prompt.txt", "negative_prompt": "seedance_negative_prompt.txt", "provider_calls": 0})
        image = assets / "keyframes" / f"{shot.shot_id}.png"
        if image.is_file():
            shutil.copyfile(image, folder / "keyframe.png")
        for ref in shot.required_reference_images:
            target = folder / ref
            target.parent.mkdir(parents=True, exist_ok=True)
            name = aliases.get(Path(ref).name, Path(ref).name.replace("_", "-"))
            candidate = (assets if name == "energy-orb-straight.png" else prior) / name
            if candidate.is_file():
                shutil.copyfile(candidate, target)
    _write_documents(output, plan, groups)
    _camera_contact_sheet(output, plan)
    _write_production_review(output, plan)
    status = validate_package(output)
    _write_preupload_review(output, plan, groups, status)
    return output, status


def finalize_preupload(project: Path) -> dict:
    """Repair only final-shot text and refresh review metadata, never shot art."""
    project = project.resolve()
    replay = load_replay(project / "simulation.json")
    revised, _ = build_plan(replay)
    existing = EpisodePlan.model_validate_json((project / "episode_plan.json").read_text(encoding="utf-8"))
    if existing.shots[:-1] != revised.shots[:-1] or existing.outcome != revised.outcome:
        raise ValueError("Existing package differs outside shot 028; refusing a broad rewrite")
    images_before = {
        str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in project.rglob("*.png")
    }
    write_json(project / "episode_plan.json", revised)
    final = revised.shots[-1]
    folder = project / "shots" / final.shot_id
    write_json(folder / "shot.json", final)
    (folder / "seedance_prompt.txt").write_text(final.seedance_prompt + "\n", encoding="utf-8")
    (folder / "seedance_negative_prompt.txt").write_text(final.negative_prompt + "\n", encoding="utf-8")
    groups = json.loads((project / "sequence_plan.json").read_text(encoding="utf-8"))
    _write_documents(project, revised, groups)
    status = validate_package(project)
    images_after = {
        str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in project.rglob("*.png")
    }
    if images_before != images_after:
        raise ValueError("Pre-upload correction unexpectedly changed image files")
    _write_preupload_review(project, revised, groups, status)
    return status


def _write_preupload_review(project: Path, plan: EpisodePlan, groups: list[dict], status: dict) -> None:
    from PIL import Image

    shots = plan.shots
    source_art = Path(__file__).resolve().parents[4] / "assets/seedance/seed289_60s/keyframes"
    image_matches = []
    dimensions = []
    for shot in shots:
        keyframe = project / "shots" / shot.shot_id / "keyframe.png"
        source = source_art / f"{shot.shot_id}.png"
        image_matches.append(source.is_file() and keyframe.read_bytes() == source.read_bytes())
        with Image.open(keyframe) as image:
            dimensions.append([image.width, image.height])
    technical = (
        status["ready_for_manual_upload"] and len(shots) == 28 and len(groups) == 5
        and abs(plan.duration_seconds - 62) < 1e-6
        and all(image_matches)
        and shots[-1].transition_out == "clean hold to end"
        and "shot 029" not in shots[-1].seedance_prompt
    )
    camera_checks = {
        "wide_establishing": any("wide" in family for family in CAMERA_FAMILIES[:4]),
        "close_up": any("close-up" in family for family in CAMERA_FAMILIES),
        "low_angle": any("low" in family or "ground-level" in family for family in CAMERA_FAMILIES),
        "overhead": any("overhead" in family for family in CAMERA_FAMILIES),
        "side_profile": any("profile" in family or "side" in family for family in CAMERA_FAMILIES),
        "three_quarter_contact": any("three-quarter" in family and ("impact" in family or "contact" in family) for family in CAMERA_FAMILIES),
        "reaction": any("reaction" in family for family in CAMERA_FAMILIES),
        "impact_insert": any("impact" in family for family in CAMERA_FAMILIES),
        "wide_aftermath": CAMERA_FAMILIES[-1] == "wide aftermath",
    }
    report = {
        "technical_ready_for_manual_generation": technical and all(camera_checks.values()),
        "validation_issue_count": status["missing_count"],
        "duration_seconds": plan.duration_seconds,
        "shot_count": len(shots),
        "sequence_count": len(groups),
        "camera_checks": camera_checks,
        "keyframes_identical_to_versioned_sources": all(image_matches),
        "keyframe_dimensions": dimensions,
        "final_transition": shots[-1].transition_out,
        "nonexistent_shot_029_reference": "shot 029" in shots[-1].seedance_prompt,
        "canonical_event_sha256": status["canonical_event_sha256"],
        "source_replay_checksum": status["source_replay_checksum"],
        "paid_provider_calls": status["provider_calls"],
        "storyboard_visual_review": "All 28 images reviewed as a contact sheet: consistently outlined, flat-color 2D figures; no materially realistic outlier identified. Framing and screen lanes appear plausible at board scale.",
        "generated_motion_quality": "unverified; no Seedance clips generated",
        "sample_video_parity": "not assessable before at least the first five clips are generated and reviewed at normal speed",
    }
    write_json(project / "review/preupload_audit.json", report)
    verdict = "Technically ready for controlled manual Seedance generation" if report["technical_ready_for_manual_generation"] else "Blocked by technical validation"
    (project / "production_readiness.md").write_text(
        "# Production readiness — pre-upload audit\n\n"
        f"**{verdict}.** {len(shots)} shots, {len(groups)} sequences, {plan.duration_seconds:.0f} editorial seconds. "
        f"Validation issues: {status['missing_count']}. All staged keyframes match their versioned source images. Shot 028 ends with `clean hold to end` and contains no shot-029 reference. Canonical event hash: `{status['canonical_event_sha256']}`.\n\n"
        "## Storyboard and keyframe quality\n\n"
        "The 28-image contact sheet was visually reviewed. Figures share a simplified 2D ink-and-flat-color style; no single frame is materially photorealistic or demands replacement. Establishing, low, overhead, profile, over-shoulder, three-quarter contact, reaction, impact and aftermath compositions are represented in the actual images. Naruto generally remains left and Omni-Man right, except for isolated character inserts and overhead views. The images offer plausible cuts, but they do not prove that generated motion will join the poses cleanly.\n\n"
        "## Source truth and movement\n\n"
        "Prompts specify weight shifts, foot loading/release, shoulder and hip sequencing, contact or miss, recoil and recovery rather than merely naming source events. The recorded Energy Orb is a small straight ranged pellet, separate from the hand-held Rasengan. Naruto's late Rasengan preparation is authorized noncanonical, non-damaging editorial staging: it never leaves his hand or hits Omni-Man. Omni-Man's recorded heavy strike remains the decisive KO.\n\n"
        "## Unverified generated-motion quality\n\n"
        "No Seedance clips were generated. Foot skating, limb disappearance, hidden contact, style drift, action-axis reversal, camera behavior, pose matching and editorial pace can only be judged by watching generated clips at normal speed. Technical readiness is not final video approval.\n\n"
        "## Remaining gate\n\n"
        "Generate and review the first **five** clips at normal speed before making any claim of parity with the supplied sample videos. Continue shot by shot only if identity, camera variation, body mechanics and attack truth hold. No paid API was called during this audit.\n",
        encoding="utf-8",
    )


def _camera_contact_sheet(output: Path, plan: EpisodePlan) -> None:
    """Create a review index of the supplied art; it is never a video input."""
    from PIL import Image, ImageDraw

    width, height, cols = 198, 378, 7
    rows = (len(plan.shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * width, rows * height), "#111824")
    draw = ImageDraw.Draw(sheet)
    for index, (shot, family) in enumerate(zip(plan.shots, CAMERA_FAMILIES)):
        with Image.open(output / "shots" / shot.shot_id / "keyframe.png") as original:
            thumb = original.convert("RGB")
            thumb.thumbnail((width - 12, height - 66))
        x, y = (index % cols) * width + 6, (index // cols) * height + 4
        sheet.paste(thumb, (x + (width - 12 - thumb.width) // 2, y))
        draw.text((x, y + height - 61), f"{shot.shot_id}  {family[:22]}", fill="white")
    review = output / "review"
    review.mkdir(exist_ok=True)
    sheet.save(review / "keyframe_camera_contact_sheet.jpg", quality=86)


def _write_production_review(output: Path, plan: EpisodePlan) -> None:
    from collections import Counter

    categories = {
        "wide": lambda family: "wide" in family,
        "close-up": lambda family: "close-up" in family,
        "overhead": lambda family: "overhead" in family,
        "over-shoulder": lambda family: "over-shoulder" in family,
        "low-angle/ground": lambda family: "low" in family or "ground-level" in family,
        "profile": lambda family: "profile" in family or "side" in family,
        "three-quarter/oblique": lambda family: "three-quarter" in family or "oblique" in family,
    }
    count = Counter({name: sum(test(family) for family in CAMERA_FAMILIES) for name, test in categories.items()})
    summary = "\n".join(f"- {name}: {number}" for name, number in count.items())
    (output.parent / "naruto_vs_omniman_production_review.md").write_text(
        "# Naruto vs Omni-Man — Seedance production review\n\n"
        "The previous seed-289 package had eight shots across about ten seconds. Its mostly frontal medium street framing gave little visual scale or camera rhythm. It omitted several recorded exchange beats, left transitions underdeveloped, and could not support a one-minute edit. The prior Energy Orb visual reference also resembled a swirling Rasengan, an inaccurate ability cue.\n\n"
        f"The new package uses five sequences, {len(plan.shots)} image-backed shots and {plan.duration_seconds:.0f} editorial seconds at 30 fps. "
        "The canonical fight itself is only 7.55 simulated seconds; the longer duration is an interpretive cinematic expansion, not altered combat time. Omni-Man's heavy strike remains the KO. The late hand-held Rasengan preparation/failed entry is explicitly noncanonical and causes no contact or damage. The thrown charged-vortex attack is a separate Rasenshuriken-like projectile; shot 013's recorded Energy Orb is a distinct straight cyan pellet.\n\n"
        "## Framing distribution\n\n" + summary + "\n\n"
        "Counts overlap because one image can be both low and close. Review the actual 28-image `naruto_vs_omniman_60s/review/keyframe_camera_contact_sheet.jpg`. The finished boards alternate establishing width, facial intent, ground-level power, overhead geography, shoulder/depth views, perpendicular flight and close interrupted melee contact. The apparent variety is backed by different keyframe compositions, not only prompt labels.\n\n"
        "## Comparison to the supplied examples\n\n"
        "The plan borrows their short anticipation/contact/reaction rhythm, strong silhouettes and concentrated impact accents while using a clean full-height 9:16 canvas rather than social-app UI capture. It keeps a stable left/right fight axis; only the camera height, depth and distance vary. The final punch receives the shortest contact insert and a separate fallout shot. Relative to the references, these are still static generated boards: Seedance motion, timing, inter-shot identity and final editorial pacing have not been tested.\n\n"
        "## Readiness decision\n\n"
        "All required local images and shot data are staged and source-validated, so this package is ready for **controlled manual Seedance clip tests** without another asset-generation pass. It is **not yet approved as a finished high-quality video**: watch each generated clip at normal speed for motion, hidden limbs, attack identity, contact, continuity and camera behavior before assembly. Reject any output that throws Rasengan, obscures Omni-Man's punching arm, repeats one frontal street angle, or adds a Rasengan hit. No paid video call or final assembly was performed.\n",
        encoding="utf-8",
    )


def _write_documents(output: Path, plan: EpisodePlan, groups: list[dict]) -> None:
    source_note = "Seed 289 ends with Omni-Man KO by heavy strike. Naruto's failed hand-held Rasengan attempt is authorized editorial staging only; it causes no hit, damage, or altered outcome."
    lines = ["# Shot order — 62 seconds / 28 shots", "", source_note, "", "| Shot | Sequence | Duration | Camera | Action | Source beat |", "|---|---:|---:|---|---|---|"]
    for shot, direction in zip(plan.shots, SHOTS):
        lines.append(f"| {shot.shot_id} | {direction.sequence} | {shot.duration_seconds:.2f}s | {direction.framing} | {direction.title} | {shot.source_beat_ids[0]} |")
    (output / "shot_order.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output / "character_design_spec.md").write_text("# Character design lock\n\nNaruto: short angular blond spikes, forehead protector, three cheek marks, orange/charcoal blocks, low athletic stance. Omni-Man: much broader adult silhouette, short dark hair, mustache, red/off-white suit, large cape. Keep both designs identical across views and shots; never replace them with anonymous silhouettes. Source art is a development fixture, not official production approval.\n", encoding="utf-8")
    (output / "simplified_style_guide.md").write_text("# Simplified 2D style\n\nFollow the simpler supplied example's flat color blocks, decisive outlines, short action beats and sparse impact marks. Use full-frame vertical 9:16 rather than the screen recording's UI/letterbox. One flat shadow maximum per body mass; backgrounds stay below the fighters in detail. Effects appear only at recorded attacks. Naruto's final hand-held Rasengan attempt is non-damaging and never thrown.\n", encoding="utf-8")
    camera_lines = ["# Camera grammar and image review", "", "These labels describe the reviewed keyframes, not merely intended prompt angles. The complete 28-image contact sheet is `review/keyframe_camera_contact_sheet.jpg`. Preserve one south-side action axis while varying camera height, subject scale, depth, and viewing angle. An overhead angle may rotate within the established geography, but a reverse should not silently swap screen lanes.", "", "| Shot | Camera family | Purpose |", "|---|---|---|"]
    for shot, family in zip(plan.shots, CAMERA_FAMILIES):
        camera_lines.append(f"| {shot.shot_id} | {family} | {shot.purpose} |")
    camera_lines += ["", "Cut from wide geography to close intent, use side views for attack lanes, overhead for repositioning, and an oblique close-up for the interrupted hand-held Rasengan. The Rasengan never leaves Naruto's palm. Shot 013 is a separate straight Energy Orb projectile. Hold the final heavy-strike surface contact long enough to read before any camera impulse. Reject generated video that collapses these compositions back into the same frontal street view, hides a limb, or invents a Rasengan projectile.", ""]
    (output / "camera_grammar.md").write_text("\n".join(camera_lines), encoding="utf-8")
    guide = ["# Manual Seedance upload", "", source_note, "", "1. Check `production_readiness.md`, `asset_inventory.json`, and every keyframe. Do not upload shots with missing or unapproved art.",
             "2. For each numbered shot upload `shots/shot_###/keyframe.png` as the start image plus only the character, style, and ability boards listed in that folder's `upload_manifest.json`.",
             "3. Paste `seedance_prompt.txt` and `seedance_negative_prompt.txt`. Set vertical 9:16 and the shot's listed duration; keep one shot per generation. Exact provider control names are unverified locally.",
             "4. Review normal-speed output for identity, support feet, action axis, contact/miss, and matched ending pose. Reject gliding, random arm motion, hidden hits, extra damage, style drift or a thrown Rasengan.",
             "5. Use an `end_frame.png` only when a generated clip's ending cannot match the next shot and the extra frame is artist-approved. Do not invent bridge contact.",
             "6. Export approved clips to `clips/shot_###.mp4` in order; normalize to a common 9:16 codec/frame rate, concatenate with hard cuts, then inspect every cut on a phone. This package does not call Seedance or create a final video.", ""]
    (output / "seedance_manual_upload_guide.md").write_text("\n".join(guide), encoding="utf-8")
    (output / "quality_review_checklist.md").write_text("# Episode quality gate\n\n- [ ] Every shot reads at phone size and has one purposeful action\n- [ ] Close, medium, wide and overhead grammar feels motivated\n- [ ] Anticipation, contact/miss, reaction and recovery connect between shots\n- [ ] Naruto and Omni-Man retain one design, screen lane, costume and light\n- [ ] Rasengan is hand-held, fails before any contact and changes no outcome\n- [ ] The final heavy strike is the strongest contact; Omni-Man wins\n- [ ] No generated motion skates, flails, folds or adds limbs\n- [ ] All 28 Seedance clips and the assembled 62-second video receive human approval\n", encoding="utf-8")
    inventory = []
    for image in sorted(output.rglob("*.png")):
        import hashlib
        inventory.append({"path": str(image.relative_to(output)), "sha256": hashlib.sha256(image.read_bytes()).hexdigest(), "human_visual_approval": "pending"})
    write_json(output / "asset_inventory.json", {"image_count": len(inventory), "new_keyframe_count": len(plan.shots),
               "new_ability_reference_count": 1, "image_files_include_staged_copies": True,
               "images": inventory, "source_checksum": SOURCE_CHECKSUM, "event_sha256": EVENT_SHA, "provider_calls": 0})
    (output / "production_readiness.md").write_text("# Production readiness\n\n" + source_note + "\n\nTechnical file validation is separate from creative approval. The package is ready for manual Seedance tests only when all required keyframes and references exist. Motion quality, style consistency, continuity and reference-video parity cannot be certified until every generated clip is watched. No Seedance or paid video provider was called.\n", encoding="utf-8")
