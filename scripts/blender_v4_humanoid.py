"""Replace the V3 Astra mannequin with a continuous Blender-native humanoid.

Run from the repository root:

    blender --background outputs/blender_combat_v3_astra/scene.blend \
      --python-exit-code 1 --python scripts/blender_v4_humanoid.py -- --render

The script edits presentation assets only. It preserves the source-event checksum,
outcome digest, NLA action library, root trajectories, cameras, and IK architecture.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/blender_combat_v4_humanoid"
SCENE = bpy.context.scene
STANDARD_BONES = (
    "root",
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
)
TARGET_BONES = {
    "root": "MotionRoot",
    "pelvis": "Hips",
    "spine": "SpineLower",
    "chest": "SpineUpper",
    "neck": "Neck",
    "head": "Head",
    "clavicle.L": "Shoulder_L",
    "clavicle.R": "Shoulder_R",
    "upper_arm.L": "UpperArm_L",
    "upper_arm.R": "UpperArm_R",
    "forearm.L": "LowerArm_L",
    "forearm.R": "LowerArm_R",
    "hand.L": "Hand_L",
    "hand.R": "Hand_R",
    "thigh.L": "UpperLeg_L",
    "thigh.R": "UpperLeg_R",
    "shin.L": "LowerLeg_L",
    "shin.R": "LowerLeg_R",
    "foot.L": "Foot_L",
    "foot.R": "Foot_R",
}
RIG_LAYOUT = {
    "root": ((0, 0, 0), (0, 0, 0.36), None),
    "pelvis": ((0, 0, 1.28), (0, 0, 1.56), "root"),
    "spine": ((0, 0, 1.56), (0, 0, 1.86), "pelvis"),
    "chest": ((0, 0, 1.86), (0, 0, 2.14), "spine"),
    "neck": ((0, 0, 2.14), (0, 0, 2.30), "chest"),
    "head": ((0, 0, 2.30), (0, 0, 2.73), "neck"),
    "clavicle.L": ((0, 0.08, 2.08), (0, 0.28, 2.08), "chest"),
    "upper_arm.L": ((0, 0.28, 2.08), (0, 0.67, 1.91), "clavicle.L"),
    "forearm.L": ((0, 0.67, 1.91), (0, 1.07, 1.69), "upper_arm.L"),
    "hand.L": ((0, 1.07, 1.69), (0.02, 1.29, 1.62), "forearm.L"),
    "clavicle.R": ((0, -0.08, 2.08), (0, -0.28, 2.08), "chest"),
    "upper_arm.R": ((0, -0.28, 2.08), (0, -0.67, 1.91), "clavicle.R"),
    "forearm.R": ((0, -0.67, 1.91), (0, -1.07, 1.69), "upper_arm.R"),
    "hand.R": ((0, -1.07, 1.69), (0.02, -1.29, 1.62), "forearm.R"),
    "thigh.L": ((0, 0.18, 1.31), (0, 0.20, 0.72), "pelvis"),
    "shin.L": ((0, 0.20, 0.72), (0, 0.21, 0.16), "thigh.L"),
    "foot.L": ((0, 0.21, 0.16), (0.33, 0.21, 0.09), "shin.L"),
    "thigh.R": ((0, -0.18, 1.31), (0, -0.20, 0.72), "pelvis"),
    "shin.R": ((0, -0.20, 0.72), (0, -0.21, 0.16), "thigh.R"),
    "foot.R": ((0, -0.21, 0.16), (0.33, -0.21, 0.09), "shin.R"),
}
BONE_RADII = {
    "pelvis": 0.31,
    "spine": 0.32,
    "chest": 0.38,
    "neck": 0.15,
    "head": 0.27,
    "clavicle.L": 0.20,
    "clavicle.R": 0.20,
    "upper_arm.L": 0.15,
    "upper_arm.R": 0.15,
    "forearm.L": 0.12,
    "forearm.R": 0.12,
    "hand.L": 0.13,
    "hand.R": 0.13,
    "thigh.L": 0.20,
    "thigh.R": 0.20,
    "shin.L": 0.15,
    "shin.R": 0.15,
    "foot.L": 0.14,
    "foot.R": 0.14,
}


def evaluate(frame: int) -> None:
    SCENE.frame_set(frame)
    bpy.context.view_layer.update()


def action_curve(action, path: str, axis: int):
    return action.fcurves.find(path, index=axis) or action.fcurves.new(path, index=axis)


def replace_keys(action, path: str, axis: int, values) -> None:
    curve = action_curve(action, path, axis)
    curve.keyframe_points.clear()
    for frame, value in values:
        key = curve.keyframe_points.insert(frame, value)
        key.interpolation = "BEZIER"
        key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"
    curve.update()


def strip(rig, name: str):
    return next(
        item
        for track in rig.animation_data.nla_tracks
        for item in track.strips
        if name in item.name
    )


def drive_constraint_influence(constraint, source, source_path: str) -> None:
    """Mirror source-rig IK timing without creating a second timing authority."""
    constraint.influence = 0.0
    driver = constraint.driver_add("influence").driver
    driver.type = "SCRIPTED"
    variable = driver.variables.new()
    variable.name = "source_influence"
    variable.type = "SINGLE_PROP"
    variable.targets[0].id = source
    variable.targets[0].data_path = source_path
    driver.expression = "source_influence"


def create_target_rig(source, fighter: str):
    """Create an asset-named skeleton driven only through the standard adapter."""
    armature = bpy.data.armatures.new(fighter + "_ProductionArmatureData")
    target = bpy.data.objects.new(fighter + "_ProductionRig", armature)
    bpy.context.collection.objects.link(target)
    target.show_in_front = True
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.mode_set(mode="EDIT")
    created = {}
    for standard, (head, tail, parent) in RIG_LAYOUT.items():
        bone = armature.edit_bones.new(TARGET_BONES[standard])
        bone.head = head
        bone.tail = tail
        bone.use_connect = False
        bone.parent = created[parent] if parent else None
        created[standard] = bone
    bpy.ops.object.mode_set(mode="OBJECT")

    trajectory = target.constraints.new("COPY_TRANSFORMS")
    trajectory.name = "Adapter world trajectory"
    trajectory.target = source
    trajectory.owner_space = "WORLD"
    trajectory.target_space = "WORLD"
    target.animation_data_create()
    target.animation_data.action = bpy.data.actions.new(fighter + "_AdapterTimeline")

    for standard, target_name in TARGET_BONES.items():
        bone = target.pose.bones[target_name]
        bone.rotation_mode = "XYZ"
        rotation = bone.constraints.new("COPY_ROTATION")
        rotation.name = "Retarget " + standard
        rotation.target = source
        rotation.subtarget = standard
        rotation.owner_space = "WORLD"
        rotation.target_space = "WORLD"
        rotation.mix_mode = "REPLACE"

    for standard, control_name, source_constraint in (
        ("forearm.R", "fighter_b_IK_hand.R", "Procedural contact hand.R"),
        ("foot.L", fighter + "_IK_foot.L", "Procedural contact foot.L"),
        ("foot.R", fighter + "_IK_foot.R", "Procedural contact foot.R"),
    ):
        if standard == "forearm.R" and fighter != "fighter_b":
            continue
        target_name = TARGET_BONES[standard]
        constraint = target.pose.bones[target_name].constraints.new("IK")
        constraint.name = "Adapter IK " + standard
        constraint.target = bpy.data.objects[control_name]
        constraint.chain_count = 2
        constraint.use_tail = True
        target.pose.bones[target_name].ik_stretch = 0.03
        source_path = (
            f'pose.bones["{standard}"].constraints["{source_constraint}"].influence'
        )
        drive_constraint_influence(constraint, source, source_path)

    target["wws_rig_contract"] = "standard_humanoid_v1"
    target["wws_rig_adapter"] = "blender_native_continuous_v1"
    target["wws_source_rig"] = source.name
    target["wws_standard_to_target"] = json.dumps(TARGET_BONES, sort_keys=True)
    return target


def add_ball(metaball, point, radius: float, stiffness: float = 2.0) -> None:
    element = metaball.elements.new(type="BALL")
    element.co = point
    element.radius = radius
    element.stiffness = stiffness


def sample_segment(
    metaball, start, end, radius_start: float, radius_end: float, count: int
) -> None:
    a, b = Vector(start), Vector(end)
    for index in range(count):
        t = index / max(1, count - 1)
        radius = radius_start * (1 - t) + radius_end * t
        add_ball(metaball, a.lerp(b, t), radius)


def body_field(name: str):
    """Create a single connected implicit body in the rig's local rest space."""
    data = bpy.data.metaballs.new(name + "_ImplicitData")
    data.resolution = 0.055
    data.render_resolution = 0.035
    data.threshold = 0.62
    obj = bpy.data.objects.new(name + "_Implicit", data)
    bpy.context.collection.objects.link(obj)

    # Pelvis, abdomen, rib cage, neck, and head form a continuous central mass.
    for point, radius in (
        ((0, 0, 1.30), 0.30),
        ((0.01, 0, 1.47), 0.30),
        ((0.015, 0, 1.64), 0.31),
        ((0.01, 0, 1.82), 0.36),
        ((0, 0, 1.99), 0.39),
        ((0, 0, 2.12), 0.32),
        ((0, 0, 2.24), 0.145),
        ((0, 0, 2.40), 0.235),
        ((0, 0, 2.58), 0.275),
        ((0, 0, 2.72), 0.22),
    ):
        add_ball(data, point, radius)
    # Flatten the torso depth and broaden shoulders without disconnected shells.
    for y in (-0.16, 0.16):
        add_ball(data, (0, y, 1.96), 0.29)
        add_ball(data, (0, y, 1.82), 0.27)
    for x in (-0.10, 0.10):
        add_ball(data, (x, 0, 1.88), 0.30)
        add_ball(data, (x, 0, 1.49), 0.24)

    for side, sign in (("L", 1), ("R", -1)):
        shoulder = RIG_LAYOUT[f"upper_arm.{side}"][0]
        elbow = RIG_LAYOUT[f"upper_arm.{side}"][1]
        wrist = RIG_LAYOUT[f"forearm.{side}"][1]
        hand = RIG_LAYOUT[f"hand.{side}"][1]
        sample_segment(data, (0, 0.18 * sign, 2.07), shoulder, 0.20, 0.17, 3)
        sample_segment(data, shoulder, elbow, 0.17, 0.145, 5)
        add_ball(data, elbow, 0.15)
        sample_segment(data, elbow, wrist, 0.135, 0.105, 5)
        sample_segment(data, wrist, hand, 0.13, 0.105, 3)

        hip = RIG_LAYOUT[f"thigh.{side}"][0]
        knee = RIG_LAYOUT[f"thigh.{side}"][1]
        ankle = RIG_LAYOUT[f"shin.{side}"][1]
        toe = RIG_LAYOUT[f"foot.{side}"][1]
        sample_segment(data, (0, 0.08 * sign, 1.36), hip, 0.27, 0.225, 3)
        sample_segment(data, hip, knee, 0.225, 0.17, 7)
        add_ball(data, knee, 0.17)
        sample_segment(data, knee, ankle, 0.155, 0.105, 7)
        add_ball(data, ankle, 0.12)
        sample_segment(data, ankle, toe, 0.14, 0.115, 5)
        add_ball(data, (0.22, 0.21 * sign, 0.10), 0.14)
    return obj


def point_segment_distance(point: Vector, a: Vector, b: Vector) -> float:
    ab = b - a
    if ab.length_squared == 0:
        return (point - a).length
    t = max(0.0, min(1.0, (point - a).dot(ab) / ab.length_squared))
    return (point - a.lerp(b, t)).length


def candidate_bones(co: Vector) -> tuple[str, ...]:
    """Isolate limbs by anatomical region before applying smooth joint blends."""
    if co.z > 2.20 and abs(co.y) < 0.43:
        return ("chest", "neck", "head")
    if co.z > 1.43 and abs(co.y) > 0.34:
        side = "L" if co.y > 0 else "R"
        return (
            "chest",
            f"clavicle.{side}",
            f"upper_arm.{side}",
            f"forearm.{side}",
            f"hand.{side}",
        )
    if co.z < 1.43 and abs(co.y) > 0.06:
        side = "L" if co.y > 0 else "R"
        return (
            "pelvis",
            f"thigh.{side}",
            f"shin.{side}",
            f"foot.{side}",
        )
    return ("pelvis", "spine", "chest", "neck", "thigh.L", "thigh.R")


def smooth_weights(body, rig) -> dict:
    """Assign deterministic distance weights with joint-local blending."""
    groups = {
        name: body.vertex_groups.new(name=TARGET_BONES[name]) for name in STANDARD_BONES
    }
    assignment_count = 0
    max_influences = 0
    minimum_sum = 1.0
    for vertex in body.data.vertices:
        scores = []
        for name in candidate_bones(vertex.co):
            if name == "root":
                continue
            bone = rig.data.bones[TARGET_BONES[name]]
            distance = point_segment_distance(
                vertex.co, bone.head_local, bone.tail_local
            )
            radius = BONE_RADII.get(name, 0.18)
            score = math.exp(-2.2 * (distance / max(0.08, radius)) ** 2)
            scores.append((score, name))
        selected = sorted(scores, reverse=True)[:4]
        total = sum(score for score, _ in selected)
        if total < 1e-9:
            selected = [(1.0, "pelvis")]
            total = 1.0
        normalized = [
            (score / total, name) for score, name in selected if score / total > 0.01
        ]
        renormalize = sum(weight for weight, _ in normalized)
        for weight, name in normalized:
            groups[name].add([vertex.index], weight / renormalize, "REPLACE")
            assignment_count += 1
        max_influences = max(max_influences, len(normalized))
        minimum_sum = min(
            minimum_sum, sum(weight / renormalize for weight, _ in normalized)
        )
    return {
        "assignments": assignment_count,
        "max_influences": max_influences,
        "minimum_weight_sum": minimum_sum,
    }


def convert_body(rig, fighter: str, material) -> tuple[object, dict]:
    implicit = body_field(fighter)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = implicit
    implicit.select_set(True)
    bpy.ops.object.convert(target="MESH")
    body = bpy.context.object
    body.name = fighter + "_ProductionBody"
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    body.data.materials.append(material)
    body.parent = rig
    body.matrix_parent_inverse = Matrix.Identity(4)
    body.location = (0, 0, 0)
    body.rotation_euler = (0, 0, 0)
    body.scale = (1, 1, 1)
    weights = smooth_weights(body, rig)
    armature = body.modifiers.new("Production armature deformation", "ARMATURE")
    armature.object = rig
    armature.use_deform_preserve_volume = True
    smooth = body.modifiers.new("Joint corrective smoothing", "CORRECTIVE_SMOOTH")
    smooth.factor = 0.22
    smooth.iterations = 3
    smooth.scale = 0.7
    body["wws_body_version"] = "blender_native_continuous_v1"
    body["wws_topology"] = "single_connected_implicit_surface"
    body["wws_weighting"] = "deterministic_anatomical_distance_blend"
    return body, weights


def make_material(name: str, color) -> object:
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = 0.72
    return material


def retarget_foot_controls(rig) -> None:
    prefix = rig.name.removesuffix("_Rig")
    for side in ("L", "R"):
        control = bpy.data.objects[f"{prefix}_IK_foot.{side}"]
        action = control.animation_data.action
        z_curve = action.fcurves.find("location", index=2)
        if z_curve:
            for key in z_curve.keyframe_points:
                if key.co.y < 0.20:
                    key.co.y += 0.11
            z_curve.update()
        constraint = rig.pose.bones[f"shin.{side}"].constraints[
            f"Procedural contact foot.{side}"
        ]
        constraint.chain_count = 2
        rig.pose.bones[f"shin.{side}"].ik_stretch = 0.03


def improve_weight_transfer(rig_b, rig_a) -> None:
    """Add leg loading and foot roll to the already retargeted heavy cross."""
    heavy = strip(rig_b, "heavy_cross").action
    for bone, axis, values in (
        (
            "thigh.L",
            1,
            ((1, 0.08), (8, -0.24), (13, -0.30), (18, 0.08), (26, 0.14), (32, 0.05)),
        ),
        (
            "shin.L",
            1,
            ((1, -0.06), (8, 0.30), (13, 0.38), (18, 0.13), (26, 0.02), (32, -0.04)),
        ),
        (
            "thigh.R",
            1,
            ((1, -0.04), (8, 0.18), (13, 0.24), (18, -0.16), (26, -0.10), (32, 0)),
        ),
        (
            "shin.R",
            1,
            ((1, 0.04), (8, -0.12), (13, -0.18), (18, 0.20), (26, 0.12), (32, 0)),
        ),
        (
            "foot.R",
            1,
            (
                (1, 0),
                (8, -0.08),
                (13, -0.12),
                (18, 0.34),
                (21, 0.26),
                (26, 0.06),
                (32, 0),
            ),
        ),
        ("foot.L", 1, ((1, 0), (8, 0.08), (13, 0.12), (18, -0.06), (26, 0), (32, 0))),
    ):
        replace_keys(heavy, f'pose.bones["{bone}"].rotation_euler', axis, values)

    landing = strip(rig_a, "hard_landing").action
    for bone, axis, values in (
        (
            "thigh.L",
            1,
            (
                (1, -0.12),
                (10, -0.35),
                (15, -0.70),
                (18, -0.78),
                (22, -0.55),
                (27, -0.28),
                (32, -0.08),
            ),
        ),
        (
            "thigh.R",
            1,
            (
                (1, -0.08),
                (10, -0.30),
                (15, -0.62),
                (18, -0.72),
                (22, -0.48),
                (27, -0.22),
                (32, -0.06),
            ),
        ),
        (
            "shin.L",
            1,
            (
                (1, 0.12),
                (10, 0.35),
                (15, 0.78),
                (18, 0.88),
                (22, 0.68),
                (27, 0.38),
                (32, 0.10),
            ),
        ),
        (
            "shin.R",
            1,
            (
                (1, 0.10),
                (10, 0.30),
                (15, 0.70),
                (18, 0.80),
                (22, 0.60),
                (27, 0.32),
                (32, 0.08),
            ),
        ),
        (
            "foot.L",
            1,
            ((1, 0), (10, -0.12), (15, 0.18), (18, 0.26), (22, 0.10), (27, 0), (32, 0)),
        ),
        (
            "foot.R",
            1,
            ((1, 0), (10, -0.08), (15, 0.16), (18, 0.22), (22, 0.08), (27, 0), (32, 0)),
        ),
    ):
        replace_keys(landing, f'pose.bones["{bone}"].rotation_euler', axis, values)


def evaluated_world(rig, bone: str, tail: bool = False) -> Vector:
    evaluated = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    pose_bone = evaluated.pose.bones[bone]
    return evaluated.matrix_world @ (pose_bone.tail if tail else pose_bone.head)


def nearest_surface(body, query: Vector) -> Vector:
    evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    tree = BVHTree.FromPolygons(
        vertices, [list(poly.vertices) for poly in mesh.polygons]
    )
    result = tree.find_nearest(query)
    evaluated.to_mesh_clear()
    if result is None:
        raise RuntimeError("Unable to find production-body contact surface")
    return result[0]


def retarget_contact(rig_a, body_a, rig_b) -> Vector:
    """Move the existing contact correction onto the new evaluated torso surface."""
    evaluate(163)
    intent = evaluated_world(rig_a, TARGET_BONES["spine"]).lerp(
        evaluated_world(rig_a, TARGET_BONES["chest"]), 0.74
    )
    intent += Vector((0.12, -0.10, 0.0))
    target = nearest_surface(body_a, intent)
    control = bpy.data.objects["fighter_b_IK_hand.R"]
    evaluate(158)
    rest = evaluated_world(rig_b, TARGET_BONES["forearm.R"], tail=True)
    action = control.animation_data.action
    for axis in range(3):
        replace_keys(
            action,
            "location",
            axis,
            (
                (128, rest[axis]),
                (158, rest[axis]),
                (161, rest.lerp(target, 0.55)[axis]),
                (163, target[axis]),
                (165, target[axis]),
                (169, (target + Vector((-0.18, 0.03, 0.02)))[axis]),
                (176, rest[axis]),
            ),
        )
    evaluate(163)
    return target


def create_static_camera() -> object:
    data = bpy.data.cameras.new("V4_StaticMotionReview_Data")
    camera = bpy.data.objects.new("V4_StaticMotionReview", data)
    bpy.context.collection.objects.link(camera)
    # This oblique position compresses the 11 m launch path without turning the
    # review into a side-on game camera. It stays fixed for the entire take.
    camera.location = (-8.0, -12.0, 4.5)
    target = Vector((0.45, 0.0, 1.60))
    camera.rotation_euler = (
        (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    )
    data.lens = 38
    data.sensor_fit = "HORIZONTAL"
    data.clip_start = 0.05
    camera["wws_review_camera"] = "static_three_quarter_no_vfx"
    return camera


def suspend_vfx() -> list[tuple[object, bool, list[tuple[object, bool]]]]:
    """Hide presentation VFX even when their visibility is animation-driven."""
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


def save_markers():
    markers = [
        (marker.name, marker.frame, marker.camera) for marker in SCENE.timeline_markers
    ]
    for marker in list(SCENE.timeline_markers):
        SCENE.timeline_markers.remove(marker)
    return markers


def restore_markers(markers) -> None:
    for name, frame, camera in markers:
        marker = SCENE.timeline_markers.new(name, frame=frame)
        marker.camera = camera


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


def write_adapter(weights: dict, bodies: dict) -> None:
    adapter = {
        "adapter_id": "blender_native_continuous_v1",
        "standard_to_target": TARGET_BONES,
        "asset_specific_names_exposed_to_combat": False,
        "mesh": {
            fighter: {
                "object": body.name,
                "vertices": len(body.data.vertices),
                "polygons": len(body.data.polygons),
                "weights": weights[fighter],
            }
            for fighter, body in bodies.items()
        },
        "notes": "Blender-native evaluation body. No external or copyrighted asset used.",
    }
    (OUTPUT / "review/rig_adapter.json").write_text(json.dumps(adapter, indent=2))


def main() -> None:
    render = "--render" in sys.argv
    (OUTPUT / "review").mkdir(parents=True, exist_ok=True)
    (OUTPUT / "renders/preview").mkdir(parents=True, exist_ok=True)
    evaluate(1)
    source_rigs = {
        fighter: bpy.data.objects[f"{fighter}_Rig"]
        for fighter in ("fighter_a", "fighter_b")
    }
    for rig in source_rigs.values():
        retarget_foot_controls(rig)
    rigs = {
        fighter: create_target_rig(source_rigs[fighter], fighter)
        for fighter in ("fighter_a", "fighter_b")
    }

    for old_name in ("fighter_a_SkinnedBody", "fighter_b_SkinnedBody"):
        old = bpy.data.objects[old_name]
        old.hide_viewport = True
        old.hide_render = True
        old["wws_replaced_by_v4"] = True

    materials = {
        "fighter_a": make_material("V4_FighterA_Gray", (0.34, 0.36, 0.39)),
        "fighter_b": make_material("V4_FighterB_Gray", (0.52, 0.55, 0.60)),
    }
    bodies = {}
    weight_reports = {}
    for fighter, rig in rigs.items():
        body, report = convert_body(rig, fighter, materials[fighter])
        bodies[fighter] = body
        weight_reports[fighter] = report

    improve_weight_transfer(source_rigs["fighter_b"], source_rigs["fighter_a"])
    contact = retarget_contact(
        rigs["fighter_a"], bodies["fighter_a"], rigs["fighter_b"]
    )
    static_camera = create_static_camera()
    SCENE["wws_humanoid_body"] = "blender_native_continuous_v1"
    SCENE["wws_humanoid_milestone"] = "production_humanoid_retargeting_validation"
    SCENE["wws_v4_contact_target"] = list(contact)
    SCENE.frame_start = 1
    SCENE.frame_end = 360
    SCENE.render.resolution_x = 360
    SCENE.render.resolution_y = 640
    evaluate(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "scene.blend"))
    write_adapter(weight_reports, bodies)

    if render:
        cinematic_camera = SCENE.camera
        render_video(OUTPUT / "renders/preview/fight.mp4", 1, 360, 360, 640)
        markers = save_markers()
        SCENE.camera = static_camera
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
        evaluate(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "scene.blend"))

    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "rendered": render,
                "bodies": {
                    fighter: {
                        "vertices": len(body.data.vertices),
                        "polygons": len(body.data.polygons),
                    }
                    for fighter, body in bodies.items()
                },
                "contact_target": list(contact),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
