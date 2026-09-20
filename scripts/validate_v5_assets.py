"""Validate V5 package binding without grading the temporary V4 body as final art."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/blender_combat_v5_assets"
V4 = ROOT / "outputs/blender_combat_v4_humanoid"
SCENE = bpy.context.scene


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    v4_manifest = json.loads((V4 / "manifest.json").read_text())
    bindings = json.loads((OUT / "review/package-bindings.json").read_text())
    assert SCENE["wws_source_checksum"] == v4_manifest["source_checksum"]
    assert SCENE["wws_source_outcome_digest"] == v4_manifest["source_outcome_digest"]
    assert SCENE["wws_asset_integration_mode"] == "derived_v4_fixture_no_geometry_generation"
    assert bindings["generated_new_body"] is False
    assert sha256(OUT / "source/events.json") == sha256(V4 / "source/events.json")
    assert len([action for action in bpy.data.actions if action.name.startswith("WWS_LIB_")]) == 40

    character_checks = {}
    for source_prefix, character_id in (
        ("fighter_a", "v4_evaluation_a"),
        ("fighter_b", "v4_evaluation_b"),
    ):
        source_rig = bpy.data.objects[f"{source_prefix}_ProductionRig"]
        source_body = bpy.data.objects[f"{source_prefix}_ProductionBody"]
        working = bindings["characters"][character_id]
        rig = bpy.data.objects[working["working_rig"]]
        meshes = [bpy.data.objects[name] for name in working["working_meshes"]]
        assert source_rig.hide_render and source_body.hide_render
        assert rig.data is not source_rig.data
        assert all(mesh.data is not source_body.data for mesh in meshes)
        assert all(mesh.type == "MESH" and not mesh.hide_render for mesh in meshes)
        assert all(
            any(
                modifier.type == "ARMATURE" and modifier.object == rig
                for modifier in mesh.modifiers
            )
            for mesh in meshes
        )
        assert all(
            math.isfinite(value)
            for mesh in meshes
            for vertex in mesh.data.vertices
            for value in vertex.co
        )
        character_checks[character_id] = {
            "working_rig": rig.name,
            "working_meshes": [mesh.name for mesh in meshes],
            "vertices": sum(len(mesh.data.vertices) for mesh in meshes),
            "source_data_untouched": True,
            "armature_modifiers_rebound": True,
        }

    report = {
        "checks_passed": True,
        "source_checksum": SCENE["wws_source_checksum"],
        "outcome_digest": SCENE["wws_source_outcome_digest"],
        "source_events_sha256": sha256(OUT / "source/events.json"),
        "source_events_identical_to_v4": True,
        "native_actions": 40,
        "character_package_schema": SCENE["wws_character_package_schema"],
        "integration_mode": SCENE["wws_asset_integration_mode"],
        "characters": character_checks,
        "qualification": (
            "This validates package-derived working copies, source preservation, rig binding, "
            "and provenance. The visible bodies remain V4 development fixtures because no "
            "licensed authored production humanoid was locally available."
        ),
    }
    (OUT / "review/scene-validation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

