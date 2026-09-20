from .fighter import Fighter, Status
from .damage import apply_damage


def apply_status(fighter: Fighter, name: str, duration: float, magnitude: float, source: Fighter, action: str, emit):
    if name == "stun" and (fighter.stun_immunity > 0 or "stun" in fighter.statuses):
        return
    if name == "stun":
        duration = min(1.5, duration)
        if fighter.pending:
            emit("ActionInterrupted", fighter, source, fighter.pending.ability.id)
            fighter.pending = None
        fighter.busy = max(fighter.busy, duration)
    fighter.statuses[name] = Status(duration, magnitude, source.slot, action)
    if name == "incapacitated":
        fighter.control_action = action
    emit("StatusApplied", source, fighter, action, status=name, duration=duration, magnitude=magnitude)


def update_fighter(fighter: Fighter, fighters: list[Fighter], dt: float, emit):
    f = fighter
    for key in list(f.cooldowns):
        left = f.cooldowns[key] - dt
        if left <= 1e-8:
            del f.cooldowns[key]
        else:
            f.cooldowns[key] = left
    f.busy = max(0, f.busy - dt)
    f.decision = max(0, f.decision - dt)
    f.stun_immunity = max(0, f.stun_immunity - dt)
    f.defense_time = max(0, f.defense_time - dt)
    if not f.defense_time:
        f.defense = ""
    f.form_time = max(0, f.form_time - dt)
    if f.form and not f.form_time:
        emit("TransformationEnded", f, action=f.form)
        f.form = ""
        f.modifiers.clear()
    f.flight_time = max(0, f.flight_time - dt)
    if f.flying and (not f.flight_time or f.energy < dt * 2):
        f.flying = False
        emit("FlightEnded", f)
    control = f.statuses.get("incapacitated")
    f.control_time = f.control_time + min(dt, control.remaining) if control else 0
    for key, status in list(f.statuses.items()):
        effective_dt = min(dt, status.remaining)
        if f.alive and key == "burn":
            apply_damage(fighters[status.source], f, status.magnitude * effective_dt, status.action, emit)
        if f.alive and key == "regen":
            f.health = min(f.profile.resources.health, f.health + status.magnitude * effective_dt)
        status.remaining -= dt
        if status.remaining <= 1e-8:
            del f.statuses[key]
            if key == "stun":
                f.stun_immunity = 1.2
            emit("StatusExpired", f, action=status.action, status=key)
    if not f.alive:
        return
    resources = f.profile.resources
    f.health = min(resources.health, f.health + resources.regeneration * dt)
    f.stamina = min(resources.stamina, f.stamina + resources.stamina_regen * (f.base["stamina"] / 100) * dt)
    f.energy = min(resources.energy, max(0, f.energy + (resources.energy_regen - (2 if f.flying else 0)) * dt))
