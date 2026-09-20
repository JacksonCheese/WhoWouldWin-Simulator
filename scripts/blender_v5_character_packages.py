"""Bind the exact V4 choreography through CharacterPackage working copies.

Run against outputs/blender_combat_v4_humanoid/scene.blend. This milestone has no
external production asset, so the V4 body is cloned as an explicit development
fixture. No geometry or motion is regenerated.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/blender_combat_v5_assets"
sys.path.insert(0, str(ROOT / "src"))

from whowouldwin.cinematic.assets.blender_import import (
    import_character_model,
    retarget_package_to_source,
)


PACKAGES = (
    ROOT / "assets/characters/v4_evaluation_a/manifest.json",
    ROOT / "assets/characters/v4_evaluation_b/manifest.json",
)
SCENE = bpy.context.scene


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_markers():
    markers = [(item.name, item.frame, item.camera) for item in SCENE.timeline_markers]
    for marker in list(SCENE.timeline_markers):
        SCENE.timeline_markers.remove(marker)
    return markers


def restore_markers(markers) -> None:
    for name, frame, camera in markers:
        marker = SCENE.timeline_markers.new(name, frame=frame)
        marker.camera = camera


def suspend_vfx():
    states = []
    for obj in bpy.data.objects:
        if not obj.name.startswith("vfx-"):
            continue
        curves = []
        action = obj.animation_data.action if obj.animation_data else None
        if action:
            for curve in action.fcurves:
                if curve.data_path in {"hide_render", "hide_viewport"}:
                    curves.append((curve, curve.mute))
                    curve.mute = True
        states.append((obj, obj.hide_render, curves))
        obj.hide_render = True
    return states


def restore_vfx(states) -> None:
    for obj, hidden, curves in states:
        obj.hide_render = hidden
        for curve, muted in curves:
            curve.mute = muted


def render_video(path: Path, start: int, end: int, width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    SCENE.frame_start = start
    SCENE.frame_end = end
    SCENE.render.resolution_x = width
    SCENE.render.resolution_y = height
    SCENE.render.resolution_percentage = 100
    SCENE.render.fps = 30
    SCENE.render.engine = "BLENDER_WORKBENCH"
    SCENE.display.shading.light = "STUDIO"
    SCENE.display.shading.studio_light = "rim.sl"
    SCENE.display.shading.color_type = "MATERIAL"
    SCENE.display.shading.show_shadows = True
    SCENE.display.shading.show_cavity = True
    SCENE.render.image_settings.file_format = "FFMPEG"
    SCENE.render.ffmpeg.format = "MPEG4"
    SCENE.render.ffmpeg.codec = "H264"
    SCENE.render.ffmpeg.constant_rate_factor = "MEDIUM"
    SCENE.render.filepath = str(path)
    bpy.ops.render.render(animation=True)


def main() -> None:
    render = "--render" in sys.argv
    (OUTPUT / "review").mkdir(parents=True, exist_ok=True)
    (OUTPUT / "renders/preview").mkdir(parents=True, exist_ok=True)
    bindings = {}
    for fighter, package_path in zip(("fighter_a", "fighter_b"), PACKAGES):
        binding = import_character_model(package_path)
        binding = retarget_package_to_source(
            binding,
            bpy.data.objects[f"{fighter}_Rig"],
            source_body=bpy.data.objects[f"{fighter}_ProductionBody"],
        )
        previous_target = bpy.data.objects[f"{fighter}_ProductionRig"]
        previous_target.hide_viewport = True
        previous_target.hide_render = True
        character_id = binding["manifest"]["character_id"]
        bindings[character_id] = binding

    SCENE["wws_character_package_schema"] = 1
    SCENE["wws_character_packages"] = json.dumps(
        {key: str(path) for key, path in zip(bindings, PACKAGES)}, sort_keys=True
    )
    SCENE["wws_asset_integration_mode"] = "derived_v4_fixture_no_geometry_generation"
    SCENE.frame_start = 1
    SCENE.frame_end = 360
    SCENE.render.resolution_x = 360
    SCENE.render.resolution_y = 640
    SCENE.frame_set(1)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "scene.blend"))

    report = {
        "schema_version": 1,
        "integration_mode": "derived_working_copy",
        "production_asset_available": False,
        "generated_new_body": False,
        "source_scene": str(ROOT / "outputs/blender_combat_v4_humanoid/scene.blend"),
        "source_scene_sha256": sha256(ROOT / "outputs/blender_combat_v4_humanoid/scene.blend"),
        "source_checksum": SCENE["wws_source_checksum"],
        "source_outcome_digest": SCENE["wws_source_outcome_digest"],
        "characters": {
            character_id: {
                "manifest": str(package),
                "package_version": binding["manifest"]["package_version"],
                "rig_adapter": binding["adapter"]["adapter_id"],
                "working_rig": binding["rig"].name,
                "working_meshes": [mesh.name for mesh in binding["meshes"]],
                "source_model": binding["source_model"],
                "source_topology_copied": True,
                "source_weights_copied": True,
            }
            for (character_id, binding), package in zip(bindings.items(), PACKAGES)
        },
    }
    (OUTPUT / "review/package-bindings.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    if render:
        cinematic_camera = SCENE.camera
        render_video(OUTPUT / "renders/preview/fight.mp4", 1, 360, 360, 640)
        markers = save_markers()
        SCENE.camera = bpy.data.objects["V4_StaticMotionReview"]
        vfx_states = suspend_vfx()
        render_video(OUTPUT / "review/static-motion.mp4", 128, 320, 640, 480)
        restore_vfx(vfx_states)
        restore_markers(markers)
        SCENE.camera = cinematic_camera
        SCENE.frame_start = 1
        SCENE.frame_end = 360
        SCENE.render.resolution_x = 360
        SCENE.render.resolution_y = 640
        SCENE.render.filepath = str(OUTPUT / "renders/preview/fight.mp4")
        SCENE.frame_set(1)
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "scene.blend"))

    print(json.dumps({"output": str(OUTPUT), "rendered": render, **report}, indent=2))


if __name__ == "__main__":
    main()
