from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass(slots=True)
class CombatEvent:
    type: str
    tick: int
    timestamp: float
    fighter: int | None = None
    target: int | None = None
    action: str | None = None
    position: tuple[float, float] | None = None
    values: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
