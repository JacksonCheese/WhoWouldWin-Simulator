"""Build and render the reusable WWS athletic male humanoid review asset."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/first_production_fight_v2/review"
ASSET = ROOT / "assets/characters/base_male_athletic/model/base_male_athletic.blend"
FPS = 30
END = 180


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rt = load_module("wws_base_review_runtime", ROOT / "src/whowouldwin/cinematic/blender_backend/runtime.py")
base_humanoid = load_module("wws_base_review_humanoid", ROOT / "src/whowouldwin/cinematic/blender_backend/base_humanoid.py")
rt.bpy = bpy
rt.Vector = Vector


def material(name, color, roughness=0.55):
    value = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    value.diffuse_color = (*color, 1)
    value.use_nodes = True
    bsdf = value.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    return value


def aim(camera, target):
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def prepare_scene():
    keep = {"fighter_a_Rig", "fighter_a_ProductionRig", "fighter_a_ProductionBody"}
    for obj in list(bpy.data.objects):
        if obj.name not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    source = bpy.data.objects["fighter_a_Rig"]
    rig = bpy.data.objects["fighter_a_ProductionRig"]
    body = bpy.data.objects["fighter_a_ProductionBody"]
    source.name = "WWS_BaseMale_SourceRig"
    rig.name = "WWS_BaseMale_ProductionRig"
    body.name = "WWS_BaseMale_Body"
    source.hide_render = source.hide_viewport = True
    rig.hide_render = True
    rig.show_in_front = True
    body.hide_render = body.hide_viewport = False
    source.animation_data_create()
    for track in list(source.animation_data.nla_tracks):
        source.animation_data.nla_tracks.remove(track)
    source.animation_data.action = bpy.data.actions.new("WWS_BaseMale_DeformationReview")
    source.location = (0, 0, 0)
    source.rotation_euler = (0, 0, 0)
    rt.reset_pose(source)

    skin = material("WWS_BaseMale_Skin", (0.48, 0.24, 0.14), 0.62)
    body.data.materials.clear()
    body.data.materials.append(skin)
    base_humanoid.refine_athletic_body(body)

    hands_collection = bpy.data.collections.new("WWS_BaseMale_Hands")
    bpy.context.scene.collection.children.link(hands_collection)
    controls = {
        side: base_humanoid.create_hand_controls(
            bpy, rig, f"Hand_{side}", f"BaseMale_{side}", skin, hands_collection
        )
        for side in ("L", "R")
    }
    return source, rig, body, controls


def animate(source, controls):
    stance = dict(rt.POSES["combat_stance"])
    anticipation = dict(rt.POSES["punch_anticipation"])
    contact = dict(rt.POSES["punch_contact"])
    contact.update({"pelvis": (0, 0.34, -0.44), "spine": (0, 0.48, -0.58), "chest": (0, 0.30, -0.62)})
    follow = dict(rt.POSES["punch_followthrough"])
    landing = dict(rt.POSES["landing"])
    landing.update({"pelvis": (0, -0.36, 0.10), "spine": (0, 0.52, -0.10), "chest": (0, 0.26, 0.18)})
    recovery = dict(rt.POSES["recovery"])
    for frame, pose in (
        (1, stance), (30, stance), (48, anticipation), (62, contact),
        (70, contact), (86, follow), (105, rt.POSES["airborne_knockback"]),
        (126, landing), (140, rt.POSES["ground_impact"]),
        (158, recovery), (180, stance),
    ):
        rt.key_pose(source, frame, pose)
    action = source.animation_data.action
    for curve in action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = "BEZIER"
            key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"

    for frame, pose in ((1, "OPEN_PALM"), (32, "OPEN_PALM"), (45, "CLOSED_FIST"), (88, "CLOSED_FIST"), (105, "CUPPED"), (145, "OPEN_PALM"), (180, "RELAXED")):
        base_humanoid.set_hand_pose(controls["L"], pose, frame)
        base_humanoid.set_hand_pose(controls["R"], pose, frame)


def presentation():
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end, scene.render.fps = 1, END, FPS
    world = scene.world or bpy.data.worlds.new("WWS_BaseReviewWorld")
    scene.world = world
    world.color = (0.025, 0.03, 0.045)
    ground_mat = material("WWS_BaseReviewGround", (0.06, 0.075, 0.10), 0.82)
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, -0.09), scale=(4, 4, 0.08))
    ground = bpy.context.object
    ground.name = "WWS_BaseReview_Ground"
    ground.data.materials.append(ground_mat)
    bpy.ops.object.camera_add(location=(4.4, -5.1, 2.65))
    camera = bpy.context.object
    camera.name = "WWS_BaseReview_Camera"
    camera.data.lens = 58
    aim(camera, Vector((0.08, 0, 1.45)))
    scene.camera = camera
    bpy.ops.object.light_add(type="AREA", location=(2.5, -3.0, 5.0))
    bpy.context.object.data.energy = 1050
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = 4.0
    bpy.ops.object.light_add(type="AREA", location=(-3.0, 1.5, 3.0))
    bpy.context.object.data.energy = 650
    bpy.context.object.data.color = (0.30, 0.48, 1.0)
    bpy.context.object.data.size = 3.0
    return camera


def render_outputs(camera, rig):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "rim.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.render.resolution_x = 360
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.filepath = str(OUTPUT / "base_humanoid_deformation.mp4")
    bpy.ops.render.render(animation=True)

    hand_dir = OUTPUT / "hand_pose_frames"
    hand_dir.mkdir(parents=True, exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x = scene.render.resolution_y = 420
    for frame, label in ((20, "open"), (65, "fist"), (112, "cupped")):
        scene.frame_set(frame)
        hand = rig.matrix_world @ rig.pose.bones["Hand_R"].tail
        camera.location = hand + Vector((1.45, -1.6, 0.55))
        camera.data.lens = 72
        aim(camera, hand)
        scene.render.filepath = str(hand_dir / f"{label}.png")
        bpy.ops.render.render(write_still=True)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ASSET.parent.mkdir(parents=True, exist_ok=True)
    source, rig, body, controls = prepare_scene()
    animate(source, controls)
    camera = presentation()
    scene = bpy.context.scene
    scene["wws_base_humanoid_version"] = "base_male_athletic.1"
    scene["wws_hand_pose_presets"] = json.dumps(sorted(base_humanoid.HAND_POSES))
    scene.frame_set(1)
    target = OUTPUT / "base_humanoid.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    shutil.copy2(target, ASSET)
    if "--render" in sys.argv:
        render_outputs(camera, rig)
        scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        shutil.copy2(target, ASSET)
    print(json.dumps({"scene": str(target), "asset": str(ASSET), "frames": END}, indent=2))


if __name__ == "__main__":
    main()
