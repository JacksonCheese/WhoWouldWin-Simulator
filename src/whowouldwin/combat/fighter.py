from dataclasses import dataclass, field
from collections import Counter
from whowouldwin.characters.schema import Character, Ability


@dataclass(slots=True)
class Status:
    remaining: float
    magnitude: float
    source: int
    action: str


@dataclass(slots=True)
class Pending:
    ability: Ability
    remaining: float
    target_position: tuple[float, float]


@dataclass(slots=True)
class Fighter:
    slot: int
    profile: Character
    base: dict[str, float]
    x: float
    y: float = 1
    vx: float = 0
    vy: float = 0
    radius: float = 1
    health: float = 0
    stamina: float = 0
    energy: float = 0
    busy: float = 0
    decision: float = 0
    cooldowns: dict[str, float] = field(default_factory=dict)
    statuses: dict[str, Status] = field(default_factory=dict)
    pending: Pending | None = None
    defense: str = ""
    defense_time: float = 0
    flying: bool = False
    flight_time: float = 0
    form: str = ""
    form_time: float = 0
    modifiers: dict[str, float] = field(default_factory=dict)
    recent_actions: list[str] = field(default_factory=list)
    last_action: str = "Ready"
    debug: dict[str, float] = field(default_factory=dict)
    uses: Counter = field(default_factory=Counter)
    hits: Counter = field(default_factory=Counter)
    damage_by_ability: Counter = field(default_factory=Counter)
    damage_dealt: float = 0
    damage_received: float = 0
    last_damage_action: str = ""
    last_damage_source: int | None = None
    control_time: float = 0
    control_action: str = ""
    stun_immunity: float = 0

    def __post_init__(self):
        self.health = self.profile.resources.health
        self.stamina = self.profile.resources.stamina
        self.energy = self.profile.resources.energy

    def stat(self, key: str) -> float:
        value = self.base[key] * self.modifiers.get(key, 1)
        if key == "striking_power" and "power" in self.statuses:
            value *= 1 + self.statuses["power"].magnitude
        if key == "movement_speed" and "slow" in self.statuses:
            value *= max(.15, 1 - self.statuses["slow"].magnitude)
        return value

    @property
    def alive(self) -> bool:
        return self.health > 0

    @property
    def position(self) -> tuple[float, float]:
        return self.x, self.y

    @property
    def health_fraction(self) -> float:
        return self.health / self.profile.resources.health

    def snapshot(self) -> dict:
        return {"slot": self.slot, "id": self.profile.identity.id, "name": self.profile.identity.name,
                "x": self.x, "y": self.y, "vx": self.vx, "vy": self.vy, "radius": self.radius,
                "health": self.health, "max_health": self.profile.resources.health,
                "stamina": self.stamina, "max_stamina": self.profile.resources.stamina,
                "energy": self.energy, "max_energy": self.profile.resources.energy,
                "flying": self.flying, "form": self.form, "form_time": self.form_time,
                "defense": self.defense, "statuses": {k: v.remaining for k, v in self.statuses.items()},
                "cooldowns": dict(self.cooldowns), "action": self.last_action, "debug": dict(self.debug),
                "pending": self.pending.ability.type if self.pending else None}
