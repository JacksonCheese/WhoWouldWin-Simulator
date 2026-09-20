"""Non-destructive cleanup controls for imported humanoid performances.

These controls are created inactive.  They give an animator stable poles,
wrist/shoulder orientation and foot-roll pivots after retargeting without
changing an approved source performance during import.
"""
from __future__ import annotations

import json


def _control(bpy, collection, name, location, *, size=0.12, display="CUBE"):
    obj = bpy.data.objects.new(name, None)
    collection.objects.link(obj)
    obj.location = location
    obj.empty_display_type = display
    obj.empty_display_size = size
    obj.show_in_front = True
    return obj


def _world_point(rig, bone_name, fraction=0.5):
    bone = rig.pose.bones[bone_name]
    return rig.matrix_world @ bone.head.lerp(bone.tail, fraction)


def create_cleanup_controls(bpy, rig, *, prefix: str, collection):
    """Create a reusable, inactive animation-cleanup layer for one rig."""
    controls = {}
    for side in ("L", "R"):
        upper = _world_point(rig, f"UpperArm_{side}", .55)
        elbow = _world_point(rig, f"LowerArm_{side}", 0)
        wrist = _world_point(rig, f"Hand_{side}", .2)
        shoulder = _world_point(rig, f"Shoulder_{side}", .55)
        foot_head = _world_point(rig, f"Foot_{side}", 0)
        foot_tail = _world_point(rig, f"Foot_{side}", 1)
        lateral = upper - elbow
        lateral.z = 0
        if lateral.length < 1e-5:
            from mathutils import Vector
            lateral = Vector((0, -1 if side == "L" else 1, 0))
        lateral.normalize()
        controls[f"scapula.{side}"] = _control(bpy, collection, f"{prefix}_Scapula_{side}", shoulder, size=.14, display="CIRCLE")
        controls[f"elbow_pole.{side}"] = _control(bpy, collection, f"{prefix}_ElbowPole_{side}", elbow + lateral * .75, size=.11, display="SPHERE")
        controls[f"wrist_control.{side}"] = _control(bpy, collection, f"{prefix}_Wrist_{side}", wrist, size=.10, display="CUBE")
        heel = _control(bpy, collection, f"{prefix}_Heel_{side}", foot_head, size=.09, display="CIRCLE")
        ball = _control(bpy, collection, f"{prefix}_Ball_{side}", foot_head.lerp(foot_tail, .55), size=.08, display="CIRCLE")
        toe = _control(bpy, collection, f"{prefix}_Toe_{side}", foot_tail, size=.07, display="CIRCLE")
        ball.parent = heel
        toe.parent = ball
        controls[f"heel.{side}"] = heel
        controls[f"ball.{side}"] = ball
        controls[f"toe.{side}"] = toe

        forearm = rig.pose.bones[f"LowerArm_{side}"]
        arm_ik = forearm.constraints.new("IK")
        arm_ik.name = f"WWS cleanup arm IK {side}"
        arm_ik.target = controls[f"wrist_control.{side}"]
        arm_ik.pole_target = controls[f"elbow_pole.{side}"]
        arm_ik.chain_count = 2
        arm_ik.use_stretch = False
        arm_ik.influence = 0.0
        wrist_orient = rig.pose.bones[f"Hand_{side}"].constraints.new("COPY_ROTATION")
        wrist_orient.name = f"WWS cleanup wrist orientation {side}"
        wrist_orient.target = controls[f"wrist_control.{side}"]
        wrist_orient.influence = 0.0
        shoulder_orient = rig.pose.bones[f"Shoulder_{side}"].constraints.new("COPY_ROTATION")
        shoulder_orient.name = f"WWS cleanup scapula orientation {side}"
        shoulder_orient.target = controls[f"scapula.{side}"]
        shoulder_orient.influence = 0.0
        leg_ik = rig.pose.bones[f"LowerLeg_{side}"].constraints.new("IK")
        leg_ik.name = f"WWS cleanup planted foot {side}"
        leg_ik.target = heel
        leg_ik.chain_count = 2
        leg_ik.use_stretch = False
        leg_ik.influence = 0.0
        sole = rig.pose.bones[f"Foot_{side}"].constraints.new("COPY_ROTATION")
        sole.name = f"WWS cleanup foot orientation {side}"
        sole.target = ball
        sole.influence = 0.0

    # Twist is explicitly a supported adapter channel.  The current rig lacks
    # deforming twist bones, so controls are provided without claiming a
    # deformation upgrade that the mesh does not possess.
    for side in ("L", "R"):
        controls[f"forearm_twist.{side}"] = _control(
            bpy, collection, f"{prefix}_ForearmTwist_{side}",
            _world_point(rig, f"LowerArm_{side}", .5), size=.08, display="ARROWS",
        )
        twist = rig.pose.bones[f"LowerArm_{side}"].constraints.new("COPY_ROTATION")
        twist.name = f"WWS cleanup forearm twist {side}"
        twist.target = controls[f"forearm_twist.{side}"]
        twist.use_x = True
        twist.use_y = False
        twist.use_z = False
        twist.mix_mode = "ADD"
        twist.influence = 0.0
    mapping = {role: control.name for role, control in controls.items()}
    rig["wws_cleanup_control_map"] = json.dumps(mapping, sort_keys=True)
    rig["wws_cleanup_controls_active"] = False
    rig["wws_twist_support"] = "adapter channel/control present; deforming twist bone required from production asset"
    return mapping
