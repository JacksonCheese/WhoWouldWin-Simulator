"""Build the Combat Motion Lab from the preserved final production fight.

This is a presentation-only derivative. It retains the source armatures, NLA
architecture, root objects, IK controls, source events and deterministic outcome.
Production renderables are hidden, not deleted. A joint-readable debug body is
attached to each production armature and the same choreography is reviewed with
static cameras and a minimal environment.
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
SOURCE = ROOT / "outputs/first_production_fight_astra_final"
OUTPUT = ROOT / "outputs/combat_motion_lab"
END = 540
FPS = 30


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_v2():
    path = ROOT / "scripts/blender_first_production_fight_v2.py"
    spec = importlib.util.spec_from_file_location("wws_motion_lab_v2", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.OUTPUT = OUTPUT
    return module


def material(name: str, color: tuple[float, float, float, float]):
    result = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    result.diffuse_color = color
    result.roughness = 0.72
    return result


def move_to_collection(obj, collection):
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    collection.objects.link(obj)


def sphere(name, radius, mat, collection):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=radius)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    move_to_collection(obj, collection)
    return obj


def cylinder(name, radius, depth, mat, collection, vertices=10):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    move_to_collection(obj, collection)
    return obj


def cube(name, location, scale, mat, collection):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    move_to_collection(obj, collection)
    return obj


def carrier(rig, bone_name, name, collection):
    obj = bpy.data.objects.new(name, None)
    collection.objects.link(obj)
    constraint = obj.constraints.new("COPY_TRANSFORMS")
    constraint.target = rig
    constraint.subtarget = bone_name
    return obj


def child_to(obj, parent, location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
    obj.parent = parent
    obj.location = location
    obj.rotation_euler = rotation
    obj.scale = scale
    return obj


PRODUCTION_BONES = {
    "root": "MotionRoot", "pelvis": "Hips", "spine": "SpineLower",
    "chest": "SpineUpper", "neck": "Neck", "head": "Head",
    "clavicle.L": "Shoulder_L", "upper_arm.L": "UpperArm_L",
    "forearm.L": "LowerArm_L", "hand.L": "Hand_L",
    "clavicle.R": "Shoulder_R", "upper_arm.R": "UpperArm_R",
    "forearm.R": "LowerArm_R", "hand.R": "Hand_R",
    "thigh.L": "UpperLeg_L", "shin.L": "LowerLeg_L", "foot.L": "Foot_L",
    "thigh.R": "UpperLeg_R", "shin.R": "LowerLeg_R", "foot.R": "Foot_R",
}


def add_debug_body(prefix, rig, palette, collection):
    """Attach simple volumes to the existing production rig contract."""
    dark, primary, light, joint = palette
    assert set(PRODUCTION_BONES.values()).issubset({b.name for b in rig.data.bones})
    carriers = {}
    for role, bone_name in PRODUCTION_BONES.items():
        carriers[role] = carrier(rig, bone_name, f"ML_{prefix}_{role}_carrier", collection)
    # Bone-local +Y is the segment axis; Blender cylinders are created along +Z.
    segments = {
        "upper_arm.L": (0.105, primary), "upper_arm.R": (0.105, primary),
        "forearm.L": (0.085, light), "forearm.R": (0.085, light),
        "thigh.L": (0.145, primary), "thigh.R": (0.145, primary),
        "shin.L": (0.105, dark), "shin.R": (0.105, dark),
        "neck": (0.105, light),
    }
    for role, (radius, mat) in segments.items():
        length = rig.data.bones[PRODUCTION_BONES[role]].length
        obj = cylinder(f"ML_{prefix}_{role}", radius, length, mat, collection)
        child_to(obj, carriers[role], (0, length * 0.5, 0), (math.pi / 2, 0, 0))
        joint_obj = sphere(f"ML_{prefix}_{role}_joint", radius * 1.12, joint, collection)
        child_to(joint_obj, carriers[role])
    for role, dimensions, mat in (
        ("pelvis", (0.27, 0.20, 0.22), dark),
        ("spine", (0.27, 0.19, 0.30), primary),
        ("chest", (0.36, 0.22, 0.39), primary),
    ):
        length = rig.data.bones[PRODUCTION_BONES[role]].length
        obj = sphere(f"ML_{prefix}_{role}", 1.0, mat, collection)
        child_to(obj, carriers[role], (0, length * 0.55, 0), scale=dimensions)
    head_length = rig.data.bones["Head"].length
    head = sphere(f"ML_{prefix}_head", 1.0, light, collection)
    child_to(head, carriers["head"], (0, head_length * 0.58, 0), scale=(0.24, 0.20, 0.28))
    for role in ("hand.L", "hand.R"):
        length = rig.data.bones[PRODUCTION_BONES[role]].length
        hand = sphere(f"ML_{prefix}_{role}", 1.0, light, collection)
        child_to(hand, carriers[role], (0, length * 0.65, 0), scale=(0.10, 0.16, 0.075))
    for role in ("foot.L", "foot.R"):
        length = rig.data.bones[PRODUCTION_BONES[role]].length
        foot = cube(f"ML_{prefix}_{role}", (0, 0, 0), (1, 1, 1), dark, collection)
        child_to(foot, carriers[role], (0, length * 0.75, 0.035), scale=(0.115, 0.22, 0.08))
    return carriers


def preserve_and_hide_renderables():
    states = {}
    source_renderables = bpy.data.collections.new("WWS_MOTION_SOURCE_RENDERABLES")
    bpy.context.scene.collection.children.link(source_renderables)
    for obj in bpy.data.objects:
        if obj.type in {"MESH", "CURVE", "FONT", "VOLUME"}:
            states[obj.name] = bool(obj.hide_render)
            obj.hide_render = True
            # Source effects keyframe object visibility. Isolate every original
            # renderable in one collection so a collection-level hide remains
            # authoritative during frame evaluation.
            move_to_collection(obj, source_renderables)
    source_renderables.hide_render = True
    bpy.context.scene["wws_original_render_visibility"] = json.dumps(states, sort_keys=True)
    return states


def clone_actions_for_lab():
    """Make the motion experiment reversible inside its derived blend."""
    mapping = {}
    for rig_name in ("fighter_a_Rig", "fighter_b_Rig"):
        rig = bpy.data.objects[rig_name]
        for track in rig.animation_data.nla_tracks:
            for strip in track.strips:
                original = strip.action
                if original.name not in mapping:
                    copy = original.copy()
                    copy.name = "ML_" + original.name
                    copy["wws_motion_lab_source_action"] = original.name
                    mapping[original.name] = copy
                strip.action = mapping[original.name]
    return mapping


def author(action, rig, keys):
    old_action = rig.animation_data.action
    track_states = [(track, track.mute) for track in rig.animation_data.nla_tracks]
    for track, _ in track_states:
        track.mute = True
    rig.animation_data.action = action
    for frame, rotations in keys:
        for bone_name, value in rotations.items():
            bone = rig.pose.bones[bone_name]
            bone.rotation_mode = "XYZ"
            bone.rotation_euler = value
            bone.keyframe_insert("rotation_euler", frame=frame)
    for curve in action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = "BEZIER"
            key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"
    rig.animation_data.action = old_action
    for track, muted in track_states:
        track.mute = muted


def refine_body_actions(actions):
    omni = bpy.data.objects["fighter_a_Rig"]
    naruto = bpy.data.objects["fighter_b_Rig"]
    # Local-action timing exposes load, sequential rotation, contact and recovery.
    author(actions["WWS_CHAR_omniman_flight_blitz"], omni, [
        (3, {"pelvis": (0,-.20,.08),"spine": (0,-.18,.12),"thigh.L": (.82,0,0),"shin.L": (-.72,0,0),"thigh.R": (-.55,0,0)}),
        (5, {"pelvis": (0,-.40,.20),"spine": (0,-.35,.28),"chest": (0,-.18,.18),"upper_arm.L": (.25,0,-.48),"upper_arm.R": (.38,0,.62)}),
        (8, {"pelvis": (0,-.05,0),"spine": (0,.34,0),"chest": (0,.12,.08),"upper_arm.L": (.18,0,-.34),"upper_arm.R": (.12,0,.38),"thigh.L": (-.30,0,0),"thigh.R": (.28,0,0)}),
        (16, {"chest": (0,.08,.34),"upper_arm.L": (.25,0,-.30),"upper_arm.R": (.20,0,.35)}),
        (21, {"pelvis": (0,-.20,.42),"spine": (0,-.25,.55),"chest": (0,-.12,.66),"upper_arm.R": (-1.62,0,.95),"forearm.R": (-1.05,0,0)}),
        (23, {"pelvis": (0,.25,-.42),"spine": (0,.32,-.55),"chest": (0,.16,-.66),"clavicle.R": (0,0,-.32),"upper_arm.R": (.16,0,-1.45),"forearm.R": (.03,0,0)}),
        (27, {"pelvis": (0,.16,-.55),"spine": (0,.24,-.64),"chest": (0,.12,-.48),"upper_arm.R": (.42,0,-1.25)}),
    ])
    author(actions["WWS_CHAR_omniman_flight_brake"], omni, [
        (1, {"spine": (0,.28,0),"chest": (0,.08,0),"upper_arm.L": (.15,0,-.30),"upper_arm.R": (.15,0,.30)}),
        (5, {"pelvis": (0,.35,0),"spine": (0,.42,0),"chest": (0,.20,0),"upper_arm.L": (-.30,0,-1.0),"upper_arm.R": (-.30,0,1.0),"thigh.L": (.50,0,0),"thigh.R": (.45,0,0)}),
        (9, {"pelvis": (0,.60,0),"spine": (0,.72,0),"chest": (0,.32,0),"upper_arm.L": (.55,0,-.90),"upper_arm.R": (.55,0,.90)}),
        (13, {"pelvis": (0,.50,.16),"spine": (0,.62,.18),"chest": (0,.28,.12),"thigh.L": (-.55,0,0),"thigh.R": (.72,0,0),"shin.R": (-.55,0,0)}),
        (20, {"pelvis": (0,.18,0),"spine": (0,.25,0),"chest": (0,-.05,0)}),
    ])
    author(actions["WWS_CHAR_omniman_super_punch"], omni, [
        (4, {"pelvis": (0,-.15,.18),"thigh.R": (-.50,0,0),"shin.R": (.38,0,0)}),
        (7, {"pelvis": (0,-.22,.48),"spine": (0,-.26,.32),"chest": (0,-.12,.18),"upper_arm.R": (-1.60,0,.92),"forearm.R": (-1.05,0,0)}),
        (9, {"pelvis": (0,.05,-.12),"spine": (0,.08,-.32),"chest": (0,-.03,-.48),"upper_arm.R": (-1.10,0,-.10)}),
        (11, {"pelvis": (0,.30,-.52),"spine": (0,.38,-.65),"chest": (0,.18,-.72),"clavicle.R": (0,0,-.34),"upper_arm.R": (.12,0,-1.48),"forearm.R": (.02,0,0)}),
        (14, {"pelvis": (0,.32,-.70),"spine": (0,.45,-.78),"chest": (0,.23,-.66),"upper_arm.R": (.40,0,-1.34)}),
        (18, {"pelvis": (0,.16,-.22),"spine": (0,.22,-.28),"chest": (0,.06,-.18)}),
    ])
    author(actions["WWS_CHAR_omniman_impact_launch"], omni, [
        (1, {"pelvis": (0,-.10,.10),"spine": (0,-.14,.10),"chest": (0,-.08,.12)}),
        (3, {"pelvis": (0,-.18,.18),"spine": (0,-.58,.42),"chest": (0,-.86,.64)}),
        (4, {"pelvis": (0,-.42,.36),"spine": (0,-.88,.74),"chest": (0,-1.02,.88),"head": (0,.38,-.20)}),
        (6, {"pelvis": (0,-.72,.78),"spine": (0,-1.00,.92),"chest": (0,-.74,.90),"upper_arm.L": (.55,0,.62),"upper_arm.R": (-.38,0,-.48)}),
        (9, {"pelvis": (0,-.58,.96),"spine": (0,-.82,1.08),"chest": (0,-.48,.84),"upper_arm.L": (1.15,0,.82),"upper_arm.R": (-1.02,0,-.72),"thigh.L": (.58,0,0),"thigh.R": (-.38,0,0)}),
        (13, {"pelvis": (0,-.42,.78),"spine": (0,-.64,.82),"chest": (0,-.28,.58),"upper_arm.L": (1.38,0,.90),"upper_arm.R": (-1.22,0,-.82),"thigh.L": (.78,0,0),"thigh.R": (-.55,0,0)}),
        (18, {"pelvis": (0,-.22,.42),"spine": (0,-.40,.35),"chest": (0,-.12,.20),"forearm.L": (-.30,0,.20),"forearm.R": (-.65,0,-.20),"thigh.L": (-.20,0,0),"thigh.R": (.62,0,0)}),
        (23, {"pelvis": (0,.10,-.18),"spine": (0,.18,-.32),"chest": (0,.08,-.45),"upper_arm.L": (.42,0,-.62),"upper_arm.R": (-.72,0,.48)}),
        (28, {"pelvis": (0,.18,-.35),"spine": (0,.25,-.48),"chest": (0,.12,-.38)}),
    ])
    author(actions["WWS_CHAR_omniman_midair_recovery"], omni, [
        (1, {"pelvis": (0,-.25,.45),"spine": (0,-.42,.38),"chest": (0,-.18,.28),"upper_arm.L": (1.0,0,.72),"upper_arm.R": (-1.0,0,-.72)}),
        (5, {"pelvis": (0,-.10,.72),"spine": (0,-.18,.65),"chest": (0,.05,.48),"upper_arm.L": (.62,0,.55),"upper_arm.R": (-.82,0,-.62),"thigh.L": (.72,0,0),"thigh.R": (-.50,0,0)}),
        (9, {"pelvis": (0,.08,.45),"spine": (0,.18,.35),"chest": (0,.18,.15),"upper_arm.L": (.18,0,-.30),"upper_arm.R": (-.30,0,.38),"thigh.L": (-.30,0,0),"thigh.R": (.42,0,0)}),
        (14, {"pelvis": (0,-.05,.18),"spine": (0,.20,.10),"chest": (0,.10,-.08),"upper_arm.L": (.12,0,-.32),"upper_arm.R": (.08,0,.35)}),
        (18, {"pelvis": (0,.10,.08),"spine": (0,.16,0),"chest": (0,-.04,0)}),
        (21, {"pelvis": (0,.16,0),"spine": (0,.22,0),"chest": (0,-.06,0)}),
    ])
    author(actions["WWS_CHAR_naruto_body_dodge"], naruto, [
        (4, {"head": (0,.12,.42),"chest": (0,-.10,-.35),"spine": (0,-.12,-.20),"pelvis": (0,-.05,-.08)}),
        (7, {"head": (0,.18,.52),"chest": (0,-.25,-.78),"spine": (0,-.32,-.56),"pelvis": (0,-.25,-.38),"thigh.L": (.78,0,0),"shin.L": (-.68,0,0)}),
        (10, {"head": (0,.10,.35),"chest": (0,-.32,-.88),"spine": (0,-.42,-.72),"pelvis": (0,-.35,-.62),"thigh.R": (-.58,0,0),"shin.R": (.42,0,0)}),
        (14, {"head": (0,.06,.20),"chest": (0,-.22,-.58),"spine": (0,-.30,-.42),"pelvis": (0,-.28,-.46)}),
        (18, {"head": (0,0,.08),"chest": (0,-.12,-.22),"spine": (0,-.12,-.15),"pelvis": (0,-.12,-.16)}),
    ])
    author(actions["WWS_CHAR_naruto_ninja_dash"], naruto, [
        (2, {"pelvis": (0,-.18,-.05),"spine": (0,.28,.02),"thigh.L": (.88,0,0),"shin.L": (-.78,0,0),"thigh.R": (-.56,0,0)}),
        (4, {"pelvis": (0,-.48,-.08),"spine": (0,.58,.06),"chest": (0,.22,-.10),"head": (0,-.18,0),"thigh.L": (.76,0,0),"shin.L": (-.72,0,0),"thigh.R": (-.65,0,0)}),
        (8, {"pelvis": (0,-.36,.08),"spine": (0,.64,-.08),"chest": (0,.24,-.14),"thigh.L": (-.48,0,0),"thigh.R": (.68,0,0),"shin.R": (-.58,0,0)}),
        (13, {"pelvis": (0,-.40,-.10),"spine": (0,.62,.08),"chest": (0,.20,-.12),"thigh.L": (.70,0,0),"shin.L": (-.60,0,0),"thigh.R": (-.46,0,0)}),
        (18, {"pelvis": (0,.12,-.32),"spine": (0,.28,-.45),"chest": (0,.15,-.50),"thigh.L": (-.32,0,0),"thigh.R": (.52,0,0)}),
        (23, {"pelvis": (0,.25,-.12),"spine": (0,.20,-.18),"chest": (0,-.08,-.10)}),
    ])
    author(actions["WWS_CHAR_naruto_melee_redirect"], naruto, [
        (2, {"head": (0,.08,.25),"chest": (0,-.08,-.22),"pelvis": (0,-.04,-.05)}),
        (4, {"head": (0,.12,.42),"chest": (0,-.20,-.60),"spine": (0,-.22,-.38),"pelvis": (0,-.20,-.30)}),
        (6, {"pelvis": (0,-.12,.26),"spine": (0,-.16,.32),"chest": (0,-.08,.18),"upper_arm.R": (-1.45,0,.80),"thigh.R": (-.48,0,0)}),
        (8, {"pelvis": (0,.20,-.38),"spine": (0,.30,-.52),"chest": (0,.14,-.56),"upper_arm.R": (.12,0,-1.36),"forearm.R": (.05,0,0),"thigh.L": (-.30,0,0),"thigh.R": (.42,0,0)}),
        (10, {"pelvis": (0,.12,-.18),"spine": (0,.16,-.22),"chest": (0,-.06,-.12),"upper_arm.L": (-.82,0,-.88),"forearm.L": (-1.15,0,.08)}),
        (12, {"pelvis": (0,-.12,.18),"spine": (0,-.08,.22),"chest": (0,-.10,.28),"upper_arm.L": (-1.08,0,-.82),"forearm.L": (-1.18,0,.08)}),
        (14, {"pelvis": (0,-.28,-.18),"spine": (0,.28,-.22),"chest": (0,.06,-.28),"thigh.L": (.72,0,0),"shin.L": (-.58,0,0),"thigh.R": (-.42,0,0)}),
        (16, {"pelvis": (0,.18,-.20),"spine": (0,.28,.14),"chest": (0,-.16,.28),"upper_arm.R": (-1.28,0,.30),"forearm.R": (-1.38,0,-.16)}),
    ])
    author(actions["WWS_CHAR_naruto_rasengan_attack"], naruto, [
        (2, {"pelvis": (0,-.18,-.16),"spine": (0,.20,.12),"chest": (0,-.10,.22),"thigh.L": (.82,0,0),"shin.L": (-.72,0,0),"thigh.R": (-.55,0,0)}),
        (5, {"pelvis": (0,-.42,-.10),"spine": (0,.56,.05),"chest": (0,.18,-.12),"thigh.L": (.65,0,0),"shin.L": (-.58,0,0),"thigh.R": (-.58,0,0)}),
        (8, {"pelvis": (0,.08,-.30),"spine": (0,.26,-.45),"chest": (0,.10,-.52),"clavicle.R": (0,0,-.20),"upper_arm.R": (-.35,0,-.72),"thigh.L": (-.38,0,0),"thigh.R": (.52,0,0)}),
        (10, {"pelvis": (0,.34,-.50),"spine": (0,.46,-.64),"chest": (0,.24,-.68),"clavicle.R": (0,0,-.35),"upper_arm.R": (.04,0,-1.42),"forearm.R": (.08,0,0)}),
        (13, {"pelvis": (0,.38,-.62),"spine": (0,.50,-.72),"chest": (0,.26,-.70),"upper_arm.R": (.15,0,-1.46)}),
        (17, {"pelvis": (0,.25,-.42),"spine": (0,.32,-.52),"chest": (0,.12,-.46),"upper_arm.R": (.34,0,-1.34)}),
        (21, {"pelvis": (0,.12,-.20),"spine": (0,.18,-.24),"chest": (0,-.06,-.14)}),
        (26, {"pelvis": (0,.24,.02),"spine": (0,.36,-.05),"chest": (0,-.16,.08)}),
    ])


def remove_interval_keys(action, start, end, paths=("location", "rotation_euler")):
    for curve in action.fcurves:
        if curve.data_path in paths:
            for key in list(curve.keyframe_points):
                if start <= key.co.x <= end:
                    curve.keyframe_points.remove(key)
            curve.update()


def key_root(rig, frame, loc, yaw, *, pitch=0.0, roll=0.0, interpolation="BEZIER"):
    rig.location = loc
    rig.rotation_mode = "XYZ"
    rig.rotation_euler = (roll, pitch, yaw)
    rig.keyframe_insert("location", frame=frame)
    rig.keyframe_insert("rotation_euler", frame=frame)
    for curve in rig.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            if abs(key.co.x-frame)<.01:
                key.interpolation = interpolation
                key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"


def facing(a, b):
    return math.atan2(b[1]-a[1], b[0]-a[0])


def refine_root_paths():
    omni=bpy.data.objects["fighter_a_Rig"]
    naruto=bpy.data.objects["fighter_b_Rig"]
    # Preserve endpoints, but hold the roots during visible grounded loading.
    key_root(omni,42,(7.5,-.5,0),2.9368)
    key_root(omni,48,(7.5,-.5,0),2.9368)
    key_root(omni,52,(7.12,-.40,.16),2.9368,pitch=.28)
    # Naruto push-off: the body loads before the world displacement begins.
    key_root(naruto,132,(-4.3,-1.8,0),1.1)
    key_root(naruto,138,(-4.3,-1.8,0),1.1)
    key_root(naruto,145,(-3.75,-2.35,.12),1.22,pitch=-.04,roll=.05)
    key_root(naruto,152,(-2.3,-3.25,.28),1.42,pitch=-.08,roll=.10)
    key_root(naruto,162,(-.8,-3.5,0),1.72)
    key_root(naruto,228,(-.8,-3.5,0),1.72)
    key_root(naruto,235,(-.8,-3.5,0),1.72)
    key_root(naruto,244,(-1.0,-2.9,0),1.68)
    key_root(naruto,256,(-1.4,-1.75,.05),1.45)
    key_root(naruto,270,(-1.6,-.3,.08),1.20,pitch=-.08)
    # Replace collision-cleanup micro-keys with deliberate lateral beats.
    remove_interval_keys(omni.animation_data.action,271,379)
    remove_interval_keys(naruto.animation_data.action,271,379)
    omni_beats={
        271:(-4.0,1.45,.06),278:(-2.75,1.15,.05),290:(-2.08,1.02,.05),
        303:(-1.82,.98,.05),316:(-1.55,1.02,.05),326:(-1.42,1.12,.05),
        338:(-.98,1.12,.05),350:(-.30,1.02,.05),360:(.28,.95,.05),
        365:(.42,.88,.05),368:(.42,.88,.05),371:(.42,.88,.05),379:(1.82,1.04,1.20),
    }
    naruto_beats={
        271:(-1.68,-.34,.08),278:(-2.05,-.72,.03),286:(-2.18,-.90,.08),
        294:(-2.25,-1.18,.16),303:(-1.62,-.72,.18),316:(-1.42,-.38,.12),
        324:(-1.68,-.68,.04),332:(-.92,-.86,.03),340:(-.60,-.88,.03),
        350:(-.86,-.86,.03),360:(-.92,-.94,.03),365:(-.58,-.46,.03),
        368:(-.58,-.46,.03),371:(-.58,-.46,.03),379:(-.22,-.18,.03),
    }
    all_frames=sorted(set(omni_beats)|set(naruto_beats))
    def interpolate(beats, frame):
        if frame in beats:return beats[frame]
        lo=max(f for f in beats if f<frame);hi=min(f for f in beats if f>frame)
        t=(frame-lo)/(hi-lo)
        return tuple(beats[lo][i]*(1-t)+beats[hi][i]*t for i in range(3))
    for frame in all_frames:
        a=interpolate(omni_beats,frame);b=interpolate(naruto_beats,frame)
        hold=frame in {365,368,371}
        key_root(omni,frame,a,facing(a,b),interpolation="CONSTANT" if hold else "BEZIER")
        key_root(naruto,frame,b,facing(b,a),interpolation="CONSTANT" if hold else "BEZIER")
    return omni,naruto


def look_at(obj, target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()


def add_camera(name, location, target, lens, collection):
    data=bpy.data.cameras.new(name+"_DATA")
    camera=bpy.data.objects.new(name,data)
    collection.objects.link(camera)
    camera.location=location;data.lens=lens
    look_at(camera,target)
    return camera


def add_minimal_environment(collection):
    floor=material("ML_Floor",(.26,.27,.29,1));wall=material("ML_Wall",(.42,.44,.47,1));obstacle=material("ML_Obstacle",(.32,.34,.37,1))
    cube("ML_Ground",(3,0,-.16),(29,6,.16),floor,collection)
    cube("ML_CrashWall",(-10.5,6.0,2.1),(2.7,.12,2.1),wall,collection)
    # Low boundary rails preserve street clearance without obscuring limbs.
    cube("ML_BuildingLeft",(-1,6.8,.35),(20,.18,.35),obstacle,collection)
    cube("ML_BuildingRight",(4,-6.8,.35),(24,.18,.35),obstacle,collection)
    cube("ML_ObstacleA",(-17,-3.9,.55),(1.8,.8,.55),obstacle,collection)
    cube("ML_ObstacleB",(6,4.0,.55),(1.8,.8,.55),obstacle,collection)


def curve_path(name, points, mat, collection, bevel=.022):
    curve=bpy.data.curves.new(name+"_DATA","CURVE")
    curve.dimensions="3D";curve.bevel_depth=bevel;curve.bevel_resolution=1
    spline=curve.splines.new("POLY");spline.points.add(len(points)-1)
    for point,co in zip(spline.points,points):point.co=(*co,1)
    obj=bpy.data.objects.new(name,curve);collection.objects.link(obj);curve.materials.append(mat)
    return obj


def sample_world(rig, bone_name, frame, fraction=.5):
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
    bone=rig.pose.bones[bone_name]
    return rig.matrix_world @ bone.head.lerp(bone.tail,fraction)


def add_trajectory_overlays(overlay):
    naruto=bpy.data.objects["fighter_b_ProductionRig"];omni=bpy.data.objects["fighter_a_ProductionRig"]
    orange=material("ML_PathNaruto",(1,.28,.03,1));red=material("ML_PathOmni",(.9,.03,.04,1));blue=material("ML_PathAttack",(.02,.55,1,1));white=material("ML_PathFeet",(.85,.88,.92,1))
    for label,rig,mat in (("Naruto",naruto,orange),("Omni",omni,red)):
        curve_path("ML_"+label+"_RootPath",[sample_world(rig,"Hips",f,.5) for f in range(1,541,4)],mat,overlay,.025)
        # Approximate center of mass from the midpoint between pelvis and chest.
        com=[]
        for frame in range(1,541,4):
            pelvis=sample_world(rig,"Hips",frame,.5)
            chest=sample_world(rig,"SpineUpper",frame,.5)
            com.append(pelvis.lerp(chest,.42))
        curve_path("ML_"+label+"_CenterOfMassPath",com,mat,overlay,.016)
        # Short velocity vectors make acceleration and braking legible from the
        # top review without introducing a physics dependency.
        for frame in range(12,529,24):
            start=sample_world(rig,"Hips",frame,.5)
            end=sample_world(rig,"Hips",frame+6,.5)
            delta=end-start
            if delta.length>.025:
                end=start+delta.normalized()*min(.9,.18+delta.length*.3)
                curve_path(f"ML_{label}_Velocity_{frame:03d}",[start,end],mat,overlay,.028)
    for label,rig,bone,frames,mat in (
        ("NarutoHand",naruto,"Hand_R",range(278,380),blue),
        ("OmniHand",omni,"Hand_R",range(268,315),red),
        ("NarutoFootL",naruto,"Foot_L",range(120,380,2),white),
        ("NarutoFootR",naruto,"Foot_R",range(120,380,2),white),
        ("OmniFootL",omni,"Foot_L",range(250,380,2),white),
        ("OmniFootR",omni,"Foot_R",range(250,380,2),white),
    ):
        curve_path("ML_"+label+"Path",[sample_world(rig,bone,f,.7) for f in frames],mat,overlay,.032)
    # Contact points and intended attack lines.
    for frame,label,actor,bone,target,target_bone in (
        (294,"BlitzMiss",omni,"Hand_R",naruto,"SpineUpper"),
        (316,"Counter",naruto,"Hand_R",omni,"LowerArm_L"),
        (365,"Rasengan",naruto,"Hand_R",omni,"SpineUpper"),
    ):
        start=sample_world(actor,bone,frame,.75);end=sample_world(target,target_bone,frame,.5)
        curve_path("ML_AttackLine_"+label,[start,end],blue,overlay,.04)
        marker=sphere("ML_Contact_"+label,.12,blue,overlay);marker.location=end


def add_simple_rasengan(carriers, collection):
    blue=material("ML_RasenganBlue",(.03,.35,1,1))
    orb=sphere("ML_RasenganSphere",.18,blue,collection)
    hand=carriers["hand.R"]
    length=bpy.data.objects["fighter_b_ProductionRig"].data.bones["Hand_R"].length
    child_to(orb,hand,(0,length+.16,0))
    orb.hide_render=True;orb.keyframe_insert("hide_render",frame=1)
    orb.keyframe_insert("hide_render",frame=167)
    orb.hide_render=False;orb.keyframe_insert("hide_render",frame=168)
    orb.keyframe_insert("hide_render",frame=381)
    orb.hide_render=True;orb.keyframe_insert("hide_render",frame=382)
    return orb


def write_motion_report(actions, corrections, collision):
    payload={
        "schema_version":1,"presentation_only":True,"visualization_mode":"motion_debug",
        "source_scene":str(SOURCE/"scene.blend"),"source_scene_sha256":digest(SOURCE/"scene.blend"),
        "source_events_sha256":digest(SOURCE/"source/events.json"),
        "source_events_unchanged":digest(SOURCE/"source/events.json")==digest(OUTPUT/"source/events.json"),
        "standard_rig_contract":PRODUCTION_BONES,"animation_architecture":"existing Actions/NLA plus derived ML_ action copies",
        "substantially_changed":["Omni-Man flight launch/body alignment","Naruto evasive body sequencing","Naruto dash leg cycle","close exchange root/yaw staging","counter and Rasengan whole-body sequencing","Omni-Man segmented impact/launch/recovery"],
        "root_translation_reduced":["Omni-Man root held through launch load frames 42-48","Naruto root held through dash load frames 132-138 and Rasengan approach load frames 228-235","close exchange micro-correction keys replaced by deliberate lateral beats"],
        "derived_actions":sorted(action.name for action in actions.values()),
        "clearance_corrections":len(corrections),"collision_frames":collision["frames_evaluated"],"unsupported_proxy_issues":collision["unintentional_issue_count"],
        "normal_speed_motion_gate":"PENDING visual playback review",
    }
    (OUTPUT/"review/motion-lab-build.json").write_text(json.dumps(payload,indent=2))


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    for directory in ("source","review","renders"):(OUTPUT/directory).mkdir(exist_ok=True)
    # Source is already open; copy provenance before any presentation edits.
    (OUTPUT/"source/events.json").write_bytes((SOURCE/"source/events.json").read_bytes())
    states=preserve_and_hide_renderables()
    actions=clone_actions_for_lab();refine_body_actions(actions)
    omni,naruto=refine_root_paths()
    v2=load_v2()
    # Existing presentation solver keeps unsupported overlaps out after restaging.
    corrections=v2.apply_clearance_solver()
    # Record the evaluated hero-contact target rather than whichever transform
    # happens to be active after the 540-frame clearance pass.
    bpy.context.scene.frame_set(365);bpy.context.view_layer.update()
    surface=tuple(bpy.data.objects["fighter_b_IK_hand.R"].matrix_world.translation)
    collision=v2.collision_report(surface,corrections)
    debug=bpy.data.collections.new("WWS_MOTION_DEBUG_BODY");bpy.context.scene.collection.children.link(debug)
    minimal=bpy.data.collections.new("WWS_MOTION_MINIMAL_ENV");bpy.context.scene.collection.children.link(minimal)
    overlay=bpy.data.collections.new("WWS_MOTION_OVERLAYS");bpy.context.scene.collection.children.link(overlay)
    orange=material("ML_NarutoOrange",(.92,.19,.025,1));black=material("ML_NarutoBlack",(.025,.03,.04,1));skin=material("ML_Joint",(.60,.62,.65,1));pale=material("ML_LimbLight",(.80,.82,.84,1))
    red=material("ML_OmniRed",(.68,.02,.03,1));white=material("ML_OmniWhite",(.82,.84,.86,1));dark=material("ML_OmniDark",(.06,.06,.07,1))
    naruto_carriers=add_debug_body("Naruto",bpy.data.objects["fighter_b_ProductionRig"],(black,orange,pale,skin),debug)
    add_debug_body("Omni",bpy.data.objects["fighter_a_ProductionRig"],(dark,red,white,skin),debug)
    add_simple_rasengan(naruto_carriers,debug)
    add_minimal_environment(minimal)
    add_trajectory_overlays(overlay)
    cameras=bpy.data.collections.new("WWS_MOTION_CAMERAS");bpy.context.scene.collection.children.link(cameras)
    camera_specs={
        # Static cameras prioritize the central exchange. Extreme entrance/exit
        # positions can leave the edge of frame; the top view retains geography.
        "side":((-1,-14,3.8),(-1,0,1.45),35),
        "three-quarter":((6.2,-10.2,4.6),(-.2,0,1.55),60),
        "front-diagonal":((-7.6,-9.2,4.1),(-.4,0,1.50),58),
        "top-debug":((1,0,24),(1,0,0),35),
    }
    for name,(loc,target,lens) in camera_specs.items():
        camera=add_camera("ML_CAM_"+name,loc,target,lens,cameras)
        if name=="top-debug":
            camera.data.type="ORTHO";camera.data.ortho_scale=18
    overlay.hide_render=True;overlay.hide_viewport=True
    scene=bpy.context.scene
    scene["wws_visualization_mode"]="motion_debug"
    scene["wws_visualization_modes"]=json.dumps(["motion_debug","character_preview","production"])
    scene["wws_motion_lab_source_sha256"]=digest(SOURCE/"scene.blend")
    scene["wws_motion_lab_events_sha256"]=digest(OUTPUT/"source/events.json")
    scene["wws_motion_lab_builder_sha256"]=digest(Path(__file__))
    scene["wws_motion_lab_build_utc"]=datetime.now(timezone.utc).isoformat()
    scene["wws_motion_lab_original_states"]=json.dumps(states,sort_keys=True)
    scene.render.resolution_x=360;scene.render.resolution_y=640;scene.render.resolution_percentage=100;scene.render.fps=30
    scene.display.shading.light="STUDIO";scene.display.shading.studio_light="rim.sl";scene.display.shading.color_type="MATERIAL"
    scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True
    scene.frame_start=1;scene.frame_end=END;scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT/"scene.blend"))
    write_motion_report(actions,corrections,collision)
    print("COMBAT_MOTION_LAB_BUILT",json.dumps({"scene":str(OUTPUT/"scene.blend"),"unsupported_proxy_issues":collision["unintentional_issue_count"],"clearance_corrections":len(corrections)}))


if __name__=="__main__":main()
