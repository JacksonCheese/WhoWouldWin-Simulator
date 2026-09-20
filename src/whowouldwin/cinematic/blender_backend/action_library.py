"""Provider-neutral catalog and selection rules for reusable humanoid animation clips."""

from dataclasses import dataclass

STANDARD_HUMANOID_BONES = (
    "root",
    "pelvis",
    "spine",
    "chest",
    "neck",
    "head",
    "clavicle.L",
    "clavicle.R",
    "upper_arm.L",
    "upper_arm.R",
    "forearm.L",
    "forearm.R",
    "hand.L",
    "hand.R",
    "thigh.L",
    "thigh.R",
    "shin.L",
    "shin.R",
    "foot.L",
    "foot.R",
)

CLIP_CATEGORIES = {
    "locomotion": (
        "combat_idle",
        "stance",
        "step_forward",
        "step_back",
        "sprint",
        "dash",
        "aerial_travel",
    ),
    "attacks": (
        "jab",
        "cross",
        "heavy_cross",
        "hook",
        "uppercut",
        "body_punch",
        "front_kick",
        "roundhouse",
        "flying_punch",
        "aerial_kick",
        "downward_strike",
    ),
    "defense": (
        "dodge_left",
        "dodge_right",
        "backstep",
        "duck",
        "lean_dodge",
        "block_high",
        "block_body",
    ),
    "reactions": (
        "hit_head",
        "hit_body",
        "heavy_hit",
        "stagger",
        "spin_reaction",
        "launch_backward",
        "launch_upward",
        "airborne_tumble",
        "wall_impact",
        "ground_impact",
    ),
    "recovery": (
        "hard_landing",
        "landing_recoil",
        "ground_skid",
        "get_up",
        "aerial_recovery",
    ),
}

CLIP_NAMES = tuple(clip for category in CLIP_CATEGORIES.values() for clip in category)


@dataclass(frozen=True)
class ReactionChoice:
    clip_id: str
    launch_clip_id: str | None
    family: str


def identity_bone_map() -> dict[str, str]:
    """Return the generic rig's standard-to-target mapping."""
    return {bone: bone for bone in STANDARD_HUMANOID_BONES}


def choose_reaction(
    *, attack_family: str, direction: tuple[float, float, float], relative_power: float
) -> ReactionChoice:
    """Select a readable reaction from attack region, direction and severity."""
    _, _, vertical = direction
    if vertical > 0.55:
        return ReactionChoice("heavy_hit", "launch_upward", "upward_launch")
    if relative_power >= 0.8:
        return ReactionChoice("heavy_hit", "launch_backward", "heavy_launch")
    if attack_family in {"kick", "body", "body_punch"}:
        return ReactionChoice("hit_body", None, "body")
    if attack_family in {"head", "hook", "cross"}:
        return ReactionChoice("hit_head", None, "head")
    return ReactionChoice("stagger", None, "stagger")


def default_clip_for_action(action: str, *, actor: str = "fighter_a") -> str:
    """Map the presentation action vocabulary onto the generic authored pack."""
    mapping = {
        "idle": "combat_idle",
        "combat_stance": "stance",
        "dash": "dash",
        "sprint": "sprint",
        "jump": "aerial_travel",
        "aerial_movement": "airborne_tumble",
        "punch": "cross",
        "heavy_punch": "heavy_cross",
        "kick": "front_kick",
        "dodge": "dodge_left" if actor == "fighter_b" else "dodge_right",
        "block": "block_high",
        "hit_reaction": "heavy_hit",
        "knockback": "launch_backward",
        "launch": "launch_backward",
        "fall": "airborne_tumble",
        "landing": "hard_landing",
        "recovery": "get_up",
        "wall_impact": "wall_impact",
    }
    return mapping[action]
