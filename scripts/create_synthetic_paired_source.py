"""Create a tiny synchronized two-armature fixture for importer smoke testing.

The fixture deliberately reuses rejected diagnostic motion. It proves file,
timeline, adapter and root-separation mechanics only; it is not animation art.
"""
from __future__ import annotations

import json
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/combat_motion_lab_source_readiness"
SYNTHETIC = OUTPUT / "synthetic"

ROLES = (
    "root", "pelvis", "spine", "chest", "neck", "head",
    "clavicle.L", "clavicle.R", "upper_arm.L", "upper_arm.R",
    "forearm.L", "forearm.R", "hand.L", "hand.R", "thigh.L",
    "thigh.R", "shin.L", "shin.R", "foot.L", "foot.R",
)


def identity_adapter(adapter_id: str) -> dict:
    return {
        "schema_version": 1,
        "adapter_id": adapter_id,
        "standard_to_target": {role: role for role in ROLES},
        "optional_bones": {},
        "finger_chains": {},
        "corrective_shape_keys": [],
        "source_rest_pose": "SOURCE",
        "target_rest_pose": "A_POSE",
        "rotation_offsets_degrees": {},
    }


def main() -> None:
    SYNTHETIC.mkdir(parents=True, exist_ok=True)
    payload = []
    pairs = (
        ("fighter_a_Rig", "SyntheticActorA", "SyntheticActorAAction"),
        ("fighter_b_Rig", "SyntheticActorB", "SyntheticActorBAction"),
    )
    for source_name, object_name, action_name in pairs:
        source = bpy.data.objects[source_name]
        rig = source.copy()
        rig.data = source.data.copy()
        rig.name = object_name
        action = source.animation_data.action.copy()
        action.name = action_name
        action["wws_source_kind"] = "diagnostic_fixture"
        action["wws_production_approved"] = False
        rig.animation_data_create()
        rig.animation_data.action = action
        payload.extend((rig, action))
    path = SYNTHETIC / "paired_import_smoke.blend"
    bpy.data.libraries.write(str(path), set(payload), fake_user=True, compress=True)

    for side in ("a", "b"):
        (SYNTHETIC / f"identity_{side}.json").write_text(
            json.dumps(identity_adapter(f"synthetic.identity.{side}"), indent=2)
        )
    definition = {
        "schema_version": 1,
        "performance_id": "synthetic_paired_import_smoke",
        "path": "synthetic/paired_import_smoke.blend",
        "format": "blend",
        "source_kind": "diagnostic_fixture",
        "frame_rate": 30,
        "start_frame": 1,
        "end_frame": 120,
        "forward_axis": "-Y",
        "up_axis": "Z",
        "unit_scale_meters": 1.0,
        "root_motion": "extract",
        "quality_status": "unreviewed",
        "actors": [
            {"actor_id": "fighter_a", "source_armature": "SyntheticActorA", "action_name": "SyntheticActorAAction", "rig_adapter": "synthetic/identity_a.json"},
            {"actor_id": "fighter_b", "source_armature": "SyntheticActorB", "action_name": "SyntheticActorBAction", "rig_adapter": "synthetic/identity_b.json"},
        ],
        "support_phases": [
            {"actor_id": "fighter_a", "side": "L", "start_frame": 1, "planted_end_frame": 8, "heel_release_frame": 9, "ball_release_frame": 10, "toe_release_frame": 11, "recovery_frame": 14},
            {"actor_id": "fighter_b", "side": "R", "start_frame": 1, "planted_end_frame": 10, "heel_release_frame": 11, "ball_release_frame": 12, "toe_release_frame": 13, "recovery_frame": 16},
        ],
        "contacts": [
            {"contact_id": "synthetic_contact", "actor_id": "fighter_b", "effector_role": "hand.R", "target_actor_id": "fighter_a", "target_role": "chest", "approach_frame": 78, "contact_frame": 85, "hold_start_frame": 85, "hold_end_frame": 88, "recoil_frame": 89, "release_frame": 93, "intended_surface_gap": 0.025}
        ],
        "provenance": {
            "license_name": "Internal diagnostic fixture",
            "commercial_use_allowed": True,
            "redistribution_allowed": True,
            "performers_or_animators": ["WWS synthetic test generator"],
            "source_take": "diagnostic-fixture-not-production",
            "acquisition_date": "2026-09-13",
        },
    }
    (SYNTHETIC / "paired_import_smoke.json").write_text(json.dumps(definition, indent=2))
    print("SYNTHETIC_PAIRED_SOURCE_CREATED", path)


if __name__ == "__main__":
    main()
