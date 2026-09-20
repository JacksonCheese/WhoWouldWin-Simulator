from random import Random
from whowouldwin.characters.schema import Ability
from whowouldwin.combat.fighter import Fighter
from whowouldwin.combat.state import World
from whowouldwin.combat.actions import legal_abilities
from whowouldwin.combat.ability import ATTACK_TYPES
from whowouldwin.combat.damage import expected_damage, hit_probability
from .targeting import distance
from .tactics import threat


def choose_action(f: Fighter, opponent: Fighter, world: World, rng: Random, bloodlusted: bool = False) -> tuple[Ability | None, dict[str, float]]:
    """Score legal abilities against a rest/reposition baseline.

    Noise is local to the engine RNG. Component scores are retained for the HUD
    and ActionChosen events, including the strongest rejected alternative.
    """
    d = distance(f, opponent)
    danger = threat(f, opponent, world)
    personality = f.profile.ai
    aggression = 1 if bloodlusted else f.profile.combat.aggression
    risk_tolerance = 1 if bloodlusted else f.profile.combat.risk_tolerance
    best, best_score, best_parts = None, .15, {"rest_position": .15, "final": .15}
    second = .15
    for a in legal_abilities(f, opponent):
        parts = {"damage": 0., "position": 0., "survival": 0., "special": 0., "finisher": 0.}
        if a.type in ATTACK_TYPES:
            damage = expected_damage(f, opponent, a) * hit_probability(f, opponent, a)
            cycle = a.startup / f.stat("combat_speed") + a.recovery + .4
            parts["damage"] = damage / 70 / cycle * (.7 + aggression * .7)
            if d > a.range + 2:
                parts["damage"] *= .45
            parts["finisher"] = .7 if damage >= opponent.health else 0
            parts["position"] = .2 * max(0, 1 - abs(d - min(a.range, f.profile.combat.preferred_range)) / max(a.range, 1))
            if opponent.pending or "stun" in opponent.statuses:
                parts["damage"] *= 1 + .2 * f.profile.combat.battle_iq
            if opponent.defense == "block" and a.type != "grapple":
                parts["damage"] *= .5
        elif a.type in {"dodge", "block"}:
            parts["survival"] = danger * (1.1 + (1 - f.health_fraction) * .9) * personality.defensive_bias
            if a.type == "block" and opponent.pending and opponent.pending.ability.type == "grapple":
                parts["survival"] *= .2
        elif a.type in {"dash", "teleport"}:
            parts["position"] = min(1.8, max(0, d - f.profile.combat.preferred_range - 5) / 22)
        elif a.type == "jump":
            parts["position"] = .9 if opponent.y > f.y + 2 else .1
            parts["survival"] = danger * .25
        elif a.type == "flight":
            parts["position"] = .75 + (.4 if d > 15 else 0)
        elif a.type == "transform":
            parts["special"] = (1.2 + (1 - f.health_fraction)) * personality.special_bias
        elif a.type == "buff":
            parts["special"] = (.55 + danger * .6) * personality.special_bias
        elif a.type == "regenerate":
            parts["survival"] = (1 - f.health_fraction) * 2.2 * personality.defensive_bias
        parts["resource"] = -(.22 * a.energy_cost / max(10, f.energy) + .18 * a.stamina_cost / max(10, f.stamina))
        parts["risk"] = -danger * a.startup * .45 * (1 - risk_tolerance)
        parts["repetition"] = -personality.repeat_penalty * f.recent_actions.count(a.id)
        parts["noise"] = rng.uniform(-personality.randomness, personality.randomness)
        score = sum(parts.values()) * a.utility
        parts["final"] = score
        if score > best_score:
            second = best_score
            best, best_score, best_parts = a, score, parts
        else:
            second = max(second, score)
    best_parts["runner_up"] = second
    return best, {key: round(value, 4) for key, value in best_parts.items()}
