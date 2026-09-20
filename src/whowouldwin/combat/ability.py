from whowouldwin.characters.schema import Ability

ATTACK_TYPES = frozenset({"melee", "charged_melee", "projectile", "beam", "area", "grapple"})
DEFENSE_TYPES = frozenset({"dodge", "block"})
MOBILITY_TYPES = frozenset({"dash", "jump", "flight", "teleport"})

__all__ = ["Ability", "ATTACK_TYPES", "DEFENSE_TYPES", "MOBILITY_TYPES"]
