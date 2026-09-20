"""Provider-neutral animation classification and character override resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import CharacterPackageManifest


CLASSIFICATION_ALIASES = {
    "dash": ("dash", "burst", "blitz", "sprintstart"),
    "heavy_cross": ("heavycross", "powerpunch", "strongpunch", "haymaker"),
    "hook": ("hook", "lefthook", "righthook"),
    "kick": ("kick", "frontkick", "roundhouse"),
    "dodge": ("dodge", "evade", "sidestep", "leanback"),
    "hit_heavy": ("heavyhit", "bighit", "hitreaction", "impactreaction"),
    "launch": ("launch", "knockback", "flyback"),
    "airborne_tumble": ("airbornetumble", "airtumble", "fallloop"),
    "hard_landing": ("hardlanding", "landhard", "impactlanding"),
    "skid": ("skid", "groundslide", "slideback"),
    "recovery": ("recovery", "getup", "recover"),
}


@dataclass(frozen=True)
class ResolvedClip:
    action: str
    clip_id: str
    source: str


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def classify_animation_name(value: str) -> list[tuple[str, float]]:
    normalized = _normalized(value)
    matches = []
    for action, aliases in CLASSIFICATION_ALIASES.items():
        score = max(
            (
                1.0 if normalized == alias else 0.82
                for alias in aliases
                if alias in normalized or normalized in alias
            ),
            default=0.0,
        )
        if score:
            matches.append((action, score))
    return sorted(matches, key=lambda item: (-item[1], item[0]))


def resolve_animation(
    manifest: CharacterPackageManifest, action: str
) -> ResolvedClip | None:
    if action in manifest.custom_animation_overrides:
        return ResolvedClip(
            action=action,
            clip_id=manifest.custom_animation_overrides[action],
            source="character_override",
        )
    custom = next((clip for clip in manifest.animation_clips if clip.action == action), None)
    if custom:
        return ResolvedClip(action=action, clip_id=custom.clip_id, source="character_clip")
    if action in manifest.generic_animation_compatibility:
        return ResolvedClip(action=action, clip_id=action, source="generic_fallback")
    return None

