from whowouldwin.combat.fighter import Fighter
from whowouldwin.combat.state import World
from .targeting import distance


def threat(f: Fighter, opponent: Fighter, world: World) -> float:
    danger = .08
    if opponent.pending and opponent.pending.ability.damage:
        ability = opponent.pending.ability
        if distance(f, opponent) <= ability.range + 5:
            danger += .8 / (1 + opponent.pending.remaining)
    for p in world.projectiles:
        if p.target == f.slot and (p.x - f.x) ** 2 + (p.y - f.y) ** 2 < 20 ** 2:
            danger += .65
    danger += .15 if opponent.last_action and distance(f, opponent) < 5 else 0
    return min(1.5, danger)
