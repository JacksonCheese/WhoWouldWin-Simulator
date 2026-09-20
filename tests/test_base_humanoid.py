from pathlib import Path

from whowouldwin.cinematic.blender_backend.base_humanoid import HAND_POSES
from whowouldwin.cinematic.assets.validation import validate_character_package


ROOT = Path(__file__).resolve().parents[1]


def test_required_hand_pose_presets_are_reusable_and_bounded() -> None:
    assert {"OPEN_PALM", "CLOSED_FIST", "RELAXED", "CUPPED"} <= HAND_POSES.keys()
    for pose in HAND_POSES.values():
        assert 0 < pose["length"] <= 1
        assert 0 < pose["spread"] <= 1
        assert pose["forward"] > 0


def test_closed_fist_is_shorter_and_narrower_than_open_palm() -> None:
    open_palm = HAND_POSES["OPEN_PALM"]
    fist = HAND_POSES["CLOSED_FIST"]
    assert fist["length"] < open_palm["length"]
    assert fist["spread"] < open_palm["spread"]
    assert fist["forward"] < open_palm["forward"]


def test_athletic_base_is_a_valid_reusable_character_package() -> None:
    report = validate_character_package(
        ROOT / "assets/characters/base_male_athletic", inspect_blender=False
    )
    assert report.valid
    assert report.checks["required_bone_roles"] == 20
    assert report.checks["model_exists"] is True
