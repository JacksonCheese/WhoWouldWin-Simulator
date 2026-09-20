from math import hypot
from whowouldwin.combat.fighter import Fighter


def distance(a: Fighter, b: Fighter) -> float:
    return hypot(a.x - b.x, a.y - b.y)


def direction(ax: float, ay: float, bx: float, by: float) -> tuple[float, float]:
    length = hypot(bx - ax, by - ay)
    return ((bx - ax) / length, (by - ay) / length) if length > 1e-9 else (1, 0)


def segment_distance(ax: float, ay: float, bx: float, by: float) -> float:
    """Distance from origin to a relative swept-motion segment (prevents tunneling)."""
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = max(0, min(1, -(ax * dx + ay * dy) / length)) if length else 0
    return hypot(ax + t * dx, ay + t * dy)
