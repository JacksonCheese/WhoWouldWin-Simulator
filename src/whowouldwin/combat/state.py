from dataclasses import dataclass, field
from whowouldwin.characters.schema import Ability
from .fighter import Fighter
from .environment import Arena


@dataclass(slots=True)
class Projectile:
    id: int
    owner: int
    target: int
    ability: Ability
    x: float
    y: float
    vx: float
    vy: float
    remaining: float

    def snapshot(self):
        return {"id": self.id, "owner": self.owner, "x": self.x, "y": self.y, "type": self.ability.type}


@dataclass(slots=True)
class World:
    fighters: list[Fighter]
    arena: Arena
    tick: int = 0
    time: float = 0
    projectiles: list[Projectile] = field(default_factory=list)
    done: bool = False
    winner: int | None = None
    condition: str = ""

    def snapshot(self):
        return {"tick": self.tick, "time": self.time, "fighters": [f.snapshot() for f in self.fighters],
                "projectiles": [p.snapshot() for p in self.projectiles], "done": self.done,
                "winner": self.winner, "condition": self.condition}
