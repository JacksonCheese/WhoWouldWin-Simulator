from math import ceil
from .fighter import Fighter, Pending
from .ability import Ability, ATTACK_TYPES
from whowouldwin.ai.targeting import distance, direction


def legal_abilities(f: Fighter, target: Fighter) -> list[Ability]:
    if not f.alive or f.busy > 1e-8 or f.pending or "stun" in f.statuses or "incapacitated" in f.statuses:
        return []
    d = distance(f, target)
    legal = []
    for a in f.profile.abilities:
        if a.id in f.cooldowns or f.energy < a.energy_cost or f.stamina < a.stamina_cost:
            continue
        if not a.condition.min_health_fraction <= f.health_fraction <= a.condition.max_health_fraction:
            continue
        if a.condition.target_status and a.condition.target_status not in target.statuses:
            continue
        if a.required_form and a.required_form != f.form:
            continue
        if a.type == "transform" and f.form or a.type == "flight" and f.flying:
            continue
        if a.type == "jump" and (f.y > f.radius + .1 or f.flying):
            continue
        if a.type == "regenerate" and f.health_fraction > .9:
            continue
        if a.type == "buff" and any(s.id in f.statuses for s in a.status_effects):
            continue
        # Legal attack envelopes include collision radii; charged attacks can
        # wind up while approaching, but must actually reach the target on impact.
        reach = a.range + f.radius + target.radius
        anticipation = min(3, a.startup * f.stat("movement_speed"))
        if a.type in ATTACK_TYPES and not a.minimum_range <= d <= reach + anticipation:
            continue
        legal.append(a)
    return legal


def start_action(f: Fighter, target: Fighter, a: Ability, dt: float, emit):
    """Resource/cooldown spending happens once on commitment, including interrupted attacks."""
    f.stamina = max(0, f.stamina - a.stamina_cost)
    f.energy = max(0, f.energy - a.energy_cost)
    f.cooldowns[a.id] = a.cooldown
    startup = max(dt, ceil(a.startup / f.stat("combat_speed") / dt) * dt)
    # Newly committed actions are visited by this tick's pending update. Include
    # that tick so release time is never earlier than commitment + startup.
    f.pending = Pending(a, startup + dt, target.position)
    f.busy = startup + a.active + a.recovery / f.stat("combat_speed")
    f.decision = max(dt, .28 / f.stat("reaction_speed"))
    f.last_action = a.name
    f.uses[a.id] += 1
    f.recent_actions.append(a.id)
    del f.recent_actions[:-5]
    emit("AbilityCooldownStarted", f, target, a.id, duration=a.cooldown)
    emit("AttackStarted" if a.type in ATTACK_TYPES else "AbilityStarted", f, target, a.id,
         attack_type=a.type, startup=startup, active=a.active, target_position=target.position)


def resolve_support(f: Fighter, target: Fighter, a: Ability, emit, apply_status):
    dx, dy = direction(f.x, f.y, target.x, target.y)
    if a.type in {"dodge", "block"}:
        f.defense = a.type
        f.defense_time = a.active
        if a.type == "dodge":
            f.vx = -dx * max(12, a.mobility_distance / a.active)
            if not f.flying:
                f.vy = 5
        emit("DefenseActivated", f, target, a.id, defense=a.type, duration=a.active)
    elif a.type == "dash":
        f.vx = dx * max(f.stat("movement_speed") * 2, a.mobility_distance / a.active)
        if f.flying:
            f.vy = dy * f.stat("movement_speed") * 2
        emit("Dash", f, target, a.id)
    elif a.type == "jump":
        f.vy = max(12, a.mobility_distance)
        emit("Jump", f, target, a.id)
    elif a.type == "flight":
        f.flying = True
        f.flight_time = a.active
        f.busy = min(f.busy, a.recovery)
        emit("FlightStarted", f, target, a.id)
    elif a.type == "teleport":
        gap = min(a.mobility_distance, max(0, distance(f, target) - f.profile.combat.preferred_range))
        f.x += dx * gap
        f.y += dy * gap
        f.vx = f.vy = 0
        emit("Teleport", f, target, a.id)
    elif a.type == "transform":
        form = next(t for t in f.profile.transformations if t.id == a.transformation)
        f.form, f.form_time = form.id, form.duration
        f.modifiers = dict(form.modifiers)
        emit("TransformationActivated", f, action=a.id, form=form.name, duration=form.duration)
    for status in a.status_effects:
        apply_status(f, status.id, status.duration, status.magnitude, f, a.id)
    emit("AbilityResolved", f, target, a.id, ability_type=a.type)
