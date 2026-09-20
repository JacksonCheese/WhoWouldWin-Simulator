from pydantic import Field, model_validator
from whowouldwin.characters.schema import Model


class Arena(Model):
    width: float = Field(default=120, ge=10, le=10000)
    height: float = Field(default=40, ge=10, le=1000)
    gravity: float = Field(default=28, gt=0, le=100)


class Rules(Model):
    bloodlusted: bool = False
    timeout: float = Field(default=180, gt=0, le=3600)
    timestep: float = Field(default=.05, ge=.01, le=.2)
    lethal: bool = False
    incapacitation_seconds: float = Field(default=3, gt=0)


class Scaling(Model):
    fighter_a: str = "expected"
    fighter_b: str = "expected"

    @model_validator(mode="after")
    def modes(self):
        if self.fighter_a not in {"low", "expected", "high"} or self.fighter_b not in {"low", "expected", "high"}:
            raise ValueError("Invalid scaling mode")
        return self


class Matchup(Model):
    fighter_a: str = "naruto"
    fighter_b: str = "omniman"
    arena: Arena = Arena()
    starting_distance: float = Field(default=60, ge=2)
    rules: Rules = Rules()
    scaling: Scaling = Scaling()
    seed: int = Field(default=42, ge=0, le=2**63-1)

    @model_validator(mode="after")
    def fits(self):
        if self.starting_distance > self.arena.width - 2:
            raise ValueError("Starting distance must fit inside arena margins")
        return self
