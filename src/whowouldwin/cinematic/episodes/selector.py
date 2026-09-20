"""Explainable moment scoring and local action grouping; never fabricates combat events."""

from collections import Counter
from .schemas import CinematicBattleEvent, CinematicMoment, EventLog, SelectorSettings

MEANINGFUL = {
    "FightStarted",
    "FightEnded",
    "AttackStarted",
    "AttackReleased",
    "AttackHit",
    "DamageApplied",
    "AttackDodged",
    "AttackBlocked",
    "AttackMissed",
    "TransformationActivated",
    "TransformationEnded",
    "Knockback",
    "Explosion",
    "FlightStarted",
    "FlightEnded",
    "Dash",
    "Jump",
    "Teleport",
    "FighterKO",
    "StatusApplied",
}


class CinematicEventSelector:
    def __init__(self, settings: SelectorSettings | None = None):
        self.settings = settings or SelectorSettings()

    def score(
        self, event: CinematicBattleEvent, *, first_hit=False, repetitions=0
    ) -> dict[str, float]:
        e = event
        terms = {"damage": e.impact_score * 0.8}
        if e.event_type == "FightStarted":
            terms["establishing"] = 1
        if e.event_type == "FightEnded" or "finishing_blow" in e.narrative_tags:
            terms["outcome"] = 2
        if e.event_type == "TransformationActivated":
            terms["transformation"] = 1.2
        if e.event_type == "TransformationEnded":
            terms["form_expiry"] = 0.42
        if first_hit:
            terms["first_hit"] = 0.5
        if "special_ability" in e.narrative_tags:
            terms["special"] = 0.32
        if "successful_defense" in e.narrative_tags:
            terms["defense"] = 0.58
        if "dynamic_movement" in e.narrative_tags:
            terms["movement"] = 0.35
        if e.event_type == "Knockback":
            terms["knockback"] = 0.28
        if e.environment_effect:
            terms["environment"] = 0.22
        if e.event_type == "StatusApplied" and e.source_values.get("status") == "decoy":
            terms["decoy"] = 0.5
        a = e.actor_state_before
        for target in e.target_state_after.values():
            if e.damage and target.health_fraction < self.settings.near_defeat_fraction:
                terms["near_defeat"] = 0.35
            if (
                e.damage
                and a
                and a.health_fraction < self.settings.near_defeat_fraction
            ):
                terms["comeback"] = 0.4
        if a and e.actor_state_after:
            if (
                min(a.energy, a.stamina)
                > 10
                >= min(e.actor_state_after.energy, e.actor_state_after.stamina)
            ):
                terms["resource_exhaustion"] = 0.22
            for key, target in e.target_state_after.items():
                old = e.target_state_before[key]
                if (a.health_fraction - old.health_fraction) * (
                    e.actor_state_after.health_fraction - target.health_fraction
                ) < 0:
                    terms["momentum_swing"] = 0.3
        terms["repetition"] = -min(0.4, repetitions * self.settings.repetition_penalty)
        return terms

    def select(self, log: EventLog) -> list[CinematicMoment]:
        groups = []
        latest = {}
        for e in log.events:
            if e.event_type not in MEANINGFUL:
                continue
            key = (e.actor_id, e.ability_id)
            isolated = e.event_type in {
                "FightStarted",
                "FightEnded",
                "FighterKO",
                "TransformationActivated",
                "TransformationEnded",
            }
            index = latest.get(key)
            if (
                not isolated
                and index is not None
                and e.event_type != "AttackStarted"
                and e.simulation_time - groups[index][-1].simulation_time
                <= self.settings.group_window
            ):
                groups[index].append(e)
            else:
                groups.append([e])
                latest[key] = len(groups) - 1 if not isolated else None
        counts = Counter()
        first_hit = True
        candidates = []
        for group in sorted(
            groups, key=lambda g: (g[0].simulation_time, g[0].source_index)
        ):
            strongest = {}
            damaging = any(e.damage > 0 for e in group)
            for e in group:
                terms = self.score(
                    e,
                    first_hit=first_hit and e.damage > 0,
                    repetitions=counts[(e.actor_id, e.ability_id)],
                )
                for key, value in terms.items():
                    strongest[key] = max(strongest.get(key, -1), value)
            if damaging:
                first_hit = False
            first = group[0]
            if first.ability_id:
                counts[(first.actor_id, first.ability_id)] += 1
            score = max(0, sum(strongest.values()))
            kind = self._kind(group)
            if score < self.settings.minimum_score and kind not in {
                "faceoff",
                "outcome",
                "finisher",
            }:
                continue
            participants = list(
                dict.fromkeys(
                    k for e in group for k in [e.actor_id, *e.target_ids] if k
                )
            )
            if not participants:
                participants = list(log.fighter_names)
            damage = sum(e.damage for e in group)
            names = [log.fighter_names[k] for k in participants]
            summary = self._summary(kind, names, first.ability_id, damage, log)
            consequence = []
            if damage:
                consequence.append(
                    f"{damage:.2f} recorded health removed; visual scuffs may persist without anatomical claims."
                )
            if kind == "transformation":
                consequence.append(
                    "Use the recorded form until its recorded expiry, even across omitted events."
                )
            if any(e.environment_effect for e in group):
                consequence.append(
                    "Brief blast/dust only; no persistent terrain destruction is recorded."
                )
            candidates.append(
                CinematicMoment(
                    moment_id=f"moment-{len(candidates):04d}",
                    source_event_ids=[e.event_id for e in group],
                    start_time=first.simulation_time,
                    end_time=group[-1].simulation_time,
                    importance_score=round(score, 6),
                    score_components=strongest,
                    moment_type=kind,
                    participants=participants,
                    summary=summary,
                    continuity_consequences=consequence,
                )
            )
        mandatory = [
            m
            for m in candidates
            if m.moment_type in {"faceoff", "outcome", "finisher", "transformation"}
        ]
        selected_ids = {m.moment_id for m in mandatory}
        ranked = sorted(
            (m for m in candidates if m.moment_id not in selected_ids),
            key=lambda m: (-m.importance_score, m.start_time, m.moment_id),
        )
        selected = (
            mandatory + ranked[: max(0, self.settings.max_moments - len(mandatory))]
        )
        return sorted(selected, key=lambda m: (m.start_time, m.end_time, m.moment_id))

    @staticmethod
    def _kind(events):
        types = {e.event_type for e in events}
        tags = {t for e in events for t in e.narrative_tags}
        if "FightStarted" in types:
            return "faceoff"
        if "FightEnded" in types:
            return "outcome"
        if "finishing_blow" in tags:
            return "finisher"
        if "TransformationActivated" in types:
            return "transformation"
        if "TransformationEnded" in types:
            return "form_expiry"
        if "AttackDodged" in types:
            return "dodge"
        if "AttackBlocked" in types:
            return "block"
        if any(e.damage for e in events):
            return "special_hit" if "special_ability" in tags else "hit"
        if "special_ability" in tags:
            return "special_attack"
        if "dynamic_movement" in tags:
            return "movement"
        if any(e.source_values.get("status") == "decoy" for e in events):
            return "decoy"
        if "AttackMissed" in types:
            return "miss"
        if "Knockback" in types:
            return "knockback"
        if "FighterKO" in types:
            return "defeat"
        return "exchange"

    @staticmethod
    def _summary(kind, names, ability, damage, log):
        actor = names[0]
        target = names[-1]
        move = (ability or "attack").replace("_", " ")
        if kind == "faceoff":
            return (
                f'{" vs ".join(log.fighter_names.values())}: the recorded fight begins.'
            )
        if kind == "outcome":
            winner = log.outcome["winner"]
            label = (
                list(log.fighter_names.values())[winner] + " wins"
                if winner is not None
                else "Draw"
            )
            return f"{label} by {log.outcome['condition'].replace('_',' ')} at {log.outcome['duration']:.2f} simulation seconds."
        if kind == "dodge":
            return f"{target} avoids {actor}'s {move}; this attack causes no added cinematic damage."
        if kind == "block":
            return f"{target} blocks {actor}'s {move}. Recorded damage in this exchange: {damage:.1f}."
        if kind == "transformation":
            return f"{actor} activates the recorded transformation."
        if kind == "form_expiry":
            return f"{actor}'s recorded transformation ends."
        if kind == "finisher":
            return f"{actor} lands {move}, reducing {target} to zero health."
        if damage:
            return f"{actor} hits {target} with {move}: {damage:.1f} recorded damage."
        if kind == "miss":
            return f"{actor}'s {move} misses {target}."
        if kind == "defeat":
            return f"{actor} is defeated as recorded."
        return f'{actor}: {move.replace("attack", "combat movement") if kind=="movement" else move}; recorded {kind.replace("_"," ")}.'
