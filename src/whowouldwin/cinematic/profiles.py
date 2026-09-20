"""Shared presentation vocabulary and data-driven ability bindings."""
import json
from pathlib import Path

STATES = ("Idle", "CombatIdle", "Run", "Sprint", "Dash", "Jump", "Fall", "FlightIdle", "FlightMove",
          "LightAttack", "HeavyAttack", "SpecialAttack", "RangedAttack", "Block", "Dodge", "HitLight",
          "HitHeavy", "Knockback", "Knockdown", "Recovery", "Transformation", "Defeat")
PRIMITIVES = {"Approach", "CircleOpponent", "AnticipateAttack", "Lunge", "DashPast", "JumpAttack", "AerialApproach",
              "ProjectileCast", "BeamCast", "BlockImpact", "SuccessfulDodge", "NearMiss", "MeleeHit", "HeavyHit",
              "Launcher", "GroundImpact", "WallImpact", "Recovery", "Transformation", "Finisher", "Clash",
              "CloneFeint", "Guard", "Flight", "Teleport", "Buff", "Charge"}


def presentation_directory() -> Path:
    package = Path(__file__).resolve().parents[1] / "data" / "presentation"
    return package if package.is_dir() else Path(__file__).resolve().parents[3] / "data" / "presentation"


def load_visual_profile(character: dict, directory: Path | None = None) -> dict:
    path = (directory or presentation_directory()) / f"{character['identity']['id']}.json"
    profile = json.loads(path.read_text())
    validate_visual_profile(profile, character)
    return profile


def validate_visual_profile(profile: dict, character: dict):
    if profile["characterId"] != character["identity"]["id"]:
        raise ValueError("Visual profile character ID does not match combat profile")
    mapping = {m["abilityId"]: m for m in profile["abilities"]}
    ids = {a["id"] for a in character["abilities"]}
    if set(mapping) != ids or len(mapping) != len(profile["abilities"]):
        raise ValueError(f"Missing, duplicate or obsolete presentation mappings: {ids.symmetric_difference(mapping)}")
    if set(profile["requiredStates"]) != set(STATES):
        raise ValueError("Visual profile must declare every required animation state")
    for item in mapping.values():
        if item["state"] not in STATES or item["primitive"] not in PRIMITIVES:
            raise ValueError(f"Invalid animation/primitive in {item['abilityId']}")
        if not item["vfx"] or not item["sound"]:
            raise ValueError(f"Missing VFX or sound mapping for {item['abilityId']}")
