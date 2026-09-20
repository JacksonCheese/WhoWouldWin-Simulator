"""Coverage edits: multiple perspectives of an existing event, not extra combat."""

import json
from pathlib import Path
from whowouldwin.simulation.replay import digest
from whowouldwin.cinematic.episodes.schemas import (
    Shot,
    ShotList,
    ShotType,
    GoldenDirectorSettings,
    EditorialEffects,
    Point,
)
from whowouldwin.cinematic.episodes.continuity import ContinuityTracker
from whowouldwin.cinematic.episodes.visual_bibles import data_directory
from .schemas import AbilityVisualProfile, CinematicCoverageTemplate, CoverageBeat


def load_abilities(log, directory: Path | None = None):
    result = {}
    for fighter in dict.fromkeys(log.fighter_profile_ids.values()):
        path = (directory or data_directory() / "ability_visuals") / f"{fighter}.json"
        for raw in json.loads(path.read_text()):
            profile = AbilityVisualProfile.model_validate(raw)
            if profile.fighter_profile_id != fighter:
                raise ValueError("Ability visual profile fighter mismatch")
            key = (fighter, profile.simulation_ability_id)
            if key in result:
                raise ValueError(f"Duplicate ability mapping: {key}")
            result[key] = profile
    used = {
        (log.fighter_profile_ids[e.actor_id], e.ability_id)
        for e in log.events
        if e.actor_id
        and e.ability_id
        and e.ability_id != "rest"
        and e.event_type in {"ActionChosen", "AbilityStarted", "AttackStarted"}
    }
    missing = used - result.keys()
    if missing:
        raise ValueError(f"Missing explicit ability visual mappings: {sorted(missing)}")
    return result


def beat(role, seconds, framing, angle, motion, phase):
    return CoverageBeat(
        role=role,
        seconds=seconds,
        framing=framing,
        angle=angle,
        motion=motion,
        phase=phase,
    )


TEMPLATES = {
    "POWER_ATTACK": [
        beat(
            "anticipation",
            0.9,
            "hands and face",
            "low three-quarter",
            "slow push toward hands",
            "before",
        ),
        beat(
            "action",
            1.1,
            "diagonal medium action",
            "three-quarter",
            "fast tracking beside the attacker",
            "before",
        ),
        beat(
            "impact",
            0.5,
            "tight contact insert",
            "oblique close",
            "brief handheld impact then settle",
            "contact",
        ),
        beat(
            "consequence",
            1.2,
            "target recoil",
            "high angle",
            "follow the recorded recoil",
            "after",
        ),
    ],
    "SPEED_BLITZ": [
        beat("reaction", 0.8, "defender eyes", "eye level", "sharp push-in", "before"),
        beat(
            "rapid_approach",
            1,
            "body driving toward lens",
            "low angle",
            "high-speed follow camera",
            "before",
        ),
        beat(
            "impact",
            0.45,
            "single contact",
            "oblique close",
            "handheld contact jolt",
            "contact",
        ),
        beat(
            "knockback",
            1.3,
            "recorded recoil",
            "wide diagonal",
            "track the recoil",
            "after",
        ),
    ],
    "HEAVY_COUNTER": [
        beat(
            "commitment",
            0.9,
            "attacker shoulder and fist",
            "over shoulder",
            "track the committed strike",
            "before",
        ),
        beat(
            "defender_response",
            0.8,
            "defender face",
            "eye level",
            "quick reverse angle",
            "before",
        ),
        beat(
            "impact",
            0.5,
            "single contact",
            "low oblique",
            "short contact jolt",
            "contact",
        ),
        beat(
            "attacker_reaction",
            1.2,
            "attacker recovery",
            "medium close",
            "ease into a hold",
            "after",
        ),
    ],
    "TRANSFORMATION": [
        beat(
            "detail",
            0.8,
            "eyes and aura detail",
            "extreme close-up",
            "controlled push-in",
            "before",
        ),
        beat(
            "medium_reveal",
            1.7,
            "torso and spreading aura",
            "low angle",
            "sweeping half orbit",
            "contact",
        ),
        beat(
            "wide_power",
            2.1,
            "full form reveal",
            "wide low angle",
            "slow pull back",
            "after",
        ),
    ],
    "FINISHER": [
        beat(
            "setup",
            1.1,
            "attacker bracing the final ability",
            "over shoulder",
            "controlled inward track",
            "before",
        ),
        beat(
            "attack_launch",
            1.1,
            "ability crossing toward opponent",
            "low three-quarter",
            "fast lateral tracking",
            "before",
        ),
        beat(
            "impact",
            0.5,
            "single decisive contact",
            "tight oblique",
            "brief impact jolt then hold",
            "contact",
        ),
        beat(
            "environmental_consequence",
            1.3,
            "fading effect against intact arena",
            "overhead",
            "overhead drift",
            "after",
        ),
        beat(
            "defeated_reaction",
            2.4,
            "defeated target portrait",
            "eye level",
            "slow descending close-up",
            "after",
        ),
        beat(
            "victory",
            2.4,
            "winner with persistent form",
            "low angle",
            "slow dramatic pull-back",
            "after",
        ),
    ],
    "DODGE": [
        beat(
            "incoming_threat",
            0.9,
            "incoming attack and target",
            "over shoulder",
            "track the incoming threat",
            "before",
        ),
        beat(
            "close_evasion",
            0.7,
            "defender slipping away",
            "tight three-quarter",
            "whip pan with the evasion",
            "contact",
        ),
        beat(
            "overshoot",
            1.2,
            "attacker passes the target line",
            "wide diagonal",
            "follow into empty space",
            "after",
        ),
    ],
}
TEMPLATES = {
    key: CinematicCoverageTemplate(template_id=key, beats=rows)
    for key, rows in TEMPLATES.items()
}


def select_window(
    log, moments, *, start_time=None, end_time=None, start_moment=None, end_moment=None
):
    by_id = {m.moment_id: m for m in moments}
    if start_moment:
        if start_moment not in by_id:
            raise ValueError(f"Unknown start moment: {start_moment}")
        start_time = by_id[start_moment].start_time
    if end_moment:
        if end_moment not in by_id:
            raise ValueError(f"Unknown end moment: {end_moment}")
        end_time = by_id[end_moment].end_time
    meaningful = [
        m
        for m in moments
        if m.moment_type not in {"faceoff", "outcome", "defeat", "form_expiry"}
    ]
    if not meaningful:
        raise ValueError("This replay has no major action for a golden sequence")
    if start_time is None:
        anchor = max(
            meaningful,
            key=lambda m: (m.moment_type == "finisher", m.importance_score, m.end_time),
        )
        previous = [
            m
            for m in meaningful
            if m.end_time < anchor.start_time
            and m.moment_type in {"hit", "special_hit"}
        ]
        start_time = previous[-1].start_time if previous else anchor.start_time
        end_time = anchor.end_time if end_time is None else end_time
        reason = "Highest-value finish with the preceding recorded offensive exchange; multiple views share the same contact IDs."
    else:
        end_time = (
            min(log.outcome["duration"], start_time + 3)
            if end_time is None
            else end_time
        )
        reason = "Explicit source-time/moment selection; no unrecorded events added."
    if not 0 <= start_time < end_time <= log.outcome["duration"]:
        raise ValueError(
            "Source interval must fall inside the completed fight and have positive length"
        )
    selected = [
        m for m in meaningful if m.end_time >= start_time and m.start_time <= end_time
    ]
    if not selected:
        raise ValueError("No cinematic moments in the selected source interval")
    return start_time, end_time, selected, reason


def visual_for(moment, log, abilities):
    events = {e.event_id: e for e in log.events}
    for key in moment.source_event_ids:
        e = events[key]
        if e.actor_id and e.ability_id:
            profile = abilities.get((log.fighter_profile_ids[e.actor_id], e.ability_id))
            if profile:
                return profile, e.actor_id, e.target_ids
    raise ValueError(
        f"{moment.moment_id} lacks explicit character-specific ability semantics"
    )


def template_for(moment, visual):
    if moment.moment_type == "finisher":
        return "FINISHER"
    if moment.moment_type == "transformation":
        return "TRANSFORMATION"
    if moment.moment_type == "dodge":
        return "DODGE"
    if visual.simulation_ability_id == "charge":
        return "SPEED_BLITZ"
    return "POWER_ATTACK"


def allocate_rhythm(beats, seconds, fps):
    # Scale an intentional rhythm, then distribute fractional frames without uniformizing it.
    total = sum(b.seconds for b in beats)
    values = [
        max(round(0.3 * fps), min(4 * fps, int(b.seconds / total * seconds * fps)))
        for b in beats
    ]
    delta = round(seconds * fps) - sum(values)
    order = sorted(range(len(beats)), key=lambda i: beats[i].seconds, reverse=True)
    while delta:
        changed = False
        for i in order:
            if delta > 0 and values[i] < 4 * fps:
                values[i] += 1
                delta -= 1
                changed = True
            elif delta < 0 and values[i] > round(0.3 * fps):
                values[i] -= 1
                delta += 1
                changed = True
            if not delta:
                break
        if not changed:
            raise ValueError("Requested rhythm does not fit shot duration bounds")
    return values


class GoldenDirector:
    def direct(self, log, moments, visuals, arena, abilities, settings):
        major = max(
            moments,
            key=lambda m: (
                m.moment_type == "finisher",
                m.moment_type == "transformation",
                m.importance_score,
            ),
        )
        visual, _, _ = visual_for(major, log, abilities)
        coverage = [(major, b) for b in TEMPLATES[template_for(major, visual)].beats]
        earlier = [m for m in moments if m.end_time < major.start_time]
        later = [m for m in moments if m.start_time > major.end_time]
        if earlier:
            coverage.insert(
                0,
                (
                    earlier[-1],
                    beat(
                        "preceding_exchange",
                        1.2,
                        "single preceding strike, both silhouettes",
                        "three-quarter",
                        "fast tracking into contact",
                        "contact",
                    ),
                ),
            )
        if len(coverage) < 4 and later:
            v, _, _ = visual_for(later[0], log, abilities)
            coverage.extend(
                (later[0], b) for b in TEMPLATES[template_for(later[0], v)].beats
            )
        elif major.moment_type == "transformation" and later:
            coverage.extend((later[0], b) for b in TEMPLATES["POWER_ATTACK"].beats)
        while len(coverage) < settings.shot_count:
            at = 0 if coverage[0][1].phase == "before" else len(coverage) - 1
            m = coverage[at][0]
            coverage.insert(
                at,
                (
                    m,
                    beat(
                        "dramatic_detail",
                        1.8,
                        "expressive character detail",
                        "eye level",
                        "static dramatic composition",
                        coverage[at][1].phase,
                    ),
                ),
            )
        while len(coverage) > settings.shot_count:
            removable = next(
                (
                    i
                    for i, (m, b) in enumerate(coverage)
                    if b.role
                    in {
                        "environmental_consequence",
                        "wide_power",
                        "preceding_exchange",
                        "consequence",
                        "dramatic_detail",
                    }
                ),
                1,
            )
            coverage.pop(removable)
        frames = allocate_rhythm(
            [b for _, b in coverage], settings.duration_seconds, settings.fps
        )
        tracker = ContinuityTracker(log, visuals, arena)
        shots = []
        clock = 0
        for i, ((m, b), count) in enumerate(zip(coverage, frames)):
            v, actor, targets = visual_for(m, log, abilities)
            clock = max(
                clock,
                (
                    m.start_time - log.state_timeline[1].simulation_time
                    if b.phase == "before"
                    else m.end_time
                ),
            )
            continuity = tracker.at(max(0, clock))
            if (
                v.form_requirements
                and continuity.characters[actor].transformation
                not in v.form_requirements
            ):
                raise ValueError(
                    f"Visual mapping form requirement not met: {v.ability_visual_id}"
                )
            subjects = list(dict.fromkeys([actor, *targets]))
            if (
                b.role
                in {
                    "reaction",
                    "defender_response",
                    "defeated_reaction",
                    "close_evasion",
                }
                and targets
            ):
                subjects = targets[:1]
            elif b.role in {
                "victory",
                "detail",
                "medium_reveal",
                "wide_power",
                "dramatic_detail",
            }:
                subjects = [actor]
            types = {
                "impact": ShotType.IMPACT,
                "victory": ShotType.VICTORY,
                "defeated_reaction": ShotType.REACTION,
                "environmental_consequence": ShotType.ENVIRONMENTAL,
                "detail": ShotType.EXTREME_CLOSE_UP,
                "medium_reveal": ShotType.TRANSFORMATION,
                "wide_power": ShotType.LOW_ANGLE,
                "setup": ShotType.OVER_SHOULDER,
            }
            kind = types.get(
                b.role,
                (
                    ShotType.WIDE_ACTION
                    if b.role in {"preceding_exchange", "overshoot"}
                    else ShotType.MEDIUM_ACTION
                ),
            )
            action = (
                v.windup_description
                if b.phase == "before"
                else (
                    v.impact_description
                    if b.phase == "contact"
                    else v.movement_description
                )
            )
            if b.role == "defeated_reaction":
                action = f"{log.fighter_names[targets[0]]} is defeated at the last recorded location; slack posture, no new injury."
            if b.role == "victory":
                action = f"{log.fighter_names[actor]} holds the recorded winning pose with the same costume and active form."
            if b.role == "environmental_consequence":
                action = "The existing effect dissipates above the intact rooftop; no additional damage or structural destruction."
            if m.moment_type == "dodge":
                action = f"{log.fighter_names[targets[0]]} avoids the incoming attack; no contact occurs."
            if b.role in {
                "preceding_exchange",
                "attack_launch",
                "action",
                "rapid_approach",
            }:
                action = v.action_description
            shots.append(
                Shot(
                    shot_id=f"shot-{i+1:03d}",
                    sequence_index=i,
                    source_moment_ids=[m.moment_id],
                    source_event_ids=m.source_event_ids,
                    simulation_start=m.start_time,
                    simulation_end=m.end_time,
                    duration_seconds=count / settings.fps,
                    frame_count=count,
                    shot_type=kind,
                    framing=b.framing,
                    camera_angle=b.angle,
                    camera_motion=b.motion,
                    subjects=subjects,
                    subject_positions={
                        s: Point(x=0.35 + j * 0.35, y=0.55 - j * 0.12)
                        for j, s in enumerate(subjects)
                    },
                    action_description=action,
                    environment_description=arena.description,
                    continuity_state=continuity,
                    keyframe_prompt="",
                    motion_prompt="",
                    negative_constraints=v.prohibited_visual_changes
                    + v.prompt_constraints,
                    coverage_role=b.role,
                    ability_visual_id=v.ability_visual_id,
                    narration_hint=m.summary,
                    editorial=EditorialEffects(
                        impact_freeze_seconds=0.1 if b.role == "impact" else 0,
                        shake=0.35 if b.role == "impact" else 0,
                        punch_in=0.08,
                        flash=b.role == "impact",
                    ),
                )
            )
        return ShotList(
            director_version="golden-coverage-v1",
            source_checksum=log.source_checksum,
            outcome_digest=digest(log.outcome),
            matchup=" vs ".join(log.fighter_names.values()),
            arena_id=arena.arena_id,
            settings=settings,
            shots=shots,
            outcome=log.outcome,
        )
