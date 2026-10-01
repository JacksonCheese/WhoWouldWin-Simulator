"""Deterministic, provider-neutral short-shot planning from a completed replay."""

from pathlib import Path
import json
from whowouldwin.cinematic.episodes.adapter import adapt_replay
from whowouldwin.cinematic.episodes.selector import CinematicEventSelector
from whowouldwin.cinematic.episodes.schemas import SelectorSettings
from whowouldwin.simulation.replay import digest
from .schemas import (
    AbilityVisualSpec, CharacterVisualBible, EpisodePlan, FightBeat,
    SeedanceShot, VisualContinuity,
)


STYLE = (
    "Stylized 2D animated comic with simple repeatable character designs, bold silhouettes, "
    "restrained textured lighting, clear negative space and deliberate impact frames. "
    "Full-frame vertical 9:16, no phone interface or embedded horizontal letterbox."
)


def bible_directory() -> Path:
    editable_data = Path(__file__).resolve().parents[4] / "data/seedance_visual_bibles"
    if editable_data.is_dir():
        return editable_data
    return Path(__file__).resolve().parents[2] / "data/seedance_visual_bibles"


def load_bibles(ids: list[str], directory: Path | None = None) -> dict[str, CharacterVisualBible]:
    folder = directory or bible_directory()
    result = {}
    for key in ids:
        path = folder / f"{key}.json"
        bible = CharacterVisualBible.model_validate_json(path.read_text(encoding="utf-8"))
        if bible.character_id != key:
            raise ValueError(f"Visual bible ID mismatch in {path}")
        result[key] = bible
    return result


def ability_specs(replay: dict) -> dict[str, AbilityVisualSpec]:
    """Cover every profile ability; these are presentation fixtures, never combat logic."""
    result = {}
    for character in replay["characters"]:
        cid = character["identity"]["id"]
        for ability in character["abilities"]:
            aid, kind = ability["id"], ability["type"]
            energy = kind in {"projectile", "beam", "area", "buff", "transform", "regenerate"}
            color = (["blue-white", "cyan"] if cid == "naruto" else
                     ["pale blue", "white"] if cid == "aang" else
                     ["warm red", "white"] if cid == "homelander" else
                     ["neutral air compression", "white"])
            if not energy:
                color = ["neutral motion line", "costume color"]
            shape = {
                "projectile": "one compact directional sphere or bolt",
                "beam": "one narrow continuous line from the recorded origin",
                "area": "one bounded radial pulse",
                "charged_melee": "one physical contact arc",
                "grapple": "one close hand-to-body contact",
                "transform": "one aura surrounding the actor only",
                "flight": "subtle directional air wake",
                "teleport": "brief afterimage at the departure point",
                "dodge": "narrow body slip with a clean miss lane",
                "block": "forearm interception at the recorded contact",
            }.get(kind, "one readable action line with no extra contact")
            key = f"{cid}:{aid}"
            result[key] = AbilityVisualSpec(
                character_id=cid, ability_id=aid, ability_type=kind,
                activation_pose=("cued palm/arm windup" if energy else "grounded prepared stance"),
                visual_shape=shape, color_palette=color,
                scale="fit inside the actor's readable action silhouette",
                lighting_behavior=("restrained local glow on actor and nearby surface" if energy else "no independent glow"),
                motion_behavior=f"one {kind.replace('_', ' ')} action following the recorded direction",
                impact_behavior="show only the recorded hit, block, dodge or miss; no additional damage",
                screen_space_readability="single clear silhouette and one dominant effect at phone size",
                continuity_rules=["Keep effect color and origin consistent between shots", "End the effect when the recorded action ends"],
                never_confuse_with=["a second unrecorded attack", "a change to the combat outcome"],
                requires_image_reference=energy or kind in {"charged_melee", "grapple"},
            )
    return result


def adapt_beats(log, specs: dict[str, AbilityVisualSpec]) -> list[FightBeat]:
    """One beat per source event; timing windows are editorial labels, not new facts."""
    beats = []
    for event in log.events:
        kind = event.event_type
        actor, target = event.actor_id, next(iter(event.target_ids), None)
        spec = specs.get(f"{log.fighter_profile_ids.get(actor)}:{event.ability_id}")
        contact = (
            "Recorded contact; hold one readable surface touch" if kind in {"AttackHit", "AttackBlocked"}
            else "Clear near miss with no physical contact" if kind in {"AttackMissed", "AttackDodged"}
            else "No new contact is established by this event"
        )
        if kind == "DamageApplied":
            contact = f"Recorded {event.damage:.3f} damage; this event does not add a second hit"
        beats.append(FightBeat(
            beat_id=f"beat-{event.source_index:06d}", source_event_id=event.event_id,
            source_index=event.source_index, event_type=kind,
            acting_character=actor, target_character=target, ability_id=event.ability_id,
            intent=(f"{log.fighter_names.get(actor, 'Fight')} performs {event.ability_id or kind}"),
            simulation_time=event.simulation_time,
            start_time=max(0.0, round(event.simulation_time - 0.1, 6)),
            end_time=event.simulation_time,
            anticipation=(spec.activation_pose if spec and kind in {"AttackStarted", "TransformationActivated"} else "use prior guarded pose"),
            action=(spec.motion_behavior if spec else f"show the recorded {kind} state only"),
            contact_or_near_contact=contact,
            reaction=("target recoils in the recorded direction" if kind in {"AttackHit", "Knockback", "DamageApplied"} else "retain recorded defense state"),
            recovery="settle toward the next recorded state without inventing another action",
            required_character_poses=["actor clear silhouette", "target clear silhouette"] if target else ["actor clear silhouette"],
            required_ability_effects=[spec.visual_shape] if spec and spec.requires_image_reference else [],
            camera_importance=round(min(1.0, event.impact_score + (0.7 if kind in {"FightEnded", "FighterKO", "TransformationActivated"} else 0.45 if kind in {"AttackHit", "AttackDodged", "AttackBlocked"} else 0.05)), 4),
            continuity_requirements=["Preserve event order and recorded outcome", "Keep costume, form, facing and screen lane stable"],
            can_combine=kind not in {"FightStarted", "FightEnded", "FighterKO", "TransformationActivated", "TransformationEnded"},
            success=event.success, recorded_damage=event.damage,
        ))
    return beats


def _state_at(log, timestamp: float, event_ids: list[str]) -> VisualContinuity:
    frame = log.state_timeline[0]
    for candidate in log.state_timeline:
        if candidate.simulation_time > timestamp + 1e-9:
            break
        frame = candidate
    states = frame.fighters
    ordered = sorted(states, key=lambda key: (states[key].position.x, key))
    screen = {key: "left" if i == 0 else "right" for i, key in enumerate(ordered)}
    costume = {key: "base design" for key in states}
    injury = {key: ("surface scuffs" if value.health_fraction < 0.9 else "clean") for key, value in states.items()}
    return VisualContinuity(
        simulation_time=frame.simulation_time,
        screen_positions=screen,
        facing={key: ("right" if screen[key] == "left" else "left") for key in states},
        stance={key: ("incapacitated" if value.health_fraction <= 0 else
                      "controlled flight" if value.flying else "grounded guard") for key, value in states.items()},
        dominant_limb={key: "match approved character reference" for key in states},
        costume_state=costume, injury_state=injury,
        ability_state={key: value.transformation or "base form" for key, value in states.items()},
        energy_state={key: round(value.energy, 6) for key, value in states.items()},
        camera_side="south side of action axis; do not cross 180-degree line",
        environment_landmarks=["one road stripe", "left facade", "right facade"],
        lighting_direction="soft key from screen left, restrained right rim", time_of_day="blue hour",
        transition_safe_pose={key: ("incapacitated" if value.health_fraction <= 0 else
                                    "airborne guard" if value.flying else "grounded guard") for key, value in states.items()},
        source_event_ids=event_ids,
    )


def _choose_moments(log, count: int):
    moments = CinematicEventSelector(SelectorSettings(max_moments=100)).select(log)
    intro = next(m for m in moments if m.moment_type == "faceoff")
    outcome = next(m for m in reversed(moments) if m.moment_type == "outcome")
    finishers = [m for m in moments if m.moment_type == "finisher" and m.end_time <= outcome.start_time]
    climax = finishers[-1] if finishers else max(
        (m for m in moments if m.moment_type in {"hit", "special_hit"}),
        key=lambda m: (m.importance_score, m.end_time), default=outcome,
    )
    pool = [m for m in moments if m.moment_id not in {intro.moment_id, outcome.moment_id, climax.moment_id}
            and m.end_time < climax.end_time]
    slots = count - 3
    chosen = []
    used_kinds = set()
    for moment in sorted(pool, key=lambda m: (-m.importance_score, m.end_time, m.moment_id)):
        if len(chosen) >= slots:
            break
        if moment.moment_type not in used_kinds or len(pool) - len(chosen) <= slots:
            chosen.append(moment)
            used_kinds.add(moment.moment_type)
    for moment in sorted(pool, key=lambda m: (-m.importance_score, m.end_time, m.moment_id)):
        if len(chosen) >= slots:
            break
        if moment not in chosen:
            chosen.append(moment)
    if len(chosen) != slots or climax == outcome:
        raise ValueError("Replay lacks enough meaningful distinct events for a short episode")
    return [intro, *sorted(chosen, key=lambda m: (m.end_time, m.moment_id)), climax, outcome]


def _frame_budget(duration: float, count: int, fps: int) -> list[int]:
    total = round(duration * fps)
    if total < count * round(0.5 * fps) or total > count * 3 * fps:
        raise ValueError("Duration cannot fit shot count within 0.5–3 seconds per shot")
    weights = [1.1] + [1.0] * (count - 3) + [1.35, 0.9]
    quotas = [total * weight / sum(weights) for weight in weights]
    frames = [int(value) for value in quotas]
    for index in sorted(range(count), key=lambda i: (-(quotas[i] - frames[i]), i))[:total - sum(frames)]:
        frames[index] += 1
    if any(not round(0.5 * fps) <= value <= 3 * fps for value in frames):
        raise ValueError("Shot frame budget violates duration bounds")
    return frames


def direct(replay: dict, *, duration: float = 10, shots: int = 8, fps: int = 30,
           bibles: dict[str, CharacterVisualBible] | None = None) -> tuple[EpisodePlan, list[FightBeat], dict[str, AbilityVisualSpec]]:
    if not 8 <= duration <= 15 or not 6 <= shots <= 12 or fps not in {24, 30}:
        raise ValueError("Seedance defaults require 8–15 seconds, 6–12 shots, 24 or 30 fps")
    log = adapt_replay(replay)
    ids = list(dict.fromkeys(log.fighter_profile_ids.values()))
    bibles = bibles or load_bibles(ids)
    specs = ability_specs(replay)
    beats = adapt_beats(log, specs)
    by_event = {beat.source_event_id: beat for beat in beats}
    chosen = _choose_moments(log, shots)
    durations = _frame_budget(duration, shots, fps)
    plan_shots = []
    continuity = _state_at(log, 0, ["event-000000"])
    for index, (moment, frame_count) in enumerate(zip(chosen, durations), 1):
        related = [by_event[event_id] for event_id in moment.source_event_ids]
        lead = max(related, key=lambda beat: (beat.camera_importance, -beat.source_index))
        end = _state_at(log, moment.end_time, moment.source_event_ids)
        character_ids = list(log.fighter_names)
        actor = lead.acting_character or character_ids[0]
        profile_id = log.fighter_profile_ids.get(actor, actor)
        spec = specs.get(f"{profile_id}:{lead.ability_id}")
        if index == 1:
            framing, motion, purpose = "medium-wide faceoff; both full silhouettes", "subtle push in", "Establish combat geography"
        elif index == shots:
            framing, motion, purpose = "medium aftermath with both fighters visible", "slow pull back", "Show recorded outcome"
        elif index == shots - 1:
            ranged = spec is not None and spec.ability_type in {"projectile", "beam", "area"}
            framing = "medium three-quarter projectile impact; bodies remain separate" if ranged else "medium three-quarter physical contact silhouette"
            motion, purpose = "one short impact push", "Climactic recorded action"
        elif moment.moment_type in {"dodge", "block"}:
            framing, motion, purpose = "medium defensive angle; attack lane visible", "short lateral track", "Make the recorded defense legible"
        else:
            framing, motion, purpose = "medium three-quarter action", "controlled directional track", "Show one recorded action"
        required = [f"character_references/{log.fighter_profile_ids[key]}_{view}.png"
                    for key in character_ids for view in bibles[log.fighter_profile_ids[key]].required_views]
        required.append("style_references/approved_style.png")
        if spec and spec.requires_image_reference:
            required.append(f"ability_references/{profile_id}_{lead.ability_id}.png")
        effect = [spec.visual_shape] if spec and spec.requires_image_reference else []
        pose_start = continuity.transition_safe_pose.copy()
        pose_end = end.transition_safe_pose.copy()
        if index == 1:
            pose_end[actor] = pose_start[actor]
        elif index == shots:
            pose_end[actor] = end.transition_safe_pose[actor]
        elif moment.moment_type in {"hit", "special_hit", "finisher"}:
            pose_end[actor] = "recorded attack follow-through"
        elif moment.moment_type == "transformation":
            pose_end[actor] = "transformed guard"
        else:
            pose_end[actor] = spec.activation_pose if spec else "recorded reaction pose"
        action = moment.summary
        prompt = (
            f"{STYLE} Shot {index}/{shots}, {frame_count / fps:.3f} seconds. {purpose}. "
            f"Characters: {', '.join(log.fighter_names[key] for key in character_ids)}. "
            f"{framing}; camera {motion}, fixed south side of action axis. "
            f"One dominant action: {action} Starting poses: {pose_start}. End poses: {pose_end}. "
            f"Actor design: {bibles[profile_id].simplified_production_design} "
            f"Use the exact approved character references; no design drift. "
            f"Effect: {', '.join(effect) if effect else 'none beyond recorded action'}. "
            f"Minimal blue-hour street with one road stripe and two facade anchors. "
            f"Recorded outcome remains {log.outcome['condition']}; do not invent extra contacts."
        )
        negative = (
            "No extra fighters, attacks, hits, powers, injuries, weapons, costume changes, text, logos, "
            "phone interface, horizontal letterbox, camera-axis flip, limb duplication, merged bodies, "
            "unmotivated flash, unreadable contact or continuity drift. "
            "Do not turn a recorded miss or dodge into a hit."
        )
        shot = SeedanceShot(
            shot_id=f"shot_{index:03d}", sequence_index=index,
            duration_seconds=round(frame_count / fps, 6), purpose=purpose,
            source_beat_ids=[beat.beat_id for beat in related],
            characters_visible=character_ids, starting_pose=pose_start, ending_pose=pose_end,
            action_description=action, camera_framing=framing, camera_movement=motion,
            lens_style_direction="graphic 2D medium-lens perspective; no extreme distortion",
            background_description="Minimal blue-hour street: road stripe and two simple facade anchors",
            ability_effects=effect, transition_in="hard cut on motion" if index > 1 else "cut in",
            transition_out="hard cut on motion" if index < shots else "clean hold to end",
            continuity_anchors=["consistent screen lanes", "same costume and facial anchors", "fixed lighting direction", "same road stripe"],
            seedance_prompt=prompt, negative_prompt=negative,
            required_reference_images=required, human_review_checklist=[
                "One dominant recorded action only", "Correct hit, miss or defense", "Same character designs and screen lanes",
                "Clear full-frame 9:16 silhouette at phone size", "End pose matches next shot's start state",
            ], continuity_start=continuity, continuity_end=end, source_simulation_time=moment.end_time,
        )
        plan_shots.append(shot)
        continuity = end
    episode_id = f"{'_vs_'.join(ids)}_seed{log.simulation_seed}_{log.source_checksum[:8]}"
    plan = EpisodePlan(
        episode_id=episode_id, source_checksum=log.source_checksum,
        canonical_event_sha256=digest([event for frame in replay["frames"] for event in frame["events"]]),
        seed=log.simulation_seed,
        fighter_ids=ids, fps=fps, duration_seconds=round(sum(durations) / fps, 6),
        style=STYLE, shots=plan_shots, outcome=log.outcome,
    )
    return plan, beats, specs
