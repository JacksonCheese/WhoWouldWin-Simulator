"""Normalize existing replay events without rewriting or rerunning combat."""

from copy import deepcopy
from .schemas import CinematicBattleEvent, EventLog, FighterState, Point, StateFrame


def state(snapshot: dict) -> FighterState:
    return FighterState(
        health=snapshot["health"],
        health_fraction=snapshot["health"] / snapshot["max_health"],
        energy=snapshot["energy"],
        stamina=snapshot["stamina"],
        position=Point(x=snapshot["x"], y=snapshot["y"]),
        velocity=Point(x=snapshot["vx"], y=snapshot["vy"]),
        transformation=snapshot["form"] or None,
        flying=snapshot["flying"],
        statuses=sorted(snapshot["statuses"]),
    )


def adapt_replay(replay: dict) -> EventLog:
    characters = replay["characters"]
    profile_ids = [c["identity"]["id"] for c in characters]
    ids = [
        f"{key}@{i}" if profile_ids.count(key) > 1 else key
        for i, key in enumerate(profile_ids)
    ]
    abilities = [{a["id"]: a for a in c["abilities"]} for c in characters]
    events = []
    previous = replay["frames"][0]["state"]["fighters"]
    for frame in replay["frames"]:
        current = frame["state"]["fighters"]
        before = {ids[i]: state(f) for i, f in enumerate(previous)}
        after = {ids[i]: state(f) for i, f in enumerate(current)}
        for raw in frame["events"]:
            slot = raw["fighter"]
            target = raw["target"]
            kind = raw["type"]
            values = deepcopy(raw["values"])
            actor_id = ids[slot] if slot is not None else None
            targets = [ids[target]] if target is not None else []
            ability = abilities[slot].get(raw["action"], {}) if slot is not None else {}
            damage = float(values.get("damage", 0)) if kind == "DamageApplied" else 0.0
            maximum = (
                characters[target]["resources"]["health"] if target is not None else 1
            )
            impact = min(1, damage / maximum * 4 + float(values.get("force", 0)) / 80)
            tags = []
            if ability.get("type") in {"projectile", "beam", "area", "charged_melee"}:
                tags.append("special_ability")
            if kind in {"FlightStarted", "Dash", "Jump", "Teleport"}:
                tags.append("dynamic_movement")
            if kind in {"AttackDodged", "AttackBlocked"}:
                tags.append("successful_defense")
            if kind == "DamageApplied" and values.get("health", 1) <= 0:
                tags.append("finishing_blow")
            if kind == "TransformationActivated":
                tags.append("transformation")
            if kind == "TransformationEnded":
                tags.append("transformation_ended")
            environment = None
            if kind == "Explosion":
                environment = {
                    "kind": "explosion",
                    "center": values.get("center"),
                    "radius": values.get("radius"),
                    "persistent_destruction": False,
                    "basis": "Source effect event; terrain damage is not simulated.",
                }
            event_id = f"event-{len(events):06d}"
            events.append(
                CinematicBattleEvent(
                    event_id=event_id,
                    simulation_time=raw["timestamp"],
                    actor_id=actor_id,
                    target_ids=targets,
                    event_type=kind,
                    ability_id=raw["action"],
                    success=(
                        True
                        if kind in {"AttackHit", "AttackBlocked"}
                        else (
                            False
                            if kind
                            in {"AttackMissed", "AttackDodged", "ActionInterrupted"}
                            else None
                        )
                    ),
                    damage=damage,
                    health_after_damage=(
                        values.get("health") if kind == "DamageApplied" else None
                    ),
                    impact_score=impact,
                    location=(
                        Point(x=raw["position"][0], y=raw["position"][1])
                        if raw["position"]
                        else None
                    ),
                    positions={k: v.position for k, v in after.items()},
                    velocities={k: v.velocity for k, v in after.items()},
                    actor_state_before=before.get(actor_id),
                    actor_state_after=after.get(actor_id),
                    target_state_before={k: before[k] for k in targets},
                    target_state_after={k: after[k] for k in targets},
                    environment_effect=environment,
                    narrative_tags=tags,
                    source_event_ids=[f"sim-{len(events):06d}"],
                    source_index=len(events),
                    source_tick=raw["tick"],
                    source_values=values,
                    derivations={
                        "states": "previous tick / end of current tick; not per-event intermediate state",
                        "impact_score": "min(1, damage / target max health * 4 + recorded knockback force / 80)",
                        "source_event_ids": "Stable ordinal assigned to original event order, scoped by source checksum.",
                        "success": "Attack outcome: hit/blocked contact true, miss/dodged/interrupted false; other events unknown.",
                    },
                )
            )
        previous = current
    return EventLog(
        source_checksum=replay["checksum"],
        simulation_seed=replay["seed"],
        fighter_versions={
            ids[i]: c["identity"]["version"] for i, c in enumerate(characters)
        },
        fighter_profile_ids=dict(zip(ids, profile_ids)),
        state_timeline=[
            StateFrame(
                simulation_time=f["state"]["time"],
                fighters={
                    ids[i]: state(v) for i, v in enumerate(f["state"]["fighters"])
                },
            )
            for f in replay["frames"]
        ],
        fighter_names={ids[i]: c["identity"]["name"] for i, c in enumerate(characters)},
        initial_states={
            ids[i]: state(f)
            for i, f in enumerate(replay["frames"][0]["state"]["fighters"])
        },
        events=events,
        outcome=deepcopy(replay["result"]),
    )
