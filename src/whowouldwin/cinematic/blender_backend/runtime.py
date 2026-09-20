"""Standalone Blender 4.2+ scene builder.

This file is copied into each Blender project so Blender does not need the
WhoWouldWin package installed in its bundled Python. Run through the CLI, or:

blender --background --python scene.py -- plan.json scene.blend preview out.mp4 render
"""

import json
import math
from pathlib import Path
import random
import re
import sys

PROJECT_SCRIPT_DIRECTORY = str(Path(__file__).resolve().parent)
if PROJECT_SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, PROJECT_SCRIPT_DIRECTORY)

bpy = None
Vector = None


def vec(raw):
    return Vector((raw["x"], raw["y"], raw["z"]))


def material(name, color, metallic=0.0, roughness=0.45, emission=None):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        emission_color = bsdf.inputs.get("Emission Color") or bsdf.inputs.get(
            "Emission"
        )
        emission_strength = bsdf.inputs.get("Emission Strength")
        if emission_color and hasattr(emission_color, "default_value"):
            emission_color.default_value = (*emission, 1)
        if emission_strength and hasattr(emission_strength, "default_value"):
            emission_strength.default_value = 12
    return mat


def cube(name, location, scale, mat, bevel=0.04):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        modifier = obj.modifiers.new("Hard surface bevel", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    obj.data.materials.append(mat)
    return obj


def sphere(name, location, scale, mat):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def cylinder(name, head, tail, radius, mat):
    head, tail = Vector(head), Vector(tail)
    direction = tail - head
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12, radius=radius, depth=direction.length, location=(head + tail) / 2
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(direction)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def assign_weights(obj, influences):
    """Assign explicit, normalized deformation weights to a mesh part."""
    indices = list(range(len(obj.data.vertices)))
    for bone, weight in influences.items():
        obj.vertex_groups.new(name=bone).add(indices, weight, "REPLACE")


def join_skinned_body(name, rig, parts):
    """Join authored parts into one smooth armature-deformed character mesh."""
    bpy.ops.object.select_all(action="DESELECT")
    for obj, influences in parts:
        assign_weights(obj, influences)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0][0]
    bpy.ops.object.join()
    body = bpy.context.object
    body.name = name + "_SkinnedBody"
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    body.parent = rig
    body.matrix_parent_inverse = rig.matrix_world.inverted()
    modifier = body.modifiers.new("Armature deformation", "ARMATURE")
    modifier.object = rig
    modifier.use_deform_preserve_volume = True
    return body


def control_empty(name, location):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.empty_display_type = "SPHERE"
    obj.empty_display_size = 0.12
    obj.location = location
    obj.hide_render = True
    return obj


def create_rig(name, color, initial):
    """Create a reusable humanoid armature, smooth body and IK controls."""
    armature = bpy.data.armatures.new(name + "_ArmatureData")
    rig = bpy.data.objects.new(name + "_Rig", armature)
    bpy.context.collection.objects.link(rig)
    rig.show_in_front = True
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bones = {
        "root": ((0, 0, 0), (0, 0, 0.45), None),
        "pelvis": ((0, 0, 0.45), (0, 0, 1.1), "root"),
        "spine": ((0, 0, 1.1), (0, 0, 1.65), "pelvis"),
        "chest": ((0, 0, 1.65), (0, 0, 2.15), "spine"),
        "neck": ((0, 0, 2.15), (0, 0, 2.38), "chest"),
        "head": ((0, 0, 2.38), (0, 0, 2.85), "neck"),
        "clavicle.L": ((0, 0, 2.02), (0, 0.24, 2.02), "chest"),
        "upper_arm.L": ((0, 0.24, 2.02), (0, 0.68, 1.72), "clavicle.L"),
        "forearm.L": ((0, 0.68, 1.72), (0, 1.18, 1.48), "upper_arm.L"),
        "hand.L": ((0, 1.18, 1.48), (0, 1.38, 1.43), "forearm.L"),
        "clavicle.R": ((0, 0, 2.02), (0, -0.24, 2.02), "chest"),
        "upper_arm.R": ((0, -0.24, 2.02), (0, -0.68, 1.72), "clavicle.R"),
        "forearm.R": ((0, -0.68, 1.72), (0, -1.18, 1.48), "upper_arm.R"),
        "hand.R": ((0, -1.18, 1.48), (0, -1.38, 1.43), "forearm.R"),
        "thigh.L": ((0, 0.25, 1.0), (0, 0.28, 0.48), "pelvis"),
        "shin.L": ((0, 0.28, 0.48), (0, 0.3, 0.08), "thigh.L"),
        "foot.L": ((0, 0.3, 0.08), (0.22, 0.3, 0.04), "shin.L"),
        "thigh.R": ((0, -0.25, 1.0), (0, -0.28, 0.48), "pelvis"),
        "shin.R": ((0, -0.28, 0.48), (0, -0.3, 0.08), "thigh.R"),
        "foot.R": ((0, -0.3, 0.08), (0.22, -0.3, 0.04), "shin.R"),
    }
    edits = {}
    for bone_name, (head, tail, parent) in bones.items():
        bone = armature.edit_bones.new(bone_name)
        bone.head, bone.tail = head, tail
        if parent:
            bone.parent = edits[parent]
        edits[bone_name] = bone
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.select_set(False)
    suit = material(name + "_Suit", color, metallic=0.08, roughness=0.32)
    dark = material(name + "_Dark", tuple(c * 0.12 for c in color), roughness=0.5)
    skin = material(name + "_Skin", (0.72, 0.48, 0.32), roughness=0.62)
    parts = [
        (
            sphere(name + "_Torso", (0, 0, 1.72), (0.43, 0.36, 0.55), suit),
            {"chest": 0.72, "spine": 0.28},
        ),
        (
            sphere(name + "_Pelvis", (0, 0, 1.02), (0.36, 0.31, 0.27), dark),
            {"pelvis": 0.84, "spine": 0.16},
        ),
        (
            sphere(name + "_Head", (0, 0, 2.58), (0.32, 0.29, 0.38), skin),
            {"head": 0.9, "neck": 0.1},
        ),
    ]
    limb_specs = [
        (
            "UpperArmL",
            (0, 0.24, 2.02),
            (0, 0.68, 1.72),
            0.18,
            suit,
            {"upper_arm.L": 0.85, "clavicle.L": 0.15},
        ),
        (
            "ForearmL",
            (0, 0.68, 1.72),
            (0, 1.18, 1.48),
            0.15,
            skin,
            {"forearm.L": 0.86, "upper_arm.L": 0.14},
        ),
        (
            "HandL",
            (0, 1.18, 1.48),
            (0, 1.4, 1.43),
            0.17,
            skin,
            {"hand.L": 0.8, "forearm.L": 0.2},
        ),
        (
            "UpperArmR",
            (0, -0.24, 2.02),
            (0, -0.68, 1.72),
            0.18,
            suit,
            {"upper_arm.R": 0.85, "clavicle.R": 0.15},
        ),
        (
            "ForearmR",
            (0, -0.68, 1.72),
            (0, -1.18, 1.48),
            0.15,
            skin,
            {"forearm.R": 0.86, "upper_arm.R": 0.14},
        ),
        (
            "HandR",
            (0, -1.18, 1.48),
            (0, -1.4, 1.43),
            0.17,
            skin,
            {"hand.R": 0.8, "forearm.R": 0.2},
        ),
        (
            "ThighL",
            (0, 0.25, 1.0),
            (0, 0.28, 0.48),
            0.22,
            suit,
            {"thigh.L": 0.84, "pelvis": 0.16},
        ),
        (
            "ShinL",
            (0, 0.28, 0.48),
            (0, 0.30, 0.08),
            0.18,
            dark,
            {"shin.L": 0.86, "thigh.L": 0.14},
        ),
        (
            "FootL",
            (0, 0.3, 0.10),
            (0.30, 0.3, 0.07),
            0.17,
            dark,
            {"foot.L": 0.82, "shin.L": 0.18},
        ),
        (
            "ThighR",
            (0, -0.25, 1.0),
            (0, -0.28, 0.48),
            0.22,
            suit,
            {"thigh.R": 0.84, "pelvis": 0.16},
        ),
        (
            "ShinR",
            (0, -0.28, 0.48),
            (0, -0.30, 0.08),
            0.18,
            dark,
            {"shin.R": 0.86, "thigh.R": 0.14},
        ),
        (
            "FootR",
            (0, -0.3, 0.10),
            (0.30, -0.3, 0.07),
            0.17,
            dark,
            {"foot.R": 0.82, "shin.R": 0.18},
        ),
    ]
    parts.extend(
        (cylinder(name + "_" + n, h, t, r, m), w) for n, h, t, r, m, w in limb_specs
    )
    # Joint volumes hide gaps and blend between adjacent deform bones.
    for side, sign in (("L", 1), ("R", -1)):
        parts.extend(
            [
                (
                    sphere(
                        name + "_Shoulder" + side,
                        (0, 0.25 * sign, 2.02),
                        (0.2, 0.2, 0.2),
                        suit,
                    ),
                    {"clavicle." + side: 0.5, "upper_arm." + side: 0.5},
                ),
                (
                    sphere(
                        name + "_Elbow" + side,
                        (0, 0.68 * sign, 1.72),
                        (0.16, 0.16, 0.16),
                        skin,
                    ),
                    {"upper_arm." + side: 0.5, "forearm." + side: 0.5},
                ),
                (
                    sphere(
                        name + "_Knee" + side,
                        (0, 0.28 * sign, 0.48),
                        (0.19, 0.19, 0.19),
                        dark,
                    ),
                    {"thigh." + side: 0.5, "shin." + side: 0.5},
                ),
            ]
        )
    body = join_skinned_body(name, rig, parts)
    rig.location = initial
    rig.animation_data_create()
    rig.animation_data.action = bpy.data.actions.new(name + "_CombatTimeline")
    controls = {}
    constraints = {}
    for key, bone_name, chain in (
        ("hand.R", "forearm.R", 3),
        ("foot.L", "shin.L", 2),
        ("foot.R", "shin.R", 2),
    ):
        tail = rig.matrix_world @ rig.data.bones[bone_name].tail_local
        target = control_empty(name + "_IK_" + key, tail)
        constraint = rig.pose.bones[bone_name].constraints.new("IK")
        constraint.name = "Procedural contact " + key
        constraint.target = target
        constraint.chain_count = chain
        constraint.use_tail = True
        constraint.influence = 0
        rig.pose.bones[bone_name].ik_stretch = 0.12
        controls[key] = target
        constraints[key] = constraint
    rig["wws_rig_type"] = "generic_humanoid_v2"
    body["wws_skinning"] = "single_mesh_explicit_blended_weights"
    return {"rig": rig, "body": body, "controls": controls, "constraints": constraints}


def set_key_interpolation(action, frame, interpolation):
    if not action:
        return
    for curve in action.fcurves:
        for key in curve.keyframe_points:
            if round(key.co.x) == frame:
                key.interpolation = interpolation


def key_root(
    rig,
    frame,
    location,
    rotation_z=None,
    interpolation="BEZIER",
    tilt=0.0,
    roll=0.0,
    yaw_offset=0.0,
    scale=(1, 1, 1),
):
    rig.location = location
    if rotation_z is not None:
        rig.rotation_euler[2] = rotation_z + yaw_offset
    rig.rotation_euler[0] = roll
    rig.rotation_euler[1] = tilt
    rig.scale = scale
    rig.keyframe_insert("location", frame=frame)
    rig.keyframe_insert("rotation_euler", frame=frame)
    rig.keyframe_insert("scale", frame=frame)
    set_key_interpolation(rig.animation_data.action, frame, interpolation)


def key_pose(rig, frame, rotations):
    for name in (
        "pelvis",
        "spine",
        "chest",
        "neck",
        "head",
        "clavicle.L",
        "clavicle.R",
        "upper_arm.L",
        "upper_arm.R",
        "forearm.L",
        "forearm.R",
        "hand.L",
        "hand.R",
        "thigh.L",
        "thigh.R",
        "shin.L",
        "shin.R",
        "foot.L",
        "foot.R",
    ):
        bone = rig.pose.bones.get(name)
        if not bone:
            continue
        bone.rotation_mode = "XYZ"
        bone.rotation_euler = rotations.get(name, (0, 0, 0))
        bone.keyframe_insert("rotation_euler", frame=frame)


POSES = {
    "idle": {},
    "combat_stance": {
        "pelvis": (0, 0.10, 0),
        "spine": (0, 0.14, 0),
        "chest": (0, -0.10, 0),
        "upper_arm.L": (-0.65, 0, -0.58),
        "upper_arm.R": (-0.65, 0, 0.58),
        "forearm.L": (-0.82, 0, 0),
        "forearm.R": (-0.82, 0, 0),
        "thigh.L": (0.22, 0, 0),
        "thigh.R": (-0.18, 0, 0),
        "shin.L": (-0.18, 0, 0),
        "shin.R": (0.18, 0, 0),
    },
    "dash_start": {
        "pelvis": (0, -0.35, 0),
        "spine": (0, -0.55, 0),
        "chest": (0, -0.2, 0),
        "upper_arm.L": (-1.15, 0, -0.9),
        "upper_arm.R": (0.7, 0, 0.8),
        "thigh.L": (0.9, 0, 0),
        "thigh.R": (-0.65, 0, 0),
        "shin.L": (-0.65, 0, 0),
    },
    "dash_travel": {
        "spine": (0, 1.08, 0),
        "chest": (0, 0.42, 0),
        "head": (0, -0.35, 0),
        "upper_arm.L": (-1.35, 0, -0.7),
        "upper_arm.R": (1.15, 0, 0.75),
        "forearm.L": (-0.5, 0, 0),
        "forearm.R": (-0.4, 0, 0),
        "thigh.L": (0.55, 0, 0),
        "thigh.R": (-0.7, 0, 0),
    },
    "dash_stop": {
        "pelvis": (0, 0.55, 0),
        "spine": (0, 0.72, 0),
        "chest": (0, 0.3, 0),
        "upper_arm.L": (0.7, 0, -0.9),
        "upper_arm.R": (-1.0, 0, 0.7),
        "thigh.L": (-0.75, 0, 0),
        "thigh.R": (0.9, 0, 0),
    },
    "punch_anticipation": {
        "pelvis": (0, -0.25, 0.35),
        "spine": (0, -0.38, 0.5),
        "chest": (0, -0.18, 0.42),
        "head": (0, 0.12, -0.2),
        "upper_arm.R": (-1.7, 0, 0.85),
        "forearm.R": (-1.2, 0, 0),
        "upper_arm.L": (-0.7, 0, -0.5),
        "forearm.L": (-0.8, 0, 0),
        "thigh.L": (0.35, 0, 0),
        "thigh.R": (-0.42, 0, 0),
    },
    "punch_contact": {
        "pelvis": (0, 0.3, -0.48),
        "spine": (0, 0.38, -0.58),
        "chest": (0, 0.16, -0.45),
        "head": (0, -0.08, 0.18),
        "clavicle.R": (0, 0, -0.28),
        "upper_arm.R": (0.18, 0, -1.32),
        "forearm.R": (0.08, 0, 0),
        "upper_arm.L": (-0.65, 0, -0.55),
        "forearm.L": (-0.72, 0, 0),
        "thigh.L": (-0.35, 0, 0),
        "thigh.R": (0.48, 0, 0),
    },
    "punch_followthrough": {
        "pelvis": (0, 0.3, -0.7),
        "spine": (0, 0.48, -0.78),
        "chest": (0, 0.25, -0.62),
        "upper_arm.R": (0.45, 0, -1.35),
        "forearm.R": (0.2, 0, 0),
        "upper_arm.L": (-0.35, 0, -0.5),
    },
    "heavy_punch": {
        "spine": (0, 0.5, -0.65),
        "chest": (0, 0.18, -0.5),
        "upper_arm.R": (0.22, 0, -1.5),
        "forearm.R": (0.05, 0, 0),
    },
    "kick": {
        "spine": (0, 0.28, 0),
        "thigh.R": (-1.55, 0, 0),
        "shin.R": (0.25, 0, 0),
        "upper_arm.L": (-0.6, 0, -0.6),
        "upper_arm.R": (0.4, 0, 0.5),
    },
    "dodge_left": {
        "pelvis": (0, -0.35, -0.48),
        "spine": (0, -0.55, -0.82),
        "chest": (0, -0.15, -0.45),
        "head": (0, 0.2, 0.28),
        "upper_arm.L": (-1.05, 0, -0.3),
        "upper_arm.R": (0.65, 0, 0.3),
        "thigh.L": (0.72, 0, 0),
        "thigh.R": (-0.55, 0, 0),
    },
    "dodge_right": {
        "pelvis": (0, -0.35, 0.48),
        "spine": (0, -0.55, 0.82),
        "chest": (0, -0.15, 0.45),
        "head": (0, 0.2, -0.28),
        "upper_arm.L": (0.65, 0, -0.3),
        "upper_arm.R": (-1.05, 0, 0.3),
    },
    "air_dodge": {
        "spine": (0, -0.35, -0.75),
        "upper_arm.L": (1, 0, -0.6),
        "upper_arm.R": (-1, 0, 0.6),
        "thigh.L": (0.8, 0, 0),
        "thigh.R": (-0.8, 0, 0),
    },
    "block": {
        "spine": (0, -0.22, 0),
        "upper_arm.L": (-1.1, 0, -0.75),
        "upper_arm.R": (-1.1, 0, 0.75),
        "forearm.L": (-0.9, 0, 0),
        "forearm.R": (-0.9, 0, 0),
    },
    "hit_light": {
        "spine": (0, -0.5, 0.35),
        "chest": (0, -0.3, 0.25),
        "upper_arm.L": (0.6, 0, 0.4),
        "upper_arm.R": (-0.6, 0, -0.4),
    },
    "hit_heavy": {
        "pelvis": (0, -0.55, 0.65),
        "spine": (0, -0.95, 0.75),
        "chest": (0, -0.5, 0.55),
        "head": (0, 0.55, -0.35),
        "upper_arm.L": (1.35, 0, 0.9),
        "upper_arm.R": (-1.2, 0, -0.9),
        "thigh.L": (0.65, 0, 0),
        "thigh.R": (-0.45, 0, 0),
    },
    "launch": {
        "spine": (0, -0.95, 0.55),
        "chest": (0, -0.35, 0.45),
        "upper_arm.L": (1.45, 0, 0.9),
        "upper_arm.R": (-1.35, 0, -0.9),
        "thigh.L": (0.8, 0, 0),
        "thigh.R": (-0.6, 0, 0),
    },
    "airborne_knockback": {
        "spine": (0, -0.55, 0.3),
        "upper_arm.L": (1.1, 0, 0.8),
        "upper_arm.R": (-1.1, 0, -0.8),
        "forearm.L": (-0.5, 0, 0),
        "forearm.R": (-0.5, 0, 0),
        "thigh.L": (0.85, 0, 0),
        "thigh.R": (-0.65, 0, 0),
        "shin.L": (-0.6, 0, 0),
    },
    "wall_impact": {
        "spine": (0, 0.72, 0),
        "chest": (0, 0.3, 0),
        "upper_arm.L": (1, 0, -0.8),
        "upper_arm.R": (1, 0, 0.8),
        "thigh.L": (-0.4, 0, 0),
        "thigh.R": (0.55, 0, 0),
    },
    "ground_impact": {
        "spine": (0, 0.9, 0),
        "chest": (0, 0.45, 0),
        "upper_arm.L": (-1.25, 0, -0.55),
        "upper_arm.R": (-1.25, 0, 0.55),
        "thigh.L": (1.05, 0, 0),
        "thigh.R": (0.9, 0, 0),
        "shin.L": (-0.8, 0, 0),
        "shin.R": (-0.7, 0, 0),
    },
    "landing": {
        "pelvis": (0, 0.4, 0),
        "spine": (0, 0.82, 0),
        "chest": (0, 0.3, 0),
        "upper_arm.L": (-1.1, 0, -0.5),
        "upper_arm.R": (-1.1, 0, 0.5),
        "thigh.L": (1.05, 0, 0),
        "thigh.R": (0.85, 0, 0),
        "shin.L": (-0.85, 0, 0),
        "shin.R": (-0.75, 0, 0),
    },
    "recovery": {
        "pelvis": (0, 0.18, 0),
        "spine": (0, 0.28, 0),
        "chest": (0, -0.08, 0),
        "upper_arm.L": (-0.72, 0, -0.58),
        "upper_arm.R": (-0.72, 0, 0.58),
        "forearm.L": (-0.8, 0, 0),
        "forearm.R": (-0.8, 0, 0),
        "thigh.L": (0.32, 0, 0),
        "thigh.R": (-0.22, 0, 0),
    },
}


# These keyframes are authored once into native Blender Actions. Scene assembly
# reuses/retargets the Actions through NLA instead of rebuilding body poses per event.
CLIP_BLUEPRINTS = {
    "combat_idle": [(1, "combat_stance"), (16, "recovery"), (31, "combat_stance")],
    "stance": [(1, "combat_stance"), (18, "recovery"), (36, "combat_stance")],
    "step_forward": [(1, "combat_stance"), (8, "dash_start"), (16, "combat_stance")],
    "step_back": [(1, "combat_stance"), (8, "dash_stop"), (16, "combat_stance")],
    "sprint": [
        (1, "dash_start"),
        (7, "dash_travel"),
        (16, "dash_travel"),
        (22, "dash_stop"),
    ],
    "dash": [
        (1, "combat_stance"),
        (6, "dash_start"),
        (9, "dash_travel"),
        (17, "dash_travel"),
        (22, "dash_stop"),
        (26, "combat_stance"),
    ],
    "aerial_travel": [(1, "launch"), (10, "airborne_knockback"), (22, "air_dodge")],
    "jab": [
        (1, "combat_stance"),
        (5, "punch_anticipation"),
        (9, "punch_contact"),
        (11, "punch_followthrough"),
        (16, "combat_stance"),
    ],
    "cross": [
        (1, "combat_stance"),
        (7, "punch_anticipation"),
        (12, "punch_contact"),
        (15, "punch_followthrough"),
        (22, "recovery"),
    ],
    "heavy_cross": [
        (1, "combat_stance"),
        (8, "punch_anticipation"),
        (13, "punch_anticipation"),
        (18, "punch_contact"),
        (21, "heavy_punch"),
        (26, "punch_followthrough"),
        (32, "recovery"),
    ],
    "hook": [
        (1, "combat_stance"),
        (7, "punch_anticipation"),
        (13, "heavy_punch"),
        (18, "punch_followthrough"),
        (24, "recovery"),
    ],
    "uppercut": [
        (1, "combat_stance"),
        (8, "punch_anticipation"),
        (14, "heavy_punch"),
        (19, "punch_followthrough"),
        (25, "recovery"),
    ],
    "body_punch": [
        (1, "combat_stance"),
        (7, "punch_anticipation"),
        (13, "punch_contact"),
        (18, "punch_followthrough"),
        (23, "recovery"),
    ],
    "front_kick": [
        (1, "combat_stance"),
        (7, "punch_anticipation"),
        (14, "kick"),
        (17, "kick"),
        (24, "combat_stance"),
    ],
    "roundhouse": [
        (1, "combat_stance"),
        (8, "punch_anticipation"),
        (15, "kick"),
        (20, "punch_followthrough"),
        (28, "recovery"),
    ],
    "flying_punch": [
        (1, "dash_start"),
        (8, "dash_travel"),
        (14, "punch_contact"),
        (18, "punch_followthrough"),
        (24, "recovery"),
    ],
    "aerial_kick": [
        (1, "air_dodge"),
        (9, "kick"),
        (14, "kick"),
        (22, "airborne_knockback"),
    ],
    "downward_strike": [
        (1, "air_dodge"),
        (8, "punch_anticipation"),
        (13, "heavy_punch"),
        (19, "punch_followthrough"),
    ],
    "dodge_left": [
        (1, "combat_stance"),
        (6, "dash_start"),
        (10, "dodge_left"),
        (14, "dodge_left"),
        (21, "combat_stance"),
    ],
    "dodge_right": [
        (1, "combat_stance"),
        (6, "dash_start"),
        (10, "dodge_right"),
        (14, "dodge_right"),
        (21, "combat_stance"),
    ],
    "backstep": [
        (1, "combat_stance"),
        (6, "dash_stop"),
        (12, "dodge_right"),
        (20, "combat_stance"),
    ],
    "duck": [
        (1, "combat_stance"),
        (6, "landing"),
        (12, "landing"),
        (19, "combat_stance"),
    ],
    "lean_dodge": [
        (1, "combat_stance"),
        (7, "dodge_left"),
        (13, "dodge_left"),
        (21, "combat_stance"),
    ],
    "block_high": [
        (1, "combat_stance"),
        (7, "block"),
        (15, "block"),
        (23, "combat_stance"),
    ],
    "block_body": [
        (1, "combat_stance"),
        (7, "block"),
        (14, "landing"),
        (22, "combat_stance"),
    ],
    "hit_head": [
        (1, "combat_stance"),
        (4, "hit_light"),
        (7, "hit_light"),
        (16, "recovery"),
    ],
    "hit_body": [
        (1, "combat_stance"),
        (4, "hit_heavy"),
        (7, "hit_heavy"),
        (17, "recovery"),
    ],
    "heavy_hit": [
        (1, "wall_impact"),
        (4, "hit_heavy"),
        (7, "hit_heavy"),
        (13, "launch"),
        (20, "airborne_knockback"),
    ],
    "stagger": [
        (1, "combat_stance"),
        (5, "hit_light"),
        (11, "dash_stop"),
        (20, "recovery"),
    ],
    "spin_reaction": [
        (1, "hit_heavy"),
        (7, "launch"),
        (14, "airborne_knockback"),
        (22, "air_dodge"),
    ],
    "launch_backward": [
        (1, "hit_heavy"),
        (5, "launch"),
        (12, "airborne_knockback"),
        (22, "airborne_knockback"),
    ],
    "launch_upward": [
        (1, "hit_heavy"),
        (5, "launch"),
        (11, "air_dodge"),
        (21, "airborne_knockback"),
    ],
    "airborne_tumble": [
        (1, "launch"),
        (7, "airborne_knockback"),
        (13, "air_dodge"),
        (19, "airborne_knockback"),
        (25, "launch"),
    ],
    "wall_impact": [
        (1, "airborne_knockback"),
        (5, "wall_impact"),
        (9, "wall_impact"),
        (17, "hit_heavy"),
    ],
    "ground_impact": [
        (1, "airborne_knockback"),
        (6, "ground_impact"),
        (10, "ground_impact"),
        (18, "landing"),
    ],
    "hard_landing": [
        (1, "airborne_knockback"),
        (10, "air_dodge"),
        (15, "ground_impact"),
        (18, "ground_impact"),
        (22, "landing"),
        (27, "recovery"),
        (32, "combat_stance"),
    ],
    "landing_recoil": [
        (1, "ground_impact"),
        (7, "landing"),
        (14, "recovery"),
        (22, "combat_stance"),
    ],
    "ground_skid": [
        (1, "ground_impact"),
        (8, "landing"),
        (16, "dash_stop"),
        (24, "recovery"),
    ],
    "get_up": [
        (1, "ground_impact"),
        (10, "landing"),
        (22, "recovery"),
        (34, "combat_stance"),
    ],
    "aerial_recovery": [
        (1, "airborne_knockback"),
        (8, "air_dodge"),
        (16, "launch"),
        (24, "landing"),
    ],
}


CLIP_PHASES = {
    "dash": (6, 9, 22, 26),
    "dodge_left": (6, 10, 14, 21),
    "dodge_right": (6, 10, 14, 21),
    "heavy_cross": (13, 18, 26, 32),
    "heavy_hit": (3, 4, 13, 20),
    "launch_backward": (3, 5, 15, 22),
    "airborne_tumble": (5, 8, 19, 25),
    "hard_landing": (10, 15, 27, 32),
    "get_up": (10, 18, 28, 34),
}


def reset_pose(rig):
    for bone in rig.pose.bones:
        bone.rotation_mode = "XYZ"
        bone.rotation_euler = (0, 0, 0)


def build_action_library(authoring_rig, clip_names):
    """Author a reusable native-Action pack once in the generated blend file."""
    root_action = authoring_rig.animation_data.action
    library = {}
    for clip_id in clip_names:
        blueprint = CLIP_BLUEPRINTS[clip_id]
        action = bpy.data.actions.new("WWS_LIB_" + clip_id)
        action.use_fake_user = True
        action["wws_clip_id"] = clip_id
        action["wws_phases"] = json.dumps(
            CLIP_PHASES.get(
                clip_id,
                (
                    blueprint[1][0],
                    blueprint[len(blueprint) // 2][0],
                    blueprint[-2][0],
                    blueprint[-1][0],
                ),
            )
        )
        authoring_rig.animation_data.action = action
        reset_pose(authoring_rig)
        for frame, pose_name in blueprint:
            rotations = dict(POSES["combat_stance"])
            rotations.update(POSES[pose_name])
            key_pose(authoring_rig, frame, rotations)
        for curve in action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "BEZIER"
        library[clip_id] = action
    authoring_rig.animation_data.action = root_action
    reset_pose(authoring_rig)
    return library


def mirrored_bone(name):
    if name.endswith(".L"):
        return name[:-2] + ".R"
    if name.endswith(".R"):
        return name[:-2] + ".L"
    return name


def derive_action(base, adapter, raw, name):
    """Copy, mirror, vary and retarget a library Action for one fighter."""
    derived = base.copy()
    derived.name = name
    variation = raw.get("variation", {})
    mirrored = variation.get("mirrored", False)
    amplitude = variation.get("pose_amplitude", 1.0)
    torso = math.radians(variation.get("torso_twist_degrees", 0.0))
    attack_angle = math.radians(variation.get("attack_angle_degrees", 0.0))
    pattern = re.compile(r'pose\.bones\["([^"]+)"\]')
    for curve in derived.fcurves:
        match = pattern.search(curve.data_path)
        if not match:
            continue
        standard = match.group(1)
        selected = mirrored_bone(standard) if mirrored else standard
        target = adapter.get(selected, selected)
        curve.data_path = curve.data_path.replace(
            f'pose.bones["{standard}"]', f'pose.bones["{target}"]'
        )
        for point in curve.keyframe_points:
            value = point.co[1] * amplitude
            if mirrored and curve.array_index in {1, 2}:
                value *= -1
            if selected in {"pelvis", "spine", "chest"} and curve.array_index == 2:
                value += torso
            if selected.startswith("upper_arm") and curve.array_index == 1:
                value += attack_angle
            point.co[1] = value
    derived["wws_retargeted"] = True
    derived["wws_source_action"] = base.name
    return derived


def add_nla_clip(bundle, raw, adapter, library):
    """Place a retargeted clip through NLA with phase-aware strip time."""
    rig = bundle["rig"]
    clip_id = raw["clip_id"]
    action = derive_action(
        library[clip_id], adapter, raw, f"{rig.name}_{clip_id}_{raw['start_frame']:03d}"
    )
    track = rig.animation_data.nla_tracks.new()
    track.name = f"WWS_{clip_id}_{raw['start_frame']:03d}"
    strip = track.strips.new(track.name, raw["start_frame"], action)
    strip.action_frame_start, strip.action_frame_end = action.frame_range
    strip.frame_start, strip.frame_end = raw["start_frame"], raw["end_frame"]
    strip.extrapolation = "NOTHING"
    strip.blend_type = "REPLACE"
    strip.blend_in = raw.get("blend_in_frames", 2)
    strip.blend_out = raw.get("blend_out_frames", 2)
    if raw.get("loop"):
        native = max(1.0, action.frame_range[1] - action.frame_range[0])
        strip.repeat = max(1.0, (raw["end_frame"] - raw["start_frame"]) / native)
        strip.frame_end = raw["end_frame"]
        return strip

    phase = json.loads(action.get("wws_phases", "[6, 12, 18, 24]"))
    native_start = float(action.frame_range[0])
    ant_end, contact, follow_end, native_end = map(float, phase)
    warp = raw.get("time_warp", {})
    weights = [
        max(0.1, ant_end - native_start) * warp.get("anticipation_scale", 1.0),
        max(0.1, contact - ant_end) * warp.get("attack_scale", 1.0),
        max(0.1, follow_end - contact) * warp.get("followthrough_scale", 1.0),
        max(0.1, native_end - follow_end) * warp.get("recovery_scale", 1.0),
    ]
    start, end = raw["start_frame"], raw["end_frame"]
    hold = min(warp.get("impact_hold_frames", 0), max(0, end - start - 4))
    available = max(4, end - start - hold)
    scale = available / sum(weights)
    scene_ant = start + round(weights[0] * scale)
    scene_contact = raw.get("contact_frame") or scene_ant + round(weights[1] * scale)
    scene_contact = max(scene_ant + 1, min(end - hold - 2, scene_contact))
    scene_follow = min(end - 1, scene_contact + hold + round(weights[2] * scale))
    strip.use_animated_time = True
    keys = [
        (start, native_start),
        (scene_ant, ant_end),
        (scene_contact, contact),
        (scene_contact + hold, contact),
        (scene_follow, follow_end),
        (end, native_end),
    ]
    for frame, action_time in keys:
        strip.strip_time = action_time
        strip.keyframe_insert("strip_time", frame=frame)
    return strip


def pose(bundle, frame, name):
    key_pose(bundle["rig"], frame, POSES[name])


def local_to_world(root, facing, offset):
    x, y, z = offset
    c, s = math.cos(facing), math.sin(facing)
    return root + Vector((c * x - s * y, s * x + c * y, z))


def key_ik(bundle, key, frame, influence, location=None, interpolation="BEZIER"):
    target = bundle["controls"][key]
    constraint = bundle["constraints"][key]
    if location is not None:
        target.location = location
        target.keyframe_insert("location", frame=frame)
        set_key_interpolation(target.animation_data.action, frame, interpolation)
    constraint.influence = influence
    constraint.keyframe_insert("influence", frame=frame)
    # IK activation is a contact switch. Bezier interpolation would leak planted-foot
    # constraints into later airborne sections and pull the character off trajectory.
    set_key_interpolation(bundle["rig"].animation_data.action, frame, "CONSTANT")


def key_trajectory(rig, raw, facing):
    start, end = raw["start_frame"], raw["end_frame"]
    span = end - start
    a, target = vec(raw["start_position"]), vec(raw["target_position"])
    overshoot = (
        vec(raw["overshoot_position"]) if raw.get("overshoot_position") else target
    )
    recovery = vec(raw["recovery_position"]) if raw.get("recovery_position") else target
    kind = raw.get("trajectory", "stationary")
    if kind == "accelerating_blitz":
        anticipation = start + max(3, round(span * 0.32))
        contact = raw.get("impact_frame") or start + round(span * 0.71)
        over = start + round(span * 0.84)
        key_root(rig, start, a, facing)
        key_root(rig, anticipation, a, facing, "BEZIER", scale=(0.92, 1.0, 1.06))
        key_root(rig, contact, target, facing, "LINEAR", scale=(1.28, 0.82, 0.9))
        key_root(rig, over, overshoot, facing, "LINEAR", scale=(1.08, 0.94, 0.96))
        key_root(rig, end, recovery, facing)
    elif kind == "decelerating_approach":
        fast = start + round(span * 0.35)
        settle = start + round(span * 0.76)
        key_root(rig, start, a, facing)
        key_root(rig, fast, a.lerp(target, 0.72), facing, "LINEAR")
        key_root(rig, settle, overshoot, facing, "BEZIER")
        key_root(rig, end, recovery, facing)
    elif kind == "curved_approach":
        hold = start + round(span * 0.25)
        near = start + round(span * 0.40)
        snap = start + round(span * 0.52)
        key_root(rig, start, a, facing)
        key_root(rig, hold, a, facing, "CONSTANT", tilt=-0.08)
        key_root(rig, near, a.lerp(overshoot, 0.2), facing, "BEZIER", tilt=-0.12)
        key_root(rig, snap, overshoot, facing, "LINEAR", tilt=-0.16)
        key_root(rig, end, recovery, facing)
    elif kind in {"launch_trajectory", "rotational_launch"}:
        angular = (
            vec(raw["angular_momentum"])
            if raw.get("angular_momentum")
            else Vector((0.2, 1.0, 0.2))
        )
        key_root(rig, start, a, facing)
        key_root(rig, start + 4, a, facing, "LINEAR")
        key_root(
            rig,
            start + round(span * 0.42),
            overshoot,
            facing,
            "LINEAR",
            tilt=math.pi * 0.72 * angular.y,
            roll=angular.x * 0.42,
            yaw_offset=angular.z * 0.35,
        )
        key_root(
            rig,
            end,
            target,
            facing,
            "BEZIER",
            tilt=math.pi * 1.55 * angular.y,
            roll=angular.x * 0.8,
            yaw_offset=angular.z * 0.7,
        )
    elif kind in {"aerial_arc", "knockback_trajectory"}:
        angular = (
            vec(raw["angular_momentum"])
            if raw.get("angular_momentum")
            else Vector((0, 1, 0))
        )
        key_root(rig, start, a, facing, tilt=math.pi * 1.55, roll=angular.x)
        key_root(
            rig,
            start + round(span * 0.3),
            overshoot,
            facing,
            "BEZIER",
            tilt=math.pi * (1.8 + angular.y * 0.18),
            roll=angular.x * 1.5,
            yaw_offset=angular.z * 0.45,
        )
        key_root(
            rig,
            end,
            target,
            facing,
            "BEZIER",
            tilt=math.pi * (2.05 + angular.y * 0.22),
            roll=angular.x * 2.0,
            yaw_offset=angular.z * 0.8,
        )
    elif kind == "recovery_landing":
        contact = raw.get("impact_frame") or end - min(8, max(3, span // 3))
        severity = raw.get("landing_severity", 0.0)
        key_root(rig, start, a, facing, tilt=math.pi * 2.05)
        key_root(
            rig,
            contact,
            overshoot,
            facing,
            "LINEAR",
            tilt=0,
            scale=(1.08, 1.08, 1.0 - severity * 0.16),
        )
        if severity:
            bounce = min(end - 2, contact + 3)
            skid = min(end - 1, contact + 6)
            key_root(
                rig,
                bounce,
                recovery + Vector((0, 0, 0.22 * severity)),
                facing,
                "BEZIER",
                tilt=-0.12 * severity,
            )
            key_root(
                rig,
                skid,
                recovery + Vector((-0.28 * severity, 0, 0)),
                facing,
                "LINEAR",
                tilt=0.08 * severity,
            )
        key_root(rig, end, recovery, facing)
    elif kind == "wall_impact":
        key_root(rig, start, a, facing)
        key_root(
            rig, min(end, start + 3), a + Vector((0.08, 0, 0.04)), facing, "CONSTANT"
        )
        key_root(rig, end, target, facing)
    else:
        key_root(rig, start, a, facing)
        key_root(
            rig,
            end,
            target,
            facing,
            "LINEAR" if kind in {"linear_blitz", "ground_skid"} else "BEZIER",
        )


def plant_feet(bundle, root, facing, start, end):
    for key, side in (("foot.L", 0.3), ("foot.R", -0.3)):
        point = local_to_world(root, facing, (0.18, side, 0.05))
        key_ik(bundle, key, start, 1, point)
        key_ik(bundle, key, end, 1, point)
        key_ik(bundle, key, end + 1, 0, point, "CONSTANT")


def apply_hybrid_instruction(bundle, raw, facing, adapter, library):
    """Compose authored body clips, procedural root motion and brief IK correction."""
    start, end = raw["start_frame"], raw["end_frame"]
    a, b = vec(raw["start_position"]), vec(raw["target_position"])
    action = raw["action"]
    key_trajectory(bundle["rig"], raw, facing)
    for clip in raw["clip_stack"]:
        add_nla_clip(bundle, clip, adapter, library)

    if action == "combat_stance" and end - start < 90:
        plant_feet(bundle, a, facing, start, end)
    elif action in {"dash", "sprint"}:
        release = start + max(4, round((end - start) * 0.28))
        plant_feet(bundle, a, facing, start, release)
    elif action == "dodge":
        plant_feet(bundle, a, facing, start, start + 6)
    elif action in {"punch", "heavy_punch"}:
        contact = raw.get("impact_frame") or end - 14
        point = vec(raw["contact_position"])
        rest = local_to_world(a, facing, (0, -1.2, 1.48))
        plant_feet(bundle, a, facing, start, max(start, contact - 2))
        # Authored arm motion remains dominant until the final four frames.
        key_ik(bundle, "hand.R", start, 0, rest)
        key_ik(bundle, "hand.R", max(start, contact - 4), 0, rest, "CONSTANT")
        key_ik(
            bundle,
            "hand.R",
            max(start, contact - 2),
            0.38,
            rest.lerp(point, 0.55),
            "BEZIER",
        )
        key_ik(bundle, "hand.R", contact, 1, point, "LINEAR")
        hold = next(
            (
                clip["time_warp"].get("impact_hold_frames", 0)
                for clip in raw["clip_stack"]
                if clip.get("contact_frame") == contact
            ),
            0,
        )
        key_ik(bundle, "hand.R", contact + hold, 1, point, "CONSTANT")
        key_ik(
            bundle,
            "hand.R",
            min(end, contact + hold + 4),
            0.25,
            point + local_to_world(Vector((0, 0, 0)), facing, (0.12, 0, 0)),
        )
        key_ik(bundle, "hand.R", min(end, contact + hold + 7), 0, rest)
    elif action == "landing":
        contact = raw.get("impact_frame") or end - 8
        for key, side in (("foot.L", 0.3), ("foot.R", -0.3)):
            point = local_to_world(b, facing, (0.18, side, 0.05))
            key_ik(bundle, key, max(start, contact - 3), 0, point, "CONSTANT")
            key_ik(bundle, key, contact, 1, point, "LINEAR")
            key_ik(bundle, key, end, 1, point)
            key_ik(bundle, key, end + 1, 0, point, "CONSTANT")


def apply_instruction(bundle, raw, facing):
    start, end = raw["start_frame"], raw["end_frame"]
    a, b = vec(raw["start_position"]), vec(raw["target_position"])
    name, intensity = raw["action"], raw["intensity"]
    rig = bundle["rig"]
    key_trajectory(rig, raw, facing)
    if name in {"idle", "combat_stance", "recovery"}:
        pose(
            bundle,
            start,
            (
                "idle"
                if name == "idle"
                else ("recovery" if name == "recovery" else "combat_stance")
            ),
        )
        pose(bundle, end, "combat_stance" if name != "recovery" else "recovery")
        if name == "combat_stance" and end - start < 90:
            plant_feet(bundle, a, facing, start, end)
    elif name in {"dash", "sprint"}:
        anticipation = start + max(3, round((end - start) * 0.32))
        pose(bundle, start, "combat_stance")
        pose(bundle, anticipation, "dash_start")
        pose(bundle, anticipation + 3, "dash_travel")
        pose(bundle, end - 4, "dash_stop")
        pose(bundle, end, "combat_stance")
        plant_feet(bundle, a, facing, start, anticipation)
    elif name == "dodge":
        pose(bundle, start, "combat_stance")
        pose(bundle, start + round((end - start) * 0.55), "dodge_left")
        pose(bundle, end, "combat_stance")
        plant_feet(bundle, a, facing, start, start + 6)
    elif name in {"punch", "heavy_punch"}:
        contact = end - 14
        anticipation = start + 14
        pose(bundle, start, "combat_stance")
        pose(bundle, anticipation, "punch_anticipation")
        pose(bundle, contact, "punch_contact")
        pose(bundle, contact + 3, "punch_contact")
        pose(bundle, min(end, contact + 8), "punch_followthrough")
        pose(bundle, end, "recovery")
        plant_feet(bundle, a, facing, start, contact - 2)
        point = vec(raw["contact_position"])
        wrist = point
        rest = local_to_world(a, facing, (0, -1.2, 1.48))
        key_ik(bundle, "hand.R", start, 0, rest)
        key_ik(bundle, "hand.R", anticipation, 0.35, rest)
        key_ik(bundle, "hand.R", contact, 1, wrist, "LINEAR")
        key_ik(bundle, "hand.R", contact + 3, 1, wrist, "CONSTANT")
        key_ik(
            bundle,
            "hand.R",
            contact + 8,
            0.25,
            wrist + local_to_world(Vector((0, 0, 0)), facing, (0.12, 0, 0)),
        )
        key_ik(bundle, "hand.R", end, 0, rest)
    elif name == "hit_reaction":
        contact = start + 2
        pose(bundle, start, "wall_impact")
        pose(bundle, contact, "hit_heavy")
        pose(bundle, min(end, contact + 3), "hit_heavy")
        pose(bundle, end, "launch")
    elif name in {"launch", "knockback", "aerial_movement", "fall"}:
        pose(bundle, start, "launch" if name == "launch" else "airborne_knockback")
        pose(bundle, start + max(4, (end - start) // 2), "airborne_knockback")
        pose(bundle, end, "airborne_knockback")
    elif name == "jump":
        pose(bundle, start, "dash_start")
        pose(bundle, (start + end) // 2, "airborne_knockback")
        pose(bundle, end, "landing")
    elif name == "kick":
        contact = end - max(2, (end - start) // 4)
        pose(bundle, start, "punch_anticipation")
        pose(bundle, contact, "kick")
        pose(bundle, min(end, contact + 2), "kick")
        pose(bundle, end, "combat_stance")
    elif name == "block":
        pose(bundle, start, "block")
        pose(bundle, end, "block")
    elif name == "landing":
        contact = end - 8
        pose(bundle, start, "airborne_knockback")
        pose(bundle, contact, "ground_impact")
        pose(bundle, contact + 3, "ground_impact")
        pose(bundle, end, "landing")
        plant_feet(bundle, b, facing, contact, end)
    else:
        pose(bundle, start, "combat_stance")
        pose(bundle, end, "combat_stance")


def create_arena(mats, rng):
    cube("Ground", (0, 0, -0.28), (11, 8, 0.25), mats["ground"], 0.12)
    cube("ImpactWall", (6.15, 0, 2.2), (0.35, 2.0, 2.2), mats["wall"], 0.08)
    # Keep the skyline behind the action plane. Foreground buildings made vertical
    # portrait cameras accidentally hide contacts at the wall.
    for index in range(10):
        x = -12 + index * 2.65
        y = 7.2 + rng.random() * 1.8
        h = 2.5 + rng.random() * 5
        cube(
            f"BackgroundBuilding_{index:02d}",
            (x, y, h / 2),
            (1.0, 1.1, h / 2),
            mats["building"],
            0.06,
        )
    for index, x in enumerate((-6, -1, 4)):
        cube(
            f"BrokenColumn_{index}",
            (x, 3.7, 1.2),
            (0.35, 0.35, 1.2),
            mats["wall"],
            0.04,
        )
    # Graphic floor marks strengthen perspective in a vertical frame.
    for index in range(7):
        cube(
            f"FloorStripe_{index}",
            (-6 + index * 2, 0, 0.005),
            (0.025, 7, 0.008),
            mats["accent"],
            0,
        )


def create_cameras(plan):
    scene = bpy.context.scene
    for raw in plan["camera_shots"]:
        data = bpy.data.cameras.new(raw["shot_id"] + "_Data")
        cam = bpy.data.objects.new(raw["shot_id"], data)
        bpy.context.collection.objects.link(cam)
        data.lens = raw["lens_mm"]
        target = bpy.data.objects.new(raw["shot_id"] + "_Target", None)
        bpy.context.collection.objects.link(target)
        start, end = raw["start_frame"], raw["end_frame"]
        c0, c1 = vec(raw["location_start"]), vec(raw["location_end"])
        t0, t1 = vec(raw["target_start"]), vec(raw["target_end"])

        def camera_key(frame, camera_position, target_position, interpolation="BEZIER"):
            cam.location, target.location = camera_position, target_position
            cam.keyframe_insert("location", frame=frame)
            target.keyframe_insert("location", frame=frame)
            set_key_interpolation(cam.animation_data.action, frame, interpolation)
            set_key_interpolation(target.animation_data.action, frame, interpolation)

        behavior = raw["behavior"]
        camera_key(start, c0, t0)
        if behavior == "tracking":
            # The operator lags the blitz, then catches it in one abrupt pan.
            camera_key(start + 5, c0, t0, "CONSTANT")
            camera_key(end - 6, c0.lerp(c1, 0.78), t0.lerp(t1, 0.88), "LINEAR")
        elif behavior == "whip_pan":
            camera_key(start + 5, c0, t0, "CONSTANT")
            camera_key(min(end - 3, start + 11), c0.lerp(c1, 0.92), t1, "LINEAR")
        elif behavior == "impact_camera":
            hold = min(end, start + max(2, raw["hit_stop_frames"]))
            camera_key(hold, c0, t0, "CONSTANT")
            camera_key(min(end, hold + 1), c0.lerp(c1, 0.12), t0, "LINEAR")
        elif behavior == "knockback_tracking":
            camera_key(start + 4, c0, t0, "CONSTANT")
            camera_key(
                start + round((end - start) * 0.58),
                c0.lerp(c1, 0.66),
                t0.lerp(t1, 0.76),
                "LINEAR",
            )
        elif behavior == "high_angle":
            camera_key(
                start + round((end - start) * 0.72),
                c0.lerp(c1, 0.72),
                t0.lerp(t1, 0.82),
                "BEZIER",
            )
        camera_key(end, c1, t1)
        constraint = cam.constraints.new("TRACK_TO")
        constraint.target = target
        constraint.track_axis = "TRACK_NEGATIVE_Z"
        constraint.up_axis = "UP_Y"
        marker = scene.timeline_markers.new(raw["shot_id"], frame=raw["start_frame"])
        marker.camera = cam
        if raw["shake"]:
            shake_start, shake_end = start, end
            if behavior == "tracking":
                shake_start = max(start, end - 12)
            elif behavior == "close_up":
                shake_start, shake_end = start + 3, min(end, start + 11)
            elif behavior == "whip_pan":
                shake_start, shake_end = start + 4, min(end, start + 15)
            elif behavior == "knockback_tracking":
                shake_end = min(end, start + 13)
            elif behavior == "high_angle":
                shake_start = max(start, end - 10)
            for curve in cam.animation_data.action.fcurves:
                if curve.data_path != "location":
                    continue
                noise = curve.modifiers.new("NOISE")
                noise.strength = raw["shake"] * 0.11
                noise.scale = 2.4
                noise.phase = raw["start_frame"] * 0.73
                noise.use_restricted_range = True
                noise.frame_start = shake_start
                noise.frame_end = shake_end
        if scene.camera is None:
            scene.camera = cam


def scale_keys(obj, values):
    for frame, scale in values:
        obj.scale = scale
        obj.keyframe_insert("scale", frame=frame)
        obj.hide_render = max(scale) < 0.001
        obj.keyframe_insert("hide_render", frame=frame)


def create_effect(raw, mats, rng):
    frame, end, p, intensity = (
        raw["frame"],
        raw["end_frame"],
        vec(raw["position"]),
        raw["intensity"],
    )
    effect = raw["effect"]
    if effect == "impact_flash":
        obj = sphere(raw["effect_id"], p, (0.8, 0.8, 0.8), mats["flash"])
        scale_keys(
            obj,
            [
                (frame - 1, (0.001,) * 3),
                (frame, (1.1 * intensity,) * 3),
                (end, (0.001,) * 3),
            ],
        )
    elif effect == "shockwave":
        bpy.ops.mesh.primitive_torus_add(
            major_radius=1, minor_radius=0.035, location=p, rotation=(math.pi / 2, 0, 0)
        )
        obj = bpy.context.object
        obj.name = raw["effect_id"]
        obj.data.materials.append(mats["flash"])
        scale_keys(
            obj,
            [
                (frame - 1, (0.01,) * 3),
                (frame, (0.15,) * 3),
                (end, (4 * intensity,) * 3),
                (end + 1, (0.001,) * 3),
            ],
        )
    elif effect in {"speed_trails", "motion_streaks", "energy_trail"}:
        for i in range(12):
            offset = Vector(
                (rng.uniform(-2, 1), rng.uniform(-1.7, 1.7), rng.uniform(-1, 1))
            )
            obj = cube(
                f"{raw['effect_id']}_{i}",
                p + offset,
                (rng.uniform(0.7, 1.8), 0.018, 0.018),
                mats["trail"],
                0,
            )
            scale_keys(
                obj,
                [
                    (frame - 1, (0.001,) * 3),
                    (frame + i % 4, (1, 1, 1)),
                    (end - i % 7, (1, 1, 1)),
                    (end + 1, (0.001,) * 3),
                ],
            )
    elif effect in {"debris", "wall_fracture"}:
        for i in range(14 if effect == "debris" else 8):
            start = p + Vector(
                (rng.uniform(-0.3, 0.3), rng.uniform(-0.7, 0.7), rng.uniform(-0.4, 0.8))
            )
            obj = cube(
                f"{raw['effect_id']}_{i}",
                start,
                (rng.uniform(0.05, 0.18),) * 3,
                mats["wall"],
                0.01,
            )
            if effect == "wall_fracture":
                scale_keys(
                    obj,
                    [(frame - 1, (0.001,) * 3), (frame, (1, 1, 1)), (end, (1, 1, 1))],
                )
            else:
                scale_keys(
                    obj,
                    [(frame - 1, (0.001,) * 3), (frame, (1, 1, 1)), (end, (1, 1, 1))],
                )
            obj.keyframe_insert("location", frame=frame)
            if effect == "debris":
                obj.location += Vector(
                    (-rng.uniform(0.3, 2), rng.uniform(-1, 1), rng.uniform(0.2, 2))
                )
                obj.rotation_euler = (
                    rng.random() * 4,
                    rng.random() * 4,
                    rng.random() * 4,
                )
                obj.keyframe_insert("location", frame=end)
                obj.keyframe_insert("rotation_euler", frame=end)
    elif effect in {"dust", "smoke"}:
        for i in range(10):
            obj = sphere(
                f"{raw['effect_id']}_{i}",
                p + Vector((rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8), 0.1)),
                (0.25, 0.25, 0.12),
                mats["dust"],
            )
            scale_keys(
                obj,
                [
                    (frame - 1, (0.001,) * 3),
                    (frame + i, (0.2,) * 3),
                    (end, (1.2 + rng.random(),) * 3),
                    (end + 1, (0.001,) * 3),
                ],
            )


def lighting():
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.006, 0.012, 0.025)
    for name, kind, location, energy, color, size in (
        ("Key", "AREA", (-3, -3, 7), 1300, (0.35, 0.6, 1), 5),
        ("Rim", "AREA", (4, 3, 5), 1700, (1, 0.16, 0.05), 4),
        ("Moon", "SUN", (0, 0, 8), 3.0, (0.25, 0.4, 1), 1),
    ):
        data = bpy.data.lights.new(name, kind)
        data.energy, data.color = energy, color
        if kind == "AREA":
            data.shape, data.size = "DISK", size
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (math.radians(20), 0, math.radians(30))


def compositor():
    scene = bpy.context.scene
    scene.use_nodes = True
    nodes = scene.node_tree.nodes
    links = scene.node_tree.links
    nodes.clear()
    render = nodes.new("CompositorNodeRLayers")
    glare = nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "HIGH"
    glare.threshold = 1
    glare.size = 6
    output = nodes.new("CompositorNodeComposite")
    links.new(render.outputs["Image"], glare.inputs["Image"])
    links.new(glare.outputs["Image"], output.inputs["Image"])


def configure(plan, mode, output):
    scene = bpy.context.scene
    settings = plan["settings"]
    scene.frame_start = 1
    scene.frame_end = round(settings["duration_seconds"] * settings["fps"])
    scene.render.fps = settings["fps"]
    scene.render.resolution_percentage = 100
    prefix = "preview" if mode == "preview" else "final"
    scene.render.resolution_x = settings[prefix + "_width"]
    scene.render.resolution_y = settings[prefix + "_height"]
    if mode == "preview":
        # Workbench is intentionally fast: it validates camera cuts, staging, rigs,
        # timing and VFX placement in seconds rather than using final-look shading.
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.display.shading.light = "STUDIO"
        scene.display.shading.studio_light = "rim.sl"
        scene.display.shading.color_type = "MATERIAL"
        scene.display.shading.show_shadows = True
        scene.display.shading.show_cavity = True
        scene.display.shading.cavity_type = "WORLD"
        scene.use_nodes = False
    else:
        try:
            scene.render.engine = "BLENDER_EEVEE_NEXT"
        except TypeError:
            scene.render.engine = "BLENDER_EEVEE"
        if hasattr(scene, "eevee"):
            scene.eevee.taa_render_samples = settings[prefix + "_samples"]
        if hasattr(scene.render, "use_motion_blur"):
            scene.render.use_motion_blur = settings["motion_blur"]
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM" if mode == "preview" else "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "REALTIME" if mode == "preview" else "GOOD"
    scene.render.filepath = str(Path(output).with_suffix(""))
    scene.render.film_transparent = False
    scene.view_settings.look = "AgX - Medium High Contrast"


def build(plan, mode, output):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = random.Random(plan["random_seed"])
    mats = {
        "ground": material(
            "Ground", (0.025, 0.035, 0.055), metallic=0.12, roughness=0.4
        ),
        "wall": material("Concrete", (0.12, 0.14, 0.18), roughness=0.82),
        "building": material(
            "Buildings", (0.025, 0.05, 0.09), metallic=0.15, roughness=0.45
        ),
        "accent": material(
            "Perspective",
            (0.05, 0.32, 0.5),
            metallic=0.25,
            roughness=0.3,
            emission=(0.01, 0.08, 0.15),
        ),
        "flash": material(
            "ImpactEmission", (1, 0.55, 0.08), roughness=0.1, emission=(1, 0.28, 0.03)
        ),
        "trail": material(
            "SpeedEmission", (0.12, 0.65, 1), roughness=0.15, emission=(0.05, 0.35, 1)
        ),
        "dust": material("Dust", (0.3, 0.25, 0.19), roughness=1),
    }
    create_arena(mats, rng)
    bindings = plan["characters"]
    first_positions = {}
    for raw in plan["instructions"]:
        first_positions.setdefault(raw["actor"], vec(raw["start_position"]))
    rigs = {
        key: create_rig(key, binding["color"], first_positions[key])
        for key, binding in bindings.items()
    }
    hybrid = plan.get("schema_version", 1) >= 3
    library = (
        build_action_library(
            rigs["fighter_a"]["rig"], plan.get("required_animation_clips", [])
        )
        if hybrid
        else {}
    )
    character_libraries = {key: dict(library) for key in rigs}
    if hybrid:
        from character_assets import load_package_animation_overrides

        for key, character in bindings.items():
            package_path = character.get("character_package")
            if not package_path:
                continue
            package_path = Path(package_path)
            if not package_path.is_absolute():
                package_path = Path(plan["_project_directory"]) / package_path
            character_libraries[key].update(
                load_package_animation_overrides(package_path, rigs[key]["rig"])
            )
    for raw in plan["instructions"]:
        facing = -math.pi / 2 if raw["actor"] == "fighter_a" else math.pi / 2
        if hybrid:
            adapter = plan["rig_adapters"][raw["actor"]]["standard_to_target"]
            apply_hybrid_instruction(
                rigs[raw["actor"]],
                raw,
                facing,
                adapter,
                character_libraries[raw["actor"]],
            )
        else:
            apply_instruction(rigs[raw["actor"]], raw, facing)
    package_bindings = {}
    for key, character in bindings.items():
        package_path = character.get("character_package")
        if not package_path:
            continue
        from character_assets import import_character_model, retarget_package_to_source

        package_path = Path(package_path)
        if not package_path.is_absolute():
            package_path = Path(plan["_project_directory"]) / package_path
        imported = import_character_model(package_path, character_id=key)
        package_bindings[key] = retarget_package_to_source(
            imported,
            rigs[key]["rig"],
            source_body=rigs[key]["body"],
        )
    create_cameras(plan)
    for raw in plan["effects"]:
        create_effect(raw, mats, rng)
    lighting()
    if mode != "preview":
        compositor()
    configure(plan, mode, output)
    bpy.context.scene["wws_source_checksum"] = plan["source_checksum"]
    bpy.context.scene["wws_source_outcome_digest"] = plan["source_outcome_digest"]
    bpy.context.scene["wws_plan_id"] = plan["plan_id"]
    bpy.context.scene["wws_animation_mode"] = (
        "authored_actions_nla_hybrid" if hybrid else "procedural_pose_fallback"
    )
    if hybrid:
        bpy.context.scene["wws_action_library_version"] = plan["action_library_version"]
    if package_bindings:
        bpy.context.scene["wws_character_packages"] = json.dumps(
            {
                key: binding["manifest"]["character_id"]
                for key, binding in package_bindings.items()
            },
            sort_keys=True,
        )


def main():
    global bpy, Vector
    import bpy as _bpy
    from mathutils import Vector as _Vector

    bpy, Vector = _bpy, _Vector
    try:
        divider = sys.argv.index("--")
        plan_path, blend_path, mode, output, operation = sys.argv[
            divider + 1 : divider + 6
        ]
    except (ValueError, IndexError):
        raise SystemExit(
            "Expected -- PLAN_JSON BLEND_FILE preview|final VIDEO render|scene-only"
        )
    if mode not in {"preview", "final"} or operation not in {"render", "scene-only"}:
        raise SystemExit("Invalid Blender render mode/operation")
    plan = json.loads(Path(plan_path).read_text())
    plan["_project_directory"] = str(Path(plan_path).resolve().parent)
    build(plan, mode, output)
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(blend_path)), check_existing=False)
    if operation == "render":
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
