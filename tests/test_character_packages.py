import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from whowouldwin.cinematic.assets.animation import (
    classify_animation_name,
    resolve_animation,
)
from whowouldwin.cinematic.assets.package import load_character_package
from whowouldwin.cinematic.assets.rig_mapping import suggest_rig_mapping
from whowouldwin.cinematic.assets.schemas import (
    AbilityDefinition,
    CharacterPackageManifest,
    REQUIRED_HUMANOID_ROLES,
    RigAdapterDefinition,
)
from whowouldwin.cinematic.assets.validation import validate_character_package


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "assets/characters/v4_evaluation_a"


def test_character_package_loads_presentation_only_contracts():
    package = load_character_package(FIXTURE)
    assert package.manifest.character_id == "v4_evaluation_a"
    assert set(package.rig_adapter.standard_to_target) == set(REQUIRED_HUMANOID_ROLES)
    assert package.abilities[0].simulator_decides_outcome is True
    assert package.abilities[0].authority == "presentation"
    assert resolve_animation(package.manifest, "heavy_cross").source == "generic_fallback"


def test_ability_contract_rejects_simulation_outcome_fields():
    raw = {
        "ability_id": "strike",
        "animation": "heavy_cross",
        "success": True,
    }
    with pytest.raises(ValidationError):
        AbilityDefinition.model_validate(raw)


def test_rig_mapping_recognizes_common_names_and_exposes_ambiguity():
    names = [
        "mixamorig:Root", "mixamorig:Hips", "mixamorig:Spine", "mixamorig:Spine2",
        "mixamorig:Neck", "mixamorig:Head", "mixamorig:LeftShoulder",
        "mixamorig:RightShoulder", "mixamorig:LeftArm", "mixamorig:RightArm",
        "mixamorig:LeftForeArm", "mixamorig:RightForeArm", "mixamorig:LeftHand",
        "mixamorig:RightHand", "mixamorig:LeftUpLeg", "mixamorig:RightUpLeg",
        "mixamorig:LeftLeg", "mixamorig:RightLeg", "mixamorig:LeftFoot",
        "mixamorig:RightFoot",
    ]
    proposal = suggest_rig_mapping(names, "Armature")
    assert proposal.unresolved_required_roles == []
    assert proposal.proposed_standard_to_target["pelvis"] == "mixamorig:Hips"
    ambiguous = suggest_rig_mapping([*names, "other:LeftArm"], "Armature")
    upper_left = next(item for item in ambiguous.suggestions if item.role == "upper_arm.L")
    assert upper_left.ambiguous and upper_left.selected is None
    assert ambiguous.manual_review_required


def test_mapping_rejects_incomplete_authoritative_adapter():
    package = load_character_package(FIXTURE)
    raw = package.rig_adapter.model_dump(mode="json")
    raw["standard_to_target"].pop("head")
    with pytest.raises(ValidationError, match="missing required roles"):
        RigAdapterDefinition.model_validate(raw)


def test_animation_name_classification_is_provider_neutral():
    assert classify_animation_name("Hero_PowerPunch_take03")[0][0] == "heavy_cross"
    assert classify_animation_name("Mocap_ground_slide_back")[0][0] == "skid"


def test_fixture_package_passes_schema_validation_without_blender():
    report = validate_character_package(FIXTURE, inspect_blender=False)
    assert report.valid
    assert report.checks["core_animation_compatibility"] == 11
    assert not any(issue.code == "external_asset_reference" for issue in report.warnings)
    assert any(issue.code == "blender_inspection_skipped" for issue in report.warnings)


def test_character_package_accepts_unskinned_accessory_objects():
    package = load_character_package(FIXTURE)
    raw = package.manifest.model_dump(mode="json")
    raw["accessory_objects"] = ["Cape", "Hair"]
    manifest = CharacterPackageManifest.model_validate(raw)
    assert manifest.accessory_objects == ["Cape", "Hair"]
