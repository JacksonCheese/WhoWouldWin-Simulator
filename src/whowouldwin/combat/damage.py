"""The sole damage and hit-probability formulas, shared by AI and resolution."""
from random import Random
from whowouldwin.characters.schema import Ability
from .fighter import Fighter
from whowouldwin.ai.targeting import distance


def hit_probability(attacker: Fighter, defender: Fighter, ability: Ability) -> float:
    accuracy = attacker.profile.combat.accuracy + ability.hit_modifier
    evasion = defender.profile.combat.evasion
    speed = attacker.stat("combat_speed") / defender.stat("reaction_speed")
    chance = accuracy - .3 * evasion + .06 * (speed - 1)
    chance -= .12 if attacker.stamina < 10 else 0
    chance += .12 if "stun" in defender.statuses or defender.pending else 0
    chance -= .24 if "decoy" in defender.statuses else 0
    if ability.type == "grapple":
        chance += .15 * (attacker.profile.combat.grappling - defender.profile.combat.grappling)
    return max(.08, min(.97, chance))


def expected_damage(attacker: Fighter, defender: Fighter, ability: Ability) -> float:
    """D = base * ((power+20)/(durability+20))^.45 * (1-resistance).

    The sublinear ratio softens scale differences without subtracting defense;
    positive attacks still do positive damage. Resolution adds seeded variance,
    critical hits and defenses. All values are gameplay units, not physical feats.
    """
    power = attacker.stat("striking_power")
    if ability.type == "grapple":
        power = (power + attacker.stat("strength")) / 2
    ratio = (power + 20) / (defender.stat("durability") + 20)
    resistance = defender.profile.resistances.get(ability.damage_type,
        defender.profile.resistances.get("physical", 0) if ability.damage_type in {"blunt", "piercing"} else 0)
    shield = 1 / (1 + defender.statuses["shield"].magnitude) if "shield" in defender.statuses else 1
    return max(0, ability.damage * ratio ** .45 * (1 - resistance) * shield)


def apply_damage(attacker: Fighter, defender: Fighter, amount: float, action: str, emit) -> float:
    actual = min(defender.health, max(0, amount))
    defender.health = max(0, defender.health - actual)
    attacker.damage_dealt += actual
    defender.damage_received += actual
    attacker.damage_by_ability[action] += actual
    if actual:
        defender.last_damage_action = action
        defender.last_damage_source = attacker.slot
    emit("DamageApplied", attacker, defender, action, damage=actual, health=defender.health)
    return actual


def resolve_hit(attacker: Fighter, defender: Fighter, ability: Ability, rng: Random, emit, apply_status) -> bool:
    if defender.defense == "dodge" and rng.random() < .88:
        emit("AttackDodged", attacker, defender, ability.id)
        return False
    if rng.random() > hit_probability(attacker, defender, ability):
        emit("AttackMissed", attacker, defender, ability.id, reason="accuracy")
        return False
    damage = expected_damage(attacker, defender, ability) * rng.uniform(.88, 1.12)
    critical = rng.random() < ability.critical_chance
    if critical:
        damage *= 1.5
    blocked = defender.defense == "block" and ability.type != "grapple" and defender.stamina >= 3
    if blocked:
        damage *= 1 - .8 * defender.profile.combat.blocking
        defender.stamina = max(0, defender.stamina - 3)
        emit("AttackBlocked", attacker, defender, ability.id, damage=damage)
    attacker.hits[ability.id] += 1
    emit("AttackHit", attacker, defender, ability.id, critical=critical, blocked=blocked,
         attack_type=ability.type, target_position=defender.position)
    apply_damage(attacker, defender, damage, ability.id, emit)
    if ability.knockback and defender.alive:
        from whowouldwin.ai.targeting import direction
        dx, dy = direction(attacker.x, attacker.y, defender.x, defender.y)
        force = ability.knockback * min(2, 80 / defender.stat("mass")) * (.4 if blocked else 1)
        defender.vx += dx * force
        defender.vy += max(.25, dy) * force
        emit("Knockback", attacker, defender, ability.id, force=force)
    if not blocked and defender.alive:
        if ability.stun:
            apply_status(defender, "stun", ability.stun, 1, attacker, ability.id)
        for status in ability.status_effects:
            apply_status(defender, status.id, status.duration, status.magnitude, attacker, ability.id)
    return True
