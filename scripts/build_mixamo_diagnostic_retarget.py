"""Retarget one Mixamo clip in a disposable review scene.

This is a diagnostic import test. It never edits or saves the production scene.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "outputs/combat_motion_lab_source_readiness"
REVIEW = PROJECT / "review/combat-mixamo-diagnostic"
FBX = PROJECT / "source/incoming/combat_mixamo/Combat/BigFrontKick_mixamo.fbx"
ADAPTER = REVIEW / "mixamo-rig-adapter.json"
IMPORTER = ROOT / "src/whowouldwin/cinematic/assets/blender_import.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_importer():
    spec = importlib.util.spec_from_file_location("wws_mixamo_diagnostic_import", IMPORTER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def look_at(obj, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def copy_rigs():
    source = bpy.data.objects["fighter_a_Rig"]
    production = bpy.data.objects["fighter_a_ProductionRig"]
    body = bpy.data.objects["OmniMan_Body"]
    debug_source = source.copy()
    debug_source.data = source.data.copy()
    debug_source.name = "DIAGNOSTIC_Mixamo_SourceRig"
    bpy.context.scene.collection.objects.link(debug_source)
    debug_source.animation_data_clear()
    debug_source.location = (0, 0, 0)
    debug_source.rotation_euler = (0, 0, 0)
    for bone in debug_source.pose.bones:
        for constraint in list(bone.constraints):
            bone.constraints.remove(constraint)

    debug_production = production.copy()
    debug_production.data = production.data.copy()
    debug_production.name = "DIAGNOSTIC_Mixamo_ProductionRig"
    bpy.context.scene.collection.objects.link(debug_production)
    debug_production.animation_data_clear()
    debug_production.location = (0, 0, 0)
    debug_production.rotation_euler = (0, 0, 0)
    for bone in debug_production.pose.bones:
        for constraint in bone.constraints:
            if getattr(constraint, "target", None) == source:
                constraint.target = debug_source
            if constraint.name.startswith("WWS cleanup"):
                constraint.influence = 0.0

    debug_body = body.copy()
    debug_body.data = body.data.copy()
    debug_body.name = "DIAGNOSTIC_Mixamo_Body"
    bpy.context.scene.collection.objects.link(debug_body)
    debug_body.parent = debug_production
    for modifier in debug_body.modifiers:
        if modifier.type == "ARMATURE":
            modifier.object = debug_production
    return debug_source, debug_production, debug_body


def foot_drift(rig, bone_name: str, start: int, end: int) -> dict:
    points = {}
    for frame in range(start, end + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        point = rig.matrix_world @ rig.pose.bones[bone_name].head
        points[frame] = point.copy()
    min_z = min(point.z for point in points.values())
    candidate = [frame for frame, point in points.items() if point.z <= min_z + 0.025]
    runs = []
    for frame in candidate:
        if not runs or frame != runs[-1][-1] + 1:
            runs.append([frame])
        else:
            runs[-1].append(frame)
    windows = []
    for frames in runs:
        if len(frames) < 3:
            continue
        anchor = points[frames[0]]
        drift = max(Vector((points[frame].x - anchor.x, points[frame].y - anchor.y)).length for frame in frames)
        windows.append({"frames": [frames[0], frames[-1]], "horizontal_drift": round(drift, 6)})
    return {"bone": bone_name, "minimum_z": round(min_z, 6), "candidate_contact_windows": windows}


def main() -> None:
    REVIEW.mkdir(parents=True, exist_ok=True)
    for obj in bpy.context.scene.objects:
        obj.hide_render = True
    importer = load_importer()
    debug_source, debug_production, debug_body = copy_rigs()
    definition = {
        "clip_id": "diagnostic_big_front_kick",
        "action": "front_kick",
        "path": str(FBX),
        "source_armature": "mixamorig:Reference",
        "action_name": "mixamorig:Reference|clip|Base_Layer",
        "rig_adapter": str(ADAPTER),
        "root_motion": "extract",
    }
    imported = importer.import_animation_clip(definition, PROJECT)
    action = importer._retarget_imported_action(imported, definition, PROJECT, debug_source)
    importer.strip_root_motion(action)
    action.name = "DIAGNOSTIC_RETARGET_BigFrontKick"
    action["wws_quality_status"] = "diagnostic_non_production"
    action["wws_source_sha256"] = digest(FBX)
    debug_source.animation_data_create()
    debug_source.animation_data.action = action
    start, end = (int(round(value)) for value in action.frame_range)

    # The FBX importer also creates its source mesh and helper objects. Keep
    # those out of this retarget review so only the WWS debug body is assessed.
    for obj in bpy.context.scene.objects:
        obj.hide_render = True
    debug_body.hide_render = False
    debug_production.hide_render = True
    debug_source.hide_render = True
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "DIAGNOSTIC_Ground"
    mat = bpy.data.materials.new("DIAGNOSTIC_GroundMaterial")
    mat.diffuse_color = (0.08, 0.09, 0.11, 1)
    ground.data.materials.append(mat)

    bpy.ops.object.camera_add(location=(4.2, -7.2, 2.45))
    camera = bpy.context.object
    camera.name = "DIAGNOSTIC_StaticCamera"
    camera.data.lens = 58
    look_at(camera, Vector((0, 0, 1.05)))
    bpy.context.scene.camera = camera
    bpy.ops.object.light_add(type="AREA", location=(2.5, -3.0, 5.0))
    bpy.context.object.data.energy = 950
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = 5
    look_at(bpy.context.object, Vector((0, 0, 1)))
    bpy.ops.object.light_add(type="AREA", location=(-3.0, 1.0, 3.0))
    bpy.context.object.data.energy = 500
    bpy.context.object.data.size = 4
    look_at(bpy.context.object, Vector((0, 0, 1)))

    scene = bpy.context.scene
    scene.frame_start = start
    scene.frame_end = end
    scene.render.fps = 24
    scene.render.resolution_x = 360
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.filepath = str(REVIEW / "big-front-kick-retarget.mp4")
    scene["wws_diagnostic_only"] = True
    scene["wws_production_approved"] = False
    scene["wws_source_fbx"] = str(FBX)
    scene["wws_source_sha256"] = digest(FBX)
    # Follow only the retargeted pelvis so the complete diagnostic remains in
    # view even when the source contains large authored travel.
    for frame in range(start, end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        focus = debug_production.matrix_world @ debug_production.pose.bones["Hips"].head
        camera.location = focus + Vector((4.2, -7.2, 1.4))
        look_at(camera, focus + Vector((0, 0, 0.25)))
        camera.keyframe_insert("location", frame=frame)
        camera.keyframe_insert("rotation_euler", frame=frame)
    blend = REVIEW / "big-front-kick-retarget.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))

    report = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "diagnostic_non_production_retarget",
        "representative_source": str(FBX),
        "source_sha256": digest(FBX),
        "adapter": str(ADAPTER),
        "target_source_rig": debug_source.name,
        "target_production_rig": debug_production.name,
        "retargeted_action": action.name,
        "frame_range": [start, end],
        "root_translation_separated": not any(
            curve.data_path.endswith("location") and any(
                f'pose.bones["{name}"]' in curve.data_path for name in ("root", "Root", "Hips", "pelvis")
            ) for curve in action.fcurves
        ),
        "cleanup_controls_used": False,
        "production_assets_modified": False,
        "foot_drift": [
            foot_drift(debug_production, "Foot_L", start, end),
            foot_drift(debug_production, "Foot_R", start, end),
        ],
        "production_approved": False,
    }
    (REVIEW / "representative-retarget-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if "--render" in sys.argv:
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
