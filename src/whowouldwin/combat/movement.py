from math import exp
from .fighter import Fighter
from .environment import Arena
from whowouldwin.ai.targeting import direction, distance


def move(f: Fighter, target: Fighter, arena: Arena, dt: float, bloodlusted: bool = False):
    speed = f.stat("movement_speed")
    preferred = 2.7 if bloodlusted else f.profile.combat.preferred_range
    if f.pending and f.pending.ability.damage:
        preferred = min(preferred, max(1.5, f.pending.ability.range * .8))
    # When ranged resources are depleted, close for affordable melee instead of
    # waiting forever outside the only currently usable attack's range.
    affordable = [a.range for a in f.profile.abilities if a.damage and a.energy_cost <= f.energy and a.stamina_cost <= f.stamina]
    if affordable:
        preferred = min(preferred, max(affordable) * .85)
    d = distance(f, target)
    sign = 1 if d > preferred + 1 else (-.65 if d < preferred - 2 else 0)
    dx, _ = direction(f.x, f.y, target.x, target.y)
    desired_x = dx * speed * sign
    disabled = not f.alive or "stun" in f.statuses or "incapacitated" in f.statuses
    steering = 0 if disabled or f.defense == "dodge" else 1
    if f.pending and f.pending.ability.type in {"charged_melee", "beam", "projectile"}:
        desired_x *= .35
    acceleration = speed * 4 * dt * steering
    f.vx += max(-acceleration, min(acceleration, desired_x - f.vx))
    if not steering:
        f.vx *= exp(-2 * dt)
    if f.flying and not disabled:
        # Flight is tactical elevation, not indefinite escape beyond melee reach.
        altitude = min(arena.height - 2, target.y + (1.5 if preferred < 6 else 3))
        altitude = min(7, altitude)
        desired_y = max(-speed, min(speed, (altitude - f.y) * 3))
        f.vy += max(-speed * 4 * dt, min(speed * 4 * dt, desired_y - f.vy))
    else:
        f.vy -= arena.gravity * dt
    f.x += f.vx * dt
    f.y += f.vy * dt
    clamp_to_arena(f, arena)


def clamp_to_arena(f: Fighter, arena: Arena):
    if f.x < f.radius or f.x > arena.width - f.radius:
        f.x = max(f.radius, min(arena.width - f.radius, f.x))
        f.vx = 0
    if f.y < f.radius or f.y > arena.height - f.radius:
        f.y = max(f.radius, min(arena.height - f.radius, f.y))
        f.vy = 0


def separate(a: Fighter, b: Fighter, arena: Arena):
    d = distance(a, b)
    if d < a.radius + b.radius:
        dx, dy = direction(a.x, a.y, b.x, b.y)
        overlap = (a.radius + b.radius - d) / 2
        a.x -= dx * overlap
        a.y -= dy * overlap
        b.x += dx * overlap
        b.y += dy * overlap
        clamp_to_arena(a, arena)
        clamp_to_arena(b, arena)
