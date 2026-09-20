"""Create the isolated paired-source gate without pretending motion was replaced."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/combat_motion_lab_hero_exchange"
OUTPUT = ROOT / "outputs/combat_motion_lab_paired_source_gate"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_specification():
    return {
        "schema_version": 1,
        "performance_id": "naruto_omniman_hero_exchange_paired_v1",
        "path": "source/paired_hero_exchange.blend",
        "format": "blend",
        "source_kind": "authored",
        "frame_rate": 30,
        "start_frame": 1,
        "end_frame": 120,
        "forward_axis": "-Y",
        "up_axis": "Z",
        "unit_scale_meters": 1.0,
        "root_motion": "extract",
        "quality_status": "unreviewed",
        "actors": [
            {"actor_id": "fighter_a", "source_armature": "OmniSource", "action_name": "OmniPairedExchange", "rig_adapter": "source/omni_source_rig_adapter.json"},
            {"actor_id": "fighter_b", "source_armature": "NarutoSource", "action_name": "NarutoPairedExchange", "rig_adapter": "source/naruto_source_rig_adapter.json"},
        ],
        "support_phases": [
            {"actor_id": "fighter_a", "side": "L", "start_frame": 1, "planted_end_frame": 9, "heel_release_frame": 11, "ball_release_frame": 13, "toe_release_frame": 14, "recovery_frame": 18},
            {"actor_id": "fighter_b", "side": "R", "start_frame": 25, "planted_end_frame": 36, "heel_release_frame": 38, "ball_release_frame": 40, "toe_release_frame": 41, "recovery_frame": 45},
            {"actor_id": "fighter_b", "side": "L", "start_frame": 70, "planted_end_frame": 88, "heel_release_frame": 90, "ball_release_frame": 92, "toe_release_frame": 94, "recovery_frame": 98},
        ],
        "contacts": [
            {"contact_id": "counter_guard", "actor_id": "fighter_b", "effector_role": "hand.R", "target_actor_id": "fighter_a", "target_role": "forearm.L", "approach_frame": 32, "contact_frame": 38, "hold_start_frame": 38, "hold_end_frame": 39, "recoil_frame": 40, "release_frame": 43, "intended_surface_gap": 0.0},
            {"contact_id": "guard_redirect", "actor_id": "fighter_b", "effector_role": "hand.L", "target_actor_id": "fighter_a", "target_role": "forearm.L", "approach_frame": 42, "contact_frame": 47, "hold_start_frame": 47, "hold_end_frame": 48, "recoil_frame": 49, "release_frame": 53, "intended_surface_gap": 0.0},
            {"contact_id": "rasengan", "actor_id": "fighter_b", "effector_role": "hand.R", "target_actor_id": "fighter_a", "target_role": "chest", "approach_frame": 78, "contact_frame": 85, "hold_start_frame": 85, "hold_end_frame": 88, "recoil_frame": 89, "release_frame": 93, "intended_surface_gap": 0.025},
        ],
        "provenance": {
            "license_name": "PENDING",
            "commercial_use_allowed": False,
            "redistribution_allowed": False,
            "performers_or_animators": ["PENDING"],
            "source_take": "PENDING",
            "acquisition_date": "PENDING"
        },
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for folder in ("source", "review", "renders"):
        (OUTPUT / folder).mkdir(exist_ok=True)
    (OUTPUT / "source/events.json").write_bytes((SOURCE / "source/events.json").read_bytes())
    spec = source_specification()
    (OUTPUT / "source/paired-performance.required.json").write_text(json.dumps(spec, indent=2))
    scene = bpy.context.scene
    scene["wws_paired_source_gate"] = True
    scene["wws_paired_source_status"] = "MISSING_EXTERNAL_SOURCE"
    scene["wws_motion_quality_status"] = "DIAGNOSTIC_REJECTED"
    scene["wws_source_control_scene_sha256"] = digest(SOURCE / "scene.blend")
    scene["wws_source_events_sha256"] = digest(OUTPUT / "source/events.json")
    scene["wws_paired_import_contract"] = "PairedPerformanceDefinition/v1"
    scene["wws_build_utc"] = datetime.now(timezone.utc).isoformat()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "scene.blend"))
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scene_sha256": digest(OUTPUT / "scene.blend"),
        "source_control_scene": str(SOURCE / "scene.blend"),
        "source_control_scene_sha256": digest(SOURCE / "scene.blend"),
        "events_sha256": digest(OUTPUT / "source/events.json"),
        "source_status": "missing",
        "current_actions": ["HERO_PAIRED_OMNI", "HERO_PAIRED_NARUTO"],
        "current_actions_quality": "diagnostic_rejected",
        "animation_changed": False,
        "reason": "No approved paired authored or paired-mocap source is available locally.",
    }
    (OUTPUT / "review/build-provenance.json").write_text(json.dumps(payload, indent=2))
    print("PAIRED_SOURCE_GATE_BUILT", json.dumps(payload))


if __name__ == "__main__":
    main()
