from pathlib import Path

import pytest
from pydantic import ValidationError

from whowouldwin.cinematic.assets.paired_animation import validate_paired_source
from whowouldwin.cinematic.assets.schemas import PairedPerformanceDefinition


def definition(**updates):
    raw = {
        "performance_id": "hero_exchange_v2",
        "path": "paired/hero_exchange.blend",
        "format": "blend",
        "source_kind": "paired_mocap",
        "frame_rate": 30,
        "start_frame": 1,
        "end_frame": 120,
        "actors": [
            {"actor_id": "fighter_a", "source_armature": "OmniSource", "action_name": "OmniAction", "rig_adapter": "omni_adapter.json"},
            {"actor_id": "fighter_b", "source_armature": "NarutoSource", "action_name": "NarutoAction", "rig_adapter": "naruto_adapter.json"},
        ],
        "support_phases": [
            {"actor_id": "fighter_a", "side": "L", "start_frame": 1, "planted_end_frame": 14, "heel_release_frame": 16, "ball_release_frame": 18, "toe_release_frame": 19, "recovery_frame": 22},
            {"actor_id": "fighter_b", "side": "R", "start_frame": 20, "planted_end_frame": 32, "heel_release_frame": 34, "ball_release_frame": 36, "toe_release_frame": 38, "recovery_frame": 42},
        ],
        "contacts": [
            {"contact_id": "rasengan", "actor_id": "fighter_b", "effector_role": "hand.R", "target_actor_id": "fighter_a", "target_role": "chest", "approach_frame": 78, "contact_frame": 85, "hold_start_frame": 85, "hold_end_frame": 88, "recoil_frame": 89, "release_frame": 91},
        ],
        "provenance": {"license_name": "Internal test", "commercial_use_allowed": True, "redistribution_allowed": True, "performers_or_animators": ["WWS test"], "source_take": "synthetic-001", "acquisition_date": "2026-09-13"},
    }
    raw.update(updates)
    return PairedPerformanceDefinition.model_validate(raw)


def test_paired_performance_requires_both_actors():
    item = definition()
    raw = item.model_dump(mode="json")
    raw["actors"][1]["actor_id"] = "fighter_a"
    with pytest.raises(ValidationError, match="exactly fighter_a and fighter_b"):
        PairedPerformanceDefinition.model_validate(raw)


def test_diagnostic_fixture_cannot_be_approved():
    with pytest.raises(ValidationError, match="diagnostic fixture"):
        definition(source_kind="diagnostic_fixture", quality_status="approved")


def test_missing_paired_source_is_actionable(tmp_path: Path):
    (tmp_path / "omni_adapter.json").write_text("{}")
    (tmp_path / "naruto_adapter.json").write_text("{}")
    report = validate_paired_source(definition(), tmp_path)
    assert not report["valid"]
    assert report["errors"][0]["code"] == "paired_source_missing"
    assert "Supply" in report["errors"][0]["suggestion"]


def test_contact_hold_recoil_release_must_be_ordered():
    raw = definition().model_dump(mode="json")
    raw["contacts"][0]["recoil_frame"] = 84
    with pytest.raises(ValidationError, match="Partner-contact frames must be ordered"):
        PairedPerformanceDefinition.model_validate(raw)


def test_approved_source_requires_commercial_rights():
    raw = definition().model_dump(mode="json")
    raw["quality_status"] = "approved"
    raw["provenance"]["commercial_use_allowed"] = False
    with pytest.raises(ValidationError, match="must allow commercial use"):
        PairedPerformanceDefinition.model_validate(raw)


def test_validator_rejects_incomplete_support_metadata(tmp_path: Path):
    item = definition()
    raw = item.model_dump(mode="json")
    raw["support_phases"] = raw["support_phases"][:1]
    incomplete = PairedPerformanceDefinition.model_validate(raw)
    (tmp_path / "omni_adapter.json").write_text("{}")
    (tmp_path / "naruto_adapter.json").write_text("{}")
    report = validate_paired_source(incomplete, tmp_path)
    assert "support_phases_incomplete" in {error["code"] for error in report["errors"]}
