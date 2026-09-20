"""Reusable presentation helpers for the athletic male humanoid foundation.

The helpers operate only inside Blender and preserve the standard WWS rig contract.
They refine an existing skinned mesh and add medium-shot hand silhouettes without
changing simulation data or requiring character-specific bone names outside the
caller-provided adapter mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


HAND_POSES = {
    "OPEN_PALM": {"length": 1.0, "spread": 1.0, "forward": 0.18, "drop": 0.0},
    "CLOSED_FIST": {"length": 0.52, "spread": 0.52, "forward": 0.085, "drop": -0.045},
    "RELAXED": {"length": 0.82, "spread": 0.78, "forward": 0.145, "drop": -0.018},
    "CUPPED": {"length": 0.72, "spread": 0.82, "forward": 0.125, "drop": -0.032},
}


@dataclass
class HandControls:
    root: Any
    palm: Any
    fingers: list[Any]
    thumb: Any


def refine_athletic_body(body: Any) -> None:
    """Apply a conservative athletic proportion pass to a reusable body mesh."""
    if body.get("wws_athletic_base_revision") == 1:
        return
    for vertex in body.data.vertices:
        x, y, z = vertex.co
        lateral = abs(y)
        # Broader clavicle/chest mass while preserving the authored arm span.
        if 1.72 <= z <= 2.30 and lateral < 0.62:
            weight = 1.0 - min(1.0, abs(z - 2.02) / 0.34)
            vertex.co.y *= 1.0 + 0.085 * weight
            vertex.co.x = 0.05 + (x - 0.05) * (1.0 + 0.055 * weight)
        # Mild taper through the waist; avoids a block-shaped torso.
        if 1.02 <= z <= 1.62 and lateral < 0.46:
            weight = 1.0 - min(1.0, abs(z - 1.32) / 0.31)
            vertex.co.y *= 1.0 - 0.05 * weight
            vertex.co.x = 0.05 + (vertex.co.x - 0.05) * (1.0 - 0.025 * weight)
        # Slightly fuller thighs/calves improve silhouettes without bodybuilder mass.
        if 0.22 <= z <= 1.12 and lateral < 0.48:
            weight = 1.0 - min(1.0, abs(z - 0.78) / 0.58)
            vertex.co.x = 0.05 + (vertex.co.x - 0.05) * (1.0 + 0.035 * weight)
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    if not any(mod.type == "CORRECTIVE_SMOOTH" for mod in body.modifiers):
        modifier = body.modifiers.new("WWS joint corrective smoothing", "CORRECTIVE_SMOOTH")
        modifier.factor = 0.22
        modifier.iterations = 2
        modifier.smooth_type = "LENGTH_WEIGHTED"
        modifier.use_pin_boundary = True
    body["wws_athletic_base_revision"] = 1


def _link_only(obj: Any, collection: Any) -> None:
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    collection.objects.link(obj)


def _make_ellipsoid(bpy: Any, name: str, scale: tuple[float, float, float], material: Any, collection: Any) -> Any:
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    _link_only(obj, collection)
    return obj


def create_hand_controls(
    bpy: Any,
    rig: Any,
    bone_name: str,
    prefix: str,
    material: Any,
    collection: Any,
) -> HandControls:
    """Create a small reusable palm/finger silhouette rig on a mapped hand bone."""
    bone = rig.pose.bones[bone_name]
    root = bpy.data.objects.new(f"{prefix}_HandControl", None)
    collection.objects.link(root)
    root.matrix_world = rig.matrix_world @ bone.matrix
    world = root.matrix_world.copy()
    root.parent = rig
    root.parent_type = "BONE"
    root.parent_bone = bone_name
    root.matrix_world = world
    root["wws_hand_contract"] = "OPEN_PALM|CLOSED_FIST|RELAXED|CUPPED"

    palm = _make_ellipsoid(bpy, f"{prefix}_Palm", (0.105, 0.125, 0.055), material, collection)
    palm.parent = root
    palm.location = (0, 0.055, 0)
    fingers = []
    for index, x in enumerate((-0.072, -0.024, 0.024, 0.072)):
        finger = _make_ellipsoid(bpy, f"{prefix}_Finger_{index}", (0.024, 0.105 - index * 0.004, 0.024), material, collection)
        finger.parent = root
        finger["wws_finger_index"] = index
        fingers.append(finger)
    thumb = _make_ellipsoid(bpy, f"{prefix}_Thumb", (0.030, 0.075, 0.028), material, collection)
    thumb.parent = root
    thumb["wws_finger_index"] = 4
    controls = HandControls(root=root, palm=palm, fingers=fingers, thumb=thumb)
    set_hand_pose(controls, "RELAXED")
    return controls


def set_hand_pose(controls: HandControls, pose_name: str, frame: int | None = None) -> None:
    pose = HAND_POSES[pose_name]
    for index, finger in enumerate(controls.fingers):
        base_x = (-0.072, -0.024, 0.024, 0.072)[index]
        finger.location = (base_x * pose["spread"], pose["forward"], pose["drop"] - abs(base_x) * 0.08)
        finger.scale = (1.0, pose["length"], 1.0)
    controls.thumb.location = (0.105 * pose["spread"], pose["forward"] * 0.58, pose["drop"] - 0.018)
    controls.thumb.scale = (1.0, pose["length"] * 0.82, 1.0)
    controls.palm.scale = (1.0, 0.94 if pose_name == "CLOSED_FIST" else 1.0, 1.0)
    controls.root["wws_hand_pose"] = pose_name
    if frame is not None:
        for obj in [controls.palm, *controls.fingers, controls.thumb]:
            obj.keyframe_insert("location", frame=frame)
            obj.keyframe_insert("scale", frame=frame)

