"""Validated, versionable character documents. All units are gameplay estimates."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

PLACEHOLDER_NOTE = "Development placeholder scaling. Replace with researched feat-based values before publishing matchup claims."


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, validate_default=True)


class Estimate(Model):
    low: float = Field(gt=0)
    expected: float = Field(gt=0)
    high: float = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self):
        if not self.low <= self.expected <= self.high:
            raise ValueError("Expected low <= expected <= high")
        return self


Stat = float | Estimate


class Identity(Model):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(min_length=1)
    universe: str
    version: str


class Physical(Model):
    strength: Stat = 100
    striking_power: Stat = 100
    durability: Stat = 100
    movement_speed: Stat = 12
    combat_speed: Stat = 1
    reaction_speed: Stat = 1
    stamina: Stat = 100
    mass: Stat = 80
    reach: Stat = 1.5

    @model_validator(mode="after")
    def positive(self):
        for key, value in self.model_dump().items():
            if isinstance(value, (float, int)) and value <= 0:
                raise ValueError(f"physical.{key} must be positive")
        return self


class Resources(Model):
    health: float = Field(default=800, gt=0)
    stamina: float = Field(default=100, gt=0)
    energy: float = Field(default=100, gt=0)
    regeneration: float = Field(default=0, ge=0)
    stamina_regen: float = Field(default=12, ge=0)
    energy_regen: float = Field(default=4, ge=0)


class Combat(Model):
    battle_iq: float = Field(default=.7, ge=0, le=1)
    aggression: float = Field(default=.65, ge=0, le=1)
    risk_tolerance: float = Field(default=.5, ge=0, le=1)
    preferred_range: float = Field(default=5, ge=0)
    accuracy: float = Field(default=.85, ge=0, le=1)
    evasion: float = Field(default=.2, ge=0, le=1)
    blocking: float = Field(default=.7, ge=0, le=1)
    grappling: float = Field(default=.5, ge=0, le=1)


class Mobility(Model):
    grounded: bool = True
    flight: bool = False
    jump: bool = True
    dash: bool = True
    teleport: bool = False


class Condition(Model):
    max_health_fraction: float = Field(default=1, ge=0, le=1)
    min_health_fraction: float = Field(default=0, ge=0, le=1)
    target_status: str | None = None


class StatusSpec(Model):
    id: Literal["stun", "slow", "burn", "regen", "decoy", "power", "shield", "incapacitated"]
    duration: float = Field(gt=0, le=60)
    magnitude: float = Field(default=1, ge=0, le=500)


class Ability(Model):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    name: str
    type: Literal["melee", "charged_melee", "projectile", "beam", "area", "dodge", "block", "dash", "jump", "flight", "grapple", "teleport", "buff", "transform", "regenerate"]
    range: float = Field(default=3, ge=0)
    minimum_range: float = Field(default=0, ge=0)
    startup: float = Field(default=.15, ge=0, le=20)
    active: float = Field(default=.15, gt=0, le=30)
    recovery: float = Field(default=.3, ge=0, le=20)
    cooldown: float = Field(default=1, ge=.05, le=300)
    stamina_cost: float = Field(default=0, ge=0)
    energy_cost: float = Field(default=0, ge=0)
    damage: float = Field(default=0, ge=0)
    damage_type: str = "physical"
    projectile_speed: float = Field(default=40, gt=0)
    area_of_effect: float = Field(default=0, ge=0)
    hit_modifier: float = Field(default=0, ge=-1, le=1)
    critical_chance: float = Field(default=.05, ge=0, le=1)
    knockback: float = Field(default=0, ge=0, le=100)
    stun: float = Field(default=0, ge=0, le=5)
    status_effects: tuple[StatusSpec, ...] = ()
    mobility_distance: float = Field(default=0, ge=0, le=100)
    targeting: Literal["enemy", "self", "ground"] = "enemy"
    required_form: str | None = None
    transformation: str | None = None
    condition: Condition = Condition()
    utility: float = Field(default=1, gt=0, le=10)

    @model_validator(mode="after")
    def coherent(self):
        if self.minimum_range > self.range:
            raise ValueError("minimum_range exceeds range")
        if self.type == "transform" and not self.transformation:
            raise ValueError("transform needs a transformation id")
        if self.damage > 0 and self.targeting == "self":
            raise ValueError("damaging abilities must target enemy or ground")
        return self


class Transformation(Model):
    id: str
    name: str
    duration: float = Field(gt=0, le=120)
    modifiers: dict[str, float]

    @model_validator(mode="after")
    def valid_modifiers(self):
        for key, value in self.modifiers.items():
            if key not in Physical.model_fields or not 0 < value <= 5:
                raise ValueError("Transformation requires physical-stat multipliers in (0, 5]")
        return self


class AI(Model):
    randomness: float = Field(default=.2, ge=0, le=1)
    defensive_bias: float = Field(default=1, gt=0, le=5)
    special_bias: float = Field(default=1, gt=0, le=5)
    repeat_penalty: float = Field(default=.2, ge=0, le=1)


class Character(Model):
    identity: Identity
    scaling_note: str = Field(min_length=20)
    physical: Physical
    resources: Resources
    combat: Combat
    mobility: Mobility
    resistances: dict[str, float] = {}
    abilities: tuple[Ability, ...] = Field(min_length=1)
    transformations: tuple[Transformation, ...] = ()
    ai: AI = AI()

    @model_validator(mode="after")
    def references(self):
        ids = [a.id for a in self.abilities]
        if len(set(ids)) != len(ids):
            raise ValueError("Ability ids must be unique")
        forms = {t.id for t in self.transformations}
        if len(forms) != len(self.transformations):
            raise ValueError("Transformation ids must be unique")
        for a in self.abilities:
            if a.transformation and a.transformation not in forms or a.required_form and a.required_form not in forms:
                raise ValueError(f"Unknown form in {a.id}")
            capability = {"flight": "flight", "jump": "jump", "dash": "dash", "teleport": "teleport"}.get(a.type)
            if capability and not getattr(self.mobility, capability):
                raise ValueError(f"{a.id} requires mobility.{capability}")
            if a.energy_cost > self.resources.energy or a.stamina_cost > self.resources.stamina:
                raise ValueError(f"{a.id} costs more than maximum resources")
        if any(not -1 <= r <= .95 for r in self.resistances.values()):
            raise ValueError("Resistances must lie in [-1, .95]")
        return self

    def stats(self, scaling: str = "expected") -> dict[str, float]:
        if scaling not in {"low", "expected", "high"}:
            raise ValueError("Scaling must be low, expected or high")
        return {k: float(getattr(v, scaling) if isinstance(v, Estimate) else v)
                for k, v in self.physical.__dict__.items()}
