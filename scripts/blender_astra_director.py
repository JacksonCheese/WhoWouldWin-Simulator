"""Shot-specific directing pass over the saved V3 scene; no engine changes.

blender -b outputs/blender_combat_v3/scene.blend --python scripts/blender_astra_director.py -- [--render]
Run against V3, never against an already edited Astra scene.
"""

import bpy
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/blender_combat_v3_astra"
SCENE = bpy.context.scene
A = bpy.data.objects["fighter_a_Rig"]
B = bpy.data.objects["fighter_b_Rig"]


def curve(action, path, index=0):
    return action.fcurves.find(path, index=index) or action.fcurves.new(
        path, index=index
    )


def keys(action, path, index, values, interpolation="BEZIER"):
    c = curve(action, path, index)
    c.keyframe_points.clear()
    for f, v in values:
        k = c.keyframe_points.insert(f, v)
        k.interpolation = interpolation
        k.handle_left_type = k.handle_right_type = "AUTO_CLAMPED"
    c.update()
    return c


def bone_curve(action, bone, axis, values):
    return keys(action, f'pose.bones["{bone}"].rotation_euler', axis, values)


def strip(rig, contains):
    return next(
        s for t in rig.animation_data.nla_tracks for s in t.strips if contains in s.name
    )


def warp(s, values):
    s.use_animated_time = True
    for c in list(s.fcurves):
        if c.data_path == "strip_time":
            c.keyframe_points.clear()
    for f, v in values:
        s.strip_time = v
        s.keyframe_insert("strip_time", frame=f)
    for c in s.fcurves:
        if c.data_path == "strip_time":
            for k in c.keyframe_points:
                k.interpolation = "LINEAR"


def root_keys(rig, rows, start=1, end=360):
    act = rig.animation_data.action
    for prop, offset in [("location", 1), ("rotation_euler", 2), ("scale", 3)]:
        for axis in range(3):
            c = curve(act, prop, axis)
            retained = [
                tuple(k.co) for k in c.keyframe_points if not start <= k.co.x <= end
            ]
            c.keyframe_points.clear()
            for f, v in retained:
                c.keyframe_points.insert(f, v)
            for row in rows:
                k = c.keyframe_points.insert(row[0], row[offset][axis])
                k.interpolation = "BEZIER"
                k.handle_left_type = k.handle_right_type = "AUTO_CLAMPED"
            c.update()


def evaluate(f):
    SCENE.frame_set(f)
    bpy.context.view_layer.update()
    return bpy.context.evaluated_depsgraph_get()


def point(rig, bone="chest", tail=False):
    r = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    b = r.pose.bones[bone]
    return r.matrix_world @ (b.tail if tail else b.head)


def animate_guard(action, factor=1.0):
    # Contain the elbows and fold the forearms; retain native timing and arcs.
    for c in action.fcurves:
        for k in c.keyframe_points:
            if "upper_arm" in c.data_path and c.array_index == 0:
                k.co.y = max(-1.15, min(0.6, k.co.y * factor))
            if "upper_arm" in c.data_path and c.array_index == 2:
                k.co.y = max(-1.3, min(1.3, k.co.y))
            k.handle_left_type = k.handle_right_type = "AUTO_CLAMPED"
        c.update()


def direct_arm_pose(rig, action, frame, kind):
    """Author arm arcs onto the existing Action in armature space, preserving lengths."""
    saved = rig.animation_data.action
    use_nla = rig.animation_data.use_nla
    rig.animation_data.use_nla = False
    rig.animation_data.action = action
    rig.animation_data.action_slot = action.slots[0]
    evaluate(frame)
    for side, sign in [("L", 1), ("R", -1)]:
        upper = (0.18, sign * 0.22, -0.43)
        lower = (0.30, -sign * 0.12, 0.43)
        if kind in {"coil", "extend", "follow"} and side == "L":
            upper = (0.25, 0.22, -0.1)
            lower = (0.08, -0.15, 0.5)
        if kind == "coil" and side == "R":
            upper = (-0.18, -0.3, -0.36)
            lower = (0.28, 0.12, 0.43)
        if kind == "extend" and side == "R":
            upper = (0.48, -0.06, -0.17)
            lower = (0.53, 0.08, -0.06)
        if kind == "follow" and side == "R":
            upper = (0.38, 0.30, -0.22)
            lower = (0.42, 0.3, -0.15)
        if kind == "landing":
            upper = (0.25, sign * 0.2, -0.42)
            lower = (0.35, -sign * 0.08, -0.35)
        if kind == "dash":
            upper = (
                (-0.34, sign * 0.18, -0.3)
                if side == "R"
                else (0.38, sign * 0.15, -0.28)
            )
            lower = (
                (-0.15, -sign * 0.1, 0.5) if side == "R" else (0.25, -sign * 0.15, 0.42)
            )
        for name, direction in [
            (f"upper_arm.{side}", upper),
            (f"forearm.{side}", lower),
        ]:
            bone = rig.pose.bones[name]
            rest = bone.bone.matrix_local.to_quaternion()
            rest_dir = bone.bone.tail_local - bone.bone.head_local
            q = rest_dir.rotation_difference(Vector(direction)) @ rest
            mat = q.to_matrix().to_4x4()
            mat.translation = bone.head
            bone.matrix = mat
            bpy.context.view_layer.update()
            bone.keyframe_insert("rotation_euler", frame=frame)
    rig.animation_data.action = saved
    rig.animation_data.use_nla = use_nla


def body_edit():
    for rig in (A, B):
        for b in rig.pose.bones:
            b.rotation_mode = "XYZ"
        for t in rig.animation_data.nla_tracks:
            for s in t.strips:
                animate_guard(s.action, 0.85)
                s.blend_in = min(3, s.blend_in)
                s.blend_out = 0
                s.extrapolation = "HOLD_FORWARD"
    # Remove unanimated bind-pose holes between the clips.
    strip(A, "wall_impact").extrapolation = "HOLD_FORWARD"
    strip(A, "wall_impact").blend_out = 0
    strip(B, "stance_001").extrapolation = "HOLD_FORWARD"
    strip(B, "dodge").extrapolation = "HOLD_FORWARD"
    strip(B, "dodge").blend_out = 0
    strip(B, "stance_001").blend_out = 0
    # Deliberately compressed dash: a coil, a short travel pose, then overshoot.
    warp(strip(A, "dash"), [(55, 1), (75, 6), (81, 7), (87, 9), (92, 18), (100, 26)])
    warp(strip(B, "dodge"), [(73, 1), (82, 6), (87, 10), (92, 14), (108, 21)])
    heavy = strip(B, "heavy_cross")
    heavy.frame_end = 189
    heavy.blend_out = 6
    warp(
        heavy,
        [(128, 1), (143, 8), (158, 13), (163, 18), (165, 18), (174, 26), (189, 32)],
    )
    stance = strip(B, "stance_178")
    stance.frame_start = 183
    stance.blend_in = 6
    act = heavy.action
    # Stagger hip, chest and shoulder reversal over the final five frames.
    bone_curve(
        act,
        "pelvis",
        1,
        [
            (1, 0.08),
            (8, -0.3),
            (12, -0.34),
            (15, 0.22),
            (18, 0.28),
            (21, 0.3),
            (26, 0.12),
            (32, 0.08),
        ],
    )
    bone_curve(
        act,
        "pelvis",
        2,
        [(1, 0), (8, 0.15), (13, 0.15), (16, -0.15), (18, -0.2), (26, -0.22), (32, 0)],
    )
    bone_curve(
        act,
        "spine",
        1,
        [
            (1, 0.06),
            (8, -0.12),
            (13, -0.18),
            (16, -0.04),
            (18, 0.24),
            (26, 0.3),
            (32, 0.08),
        ],
    )
    bone_curve(
        act,
        "chest",
        1,
        [
            (1, -0.08),
            (8, -0.27),
            (14, -0.3),
            (17, 0.08),
            (18, 0.3),
            (21, 0.4),
            (26, 0.34),
            (32, -0.06),
        ],
    )
    bone_curve(
        act,
        "chest",
        2,
        [(1, 0), (8, 0.08), (13, 0.1), (18, -0.08), (26, -0.12), (32, 0)],
    )
    bone_curve(
        act,
        "spine",
        2,
        [(1, 0), (8, 0.06), (13, 0.08), (18, -0.1), (26, -0.14), (32, 0)],
    )
    bone_curve(
        act,
        "clavicle.R",
        1,
        [(1, 0), (13, -0.08), (16, -0.1), (18, 0.2), (26, 0.3), (32, 0)],
    )
    # Keep the nonstriking arm in a protective guard instead of a broad T silhouette.
    bone_curve(
        act,
        "upper_arm.L",
        0,
        [(1, -0.55), (13, -0.75), (18, -0.65), (26, -0.5), (32, -0.6)],
    )
    bone_curve(
        act, "forearm.L", 0, [(1, -1.05), (13, -1.35), (18, -1.2), (26, -1), (32, -1)]
    )
    wall = strip(A, "wall_impact").action
    for bone in ("pelvis", "spine", "chest"):
        for axis in range(3):
            c = curve(wall, f'pose.bones["{bone}"].rotation_euler', axis)
            for k in c.keyframe_points:
                if k.co.x == 17:
                    k.co.y = 0.08 if axis == 1 else 0
    # Delay the victim's collapse until AFTER contact. Native V3 folded the torso away first.
    hit = strip(A, "heavy_hit")
    hit.blend_in = 0
    warp(hit, [(161, 1), (165, 1), (169, 4), (174, 13), (178, 20)])
    for c in hit.action.fcurves:
        if any(f'"{b}"' in c.data_path for b in ("pelvis", "spine", "chest")):
            for k in c.keyframe_points:
                k.co.y *= 0.52
    launch = strip(A, "launch_backward")
    launch.frame_start = 167
    launch.blend_in = 7
    warp(launch, [(167, 1), (173, 3), (179, 5), (201, 15), (238, 22)])
    for s in (launch, strip(A, "airborne_tumble")):
        act = s.action
        for c in act.fcurves:
            if "upper_arm.L" in c.data_path:
                for k in c.keyframe_points:
                    k.co.y *= 0.7
            if "thigh.R" in c.data_path:
                for k in c.keyframe_points:
                    k.co.y *= 0.62
        # Different wrist/forearm lag on each side, sampled through the existing strip.
        end = act.frame_range[1]
        bone_curve(
            act,
            "forearm.L",
            0,
            [(1, -0.9), (end * 0.35, -0.25), (end * 0.7, -1.2), (end, -0.6)],
        )
        bone_curve(
            act,
            "forearm.R",
            0,
            [(1, -0.35), (end * 0.4, -1.1), (end * 0.8, -0.3), (end, -0.9)],
        )
    # Stretch compression and settling instead of racing to an upright recovery.
    land = strip(A, "hard_landing")
    land.frame_end = 310
    land.blend_out = 8
    warp(
        land,
        [(258, 1), (271, 10), (277, 15), (280, 18), (291, 22), (301, 27), (310, 32)],
    )
    for bone, axis, vals in [
        (
            "spine",
            2,
            [
                (1, 0.05),
                (10, 0.1),
                (15, 0.38),
                (18, 0.5),
                (22, 0.38),
                (27, 0.2),
                (32, 0.08),
            ],
        ),
        (
            "chest",
            2,
            [
                (1, 0.04),
                (10, 0.08),
                (15, 0.15),
                (18, 0.3),
                (22, 0.42),
                (27, 0.16),
                (32, 0.04),
            ],
        ),
        (
            "upper_arm.R",
            0,
            [
                (1, -0.8),
                (10, -0.5),
                (15, -0.18),
                (18, 0.1),
                (22, -0.1),
                (27, -0.4),
                (32, -0.6),
            ],
        ),
        (
            "upper_arm.L",
            0,
            [
                (1, -0.6),
                (10, -0.3),
                (15, 0.1),
                (18, 0.2),
                (22, 0),
                (27, -0.35),
                (32, -0.5),
            ],
        ),
    ]:
        bone_curve(land.action, bone, axis, vals)
    getup = strip(A, "get_up")
    getup.frame_start = 302
    getup.frame_end = 340
    getup.blend_in = 8
    warp(getup, [(302, 1), (313, 10), (321, 18), (333, 28), (340, 34)])
    idle = strip(A, "combat_idle")
    idle.frame_start = 335
    idle.blend_in = 5
    # Hand-directed guard/attack/landing limb arcs replace the broad stock silhouettes.
    for rig in (A, B):
        for t in rig.animation_data.nla_tracks:
            for st in t.strips:
                act = st.action
                frames = sorted(
                    {int(k.co.x) for c in act.fcurves for k in c.keyframe_points}
                )
                for f in frames:
                    kind = "guard"
                    if "heavy_cross" in st.name:
                        kind = (
                            "coil"
                            if 8 <= f <= 13
                            else (
                                "extend"
                                if 14 <= f <= 18
                                else "follow" if 19 <= f <= 26 else "guard"
                            )
                        )
                    elif "dash" in st.name:
                        kind = "dash"
                    elif "hard_landing" in st.name or ("get_up" in st.name and f <= 18):
                        kind = "landing"
                    elif "heavy_hit" in st.name and f == 1:
                        kind = "landing"
                    elif (
                        "launch" in st.name
                        or "tumble" in st.name
                        or "heavy_hit" in st.name
                    ):
                        continue
                    direct_arm_pose(rig, act, f, kind)
    # No all-body fold on first contact: moderate the stock hit before the launch takes over.
    for c in hit.action.fcurves:
        if any(f'"{b}"' in c.data_path for b in ("pelvis", "spine", "chest")):
            for k in c.keyframe_points:
                if k.co.x <= 1:
                    k.co.y = 0


def motion_edit():
    fa = -math.pi / 2
    # Hold the coil until f79, cross the gap over eight frames.
    root_keys(
        A,
        [
            (55, (-4.8, 0, 0), (0, 0, fa), (1, 1, 1)),
            (75, (-5, 0, -0.07), (0, -0.1, fa), (1, 1, 1)),
            (79, (-4.85, 0, -0.06), (0, -0.15, fa), (1, 1, 1)),
            (83, (-3.6, 0, -0.04), (0, -0.18, fa), (1.08, 0.96, 0.97)),
            (87, (2.4, 0, 0), (0, -0.08, fa), (1.06, 0.98, 0.98)),
            (92, (4.9, 0, 0), (0, 0, fa), (1, 1, 1)),
            (100, (4.9, 0, 0), (0, 0, fa), (1, 1, 1)),
        ],
        55,
        100,
    )
    root_keys(
        B,
        [
            (73, (2.4, 0, 0), (0, 0, math.pi / 2), (1, 1, 1)),
            (81, (2.4, 0, 0), (0, 0, math.pi / 2), (1, 1, 1)),
            (85, (2.4, -0.7, -0.1), (0, -0.1, math.pi / 2), (1, 1, 1)),
            (87, (2.4, -1.45, -0.12), (0, -0.15, math.pi / 2), (1, 1, 1)),
            (93, (2.4, -2.3, -0.08), (0, -0.08, math.pi / 2), (1, 1, 1)),
            (108, (2.4, -2.3, 0), (0, 0, math.pi / 2), (1, 1, 1)),
        ],
        73,
        108,
    )
    root_keys(
        A,
        [
            (100, (4.9, 0, 0), (0, 0, fa), (1, 1, 1)),
            (110, (5.1, 0, 0), (0, 0, fa), (1, 1, 1)),
            (116, (5.52, 0, -0.04), (0, 0, fa), (1, 1, 1)),
            (118, (5.52, 0, -0.04), (0, 0, fa), (1, 1, 1)),
            (127, (4.9, 0, 0), (0, 0, fa), (1, 1, 1)),
        ],
        100,
        127,
    )
    # Keep the original leftward knockback geography. Counter now flanks to A's right.
    root_keys(
        B,
        [
            (128, (2.4, -2.3, 0), (0, 0, math.pi / 2), (1, 1, 1)),
            (148, (3.25, -2.15, -0.04), (0, 0, 1.8), (1, 1, 1)),
            (158, (5.2, -1.65, -0.04), (0, 0, 2.4), (1, 1, 1)),
            (163, (5.55, -1.15, 0), (0, 0, 2.2), (1, 1, 1)),
            (165, (5.55, -1.15, 0), (0, 0, 2.2), (1, 1, 1)),
            (173, (5.45, -1.1, -0.03), (0, 0, 2.35), (1, 1, 1)),
            (189, (5.55, -1.15, 0), (0, 0, 2.2), (1, 1, 1)),
            (360, (5.55, -1.15, 0), (0, 0, 2.2), (1, 1, 1)),
        ],
        128,
        360,
    )
    # Launch immediately out of hit stop. Accelerate rotation then open out to slow it.
    root_keys(
        A,
        [
            (161, (4.9, 0, 0), (0, 0, fa), (1, 1, 1)),
            (163, (4.9, 0, 0), (0, 0, fa), (1, 1, 1)),
            (165, (4.9, 0, 0), (0, 0, fa), (1, 1, 1)),
            (167, (4.55, 0.05, 0.3), (0.04, 0.12, fa), (1, 1, 1)),
            (173, (2.5, 0.3, 2.25), (0.12, 0.9, fa + 0.12), (1, 1, 1)),
            (184, (0.2, 0.6, 4.8), (0.2, 2.35, fa + 0.3), (1, 1, 1)),
            (202, (-1.7, 0.95, 5.3), (0.35, 3.8, fa + 0.55), (1, 1, 1)),
            (225, (-2.6, 1.2, 4.4), (0.23, 4.55, fa + 0.4), (1, 1, 1)),
            (245, (-3, 1.3, 3), (0.14, 5.6, fa + 0.2), (1, 1, 1)),
            (260, (-3.2, 1.3, 1.55), (0.04, 6.1, fa + 0.08), (1, 1, 1)),
            (271, (-3.28, 1.3, 0.55), (0, 6.24, fa), (1, 1, 1)),
            (277, (-3.35, 1.3, -0.43), (0, math.tau, fa), (1.03, 1.03, 0.96)),
            (281, (-3.65, 1.3, -0.46), (0, math.tau + 0.05, fa), (1.02, 1.02, 0.98)),
            (290, (-4.15, 1.3, -0.3), (0, math.tau + 0.08, fa), (1, 1, 1)),
            (300, (-4.28, 1.3, -0.34), (0, math.tau + 0.02, fa), (1, 1, 1)),
            (311, (-4.3, 1.3, -0.08), (0, math.tau, fa), (1, 1, 1)),
            (326, (-4.3, 1.3, -0.03), (0, math.tau, fa), (1, 1, 1)),
            (340, (-4.3, 1.3, 0), (0, math.tau, fa), (1, 1, 1)),
            (360, (-4.3, 1.3, 0), (0, math.tau, fa), (1, 1, 1)),
        ],
        161,
        360,
    )
    # Do not pin B's feet to the old starting position while its root advances.
    for rig in (A, B):
        for side in ("L", "R"):
            path = f'pose.bones["shin.{side}"].constraints["Procedural contact foot.{side}"].influence'
            c = curve(rig.animation_data.action, path)
            if rig == B:
                retained = [tuple(k.co) for k in c.keyframe_points if k.co.x < 128]
                c.keyframe_points.clear()
                for f, v in retained:
                    c.keyframe_points.insert(f, v)
                for f, v in [
                    (128, 0),
                    (160, 0),
                    (163, 1),
                    (165, 1),
                    (172, 0),
                    (360, 0),
                ]:
                    c.keyframe_points.insert(f, v)
            else:
                retained = [tuple(k.co) for k in c.keyframe_points if k.co.x < 258]
                c.keyframe_points.clear()
                for f, v in retained:
                    c.keyframe_points.insert(f, v)
                for f, v in [
                    (258, 0),
                    (274, 0),
                    (277, 1),
                    (310, 1),
                    (320, 0),
                    (360, 0),
                ]:
                    c.keyframe_points.insert(f, v)
            for k in c.keyframe_points:
                k.interpolation = "LINEAR"
            c.update()
            ctrl = bpy.data.objects[f"{rig.name[:-4]}_IK_foot.{side}"]
            if rig == B:
                pt = Vector((5.55, -1.15, 0.05)) + Vector(
                    (-0.2, 0.3 if side == "L" else -0.3, 0)
                )
                for axis in range(3):
                    c = curve(ctrl.animation_data.action, "location", axis)
                    prior = [tuple(k.co) for k in c.keyframe_points if k.co.x < 128]
                    keys(
                        ctrl.animation_data.action,
                        "location",
                        axis,
                        prior + [(128, pt[axis]), (360, pt[axis])],
                    )
            else:
                for axis in range(3):
                    vals = []
                    for f, x in [
                        (258, -3.35),
                        (277, -3.35),
                        (281, -3.65),
                        (290, -4.15),
                        (300, -4.28),
                        (311, -4.3),
                        (360, -4.3),
                    ]:
                        pt = (x + (0.3 if side == "L" else -0.3), 1.12, 0.05)
                        vals.append((f, pt[axis]))
                    c = curve(ctrl.animation_data.action, "location", axis)
                    prior = [tuple(k.co) for k in c.keyframe_points if k.co.x < 258]
                    keys(ctrl.animation_data.action, "location", axis, prior + vals)
    pole = bpy.data.objects.new("Astra_CounterElbowPole", None)
    bpy.context.collection.objects.link(pole)
    pole.location = (5.7, -2.3, 1.65)
    contact_ik = B.pose.bones["forearm.R"].constraints["Procedural contact hand.R"]
    contact_ik.pole_target = pole
    contact_ik.pole_angle = math.pi
    contact_ik.chain_count = 2
    # Correct to the evaluated victim torso, not the old fixed target in empty space.
    evaluate(163)
    surface = point(A, "spine").lerp(point(A, "chest"), 0.72) + Vector((0.18, -0.15, 0))
    ctrl = bpy.data.objects["fighter_b_IK_hand.R"]
    evaluate(158)
    rest = point(B, "forearm.R", True)
    for axis in range(3):
        keys(
            ctrl.animation_data.action,
            "location",
            axis,
            [
                (128, rest[axis]),
                (158, rest[axis]),
                (161, rest.lerp(surface, 0.55)[axis]),
                (163, surface[axis]),
                (165, surface[axis]),
                (169, (surface + Vector((-0.25, 0.04, 0.02)))[axis]),
                (177, rest[axis]),
            ],
        )
    path = 'pose.bones["forearm.R"].constraints["Procedural contact hand.R"].influence'
    keys(
        B.animation_data.action,
        path,
        0,
        [
            (1, 0),
            (158, 0),
            (161, 0.3),
            (163, 1),
            (165, 1),
            (169, 0.45),
            (174, 0),
            (360, 0),
        ],
    )
    return surface


def camera_edit():
    # Keep old camera objects for inspection, but replace their edit markers.
    for marker in list(SCENE.timeline_markers):
        SCENE.timeline_markers.remove(marker)
    specs = [
        ("01_faceoff_OTS", 1, 36, "fixed", (-7.9, -2.8, 2.7), (-0.3, 0, 1.5), 42),
        ("02_coil", 37, 78, "A", (-2.6, -5.7, 0.1), (0, 0, 1.3), 48),
        ("03_near_miss", 79, 96, "fixed", (-0.6, -8, 4.8), (2.7, -0.8, 1.25), 38),
        ("04_wall", 97, 127, "A", (-2.6, -5.7, 0.6), (0, 0, 1.4), 48),
        ("05_counter_coil", 128, 153, "B", (-2.0, -5.6, 0.35), (0, 0, 1.5), 48),
        (
            "06_counter_contact",
            154,
            176,
            "fixed",
            (1.24, -5.1, 2.3),
            (5.1, -0.5, 1.5),
            46,
        ),
        ("07_launch", 177, 211, "A", (-1.2, -6.7, 0.7), (0, 0, 1.0), 44),
        ("08_air_recovery", 212, 261, "A", (-2.1, -6.4, 2.5), (0, 0, 0.7), 44),
        ("09_ground_impact", 262, 304, "A", (-2.1, -6.3, 0.3), (0, 0, 1.0), 46),
        ("10_settle", 305, 330, "A", (-2, -5.3, 0.4), (0, 0, 1.3), 48),
        ("11_aftermath", 331, 360, "B", (-3.8, -5.8, 0.25), (0, 0, 1.5), 48),
    ]
    shots = []
    for name, start, end, subject, offset, target, lens in specs:
        d = bpy.data.cameras.new("Astra_" + name)
        cam = bpy.data.objects.new("Astra_" + name, d)
        bpy.context.collection.objects.link(cam)
        d.lens = lens
        d.sensor_fit = "VERTICAL"
        d.sensor_height = 36
        d.clip_start = 0.05
        positions = []
        prior = None
        for f in range(start, end + 1):
            evaluate(f)
            if subject == "fixed":
                loc = Vector(offset)
                aim = Vector(target)
            else:
                rig = A if subject == "A" else B
                # Head/hips center follows body rotation, rather than the feet-space root.
                center = (point(rig, "pelvis") + point(rig, "head")) * 0.5
                desired = center + Vector((0, 0, target[2] - 1.35))
                if prior is None:
                    prior = desired
                rate = 0.65 if name.startswith("07") else 0.4
                aim = prior.lerp(desired, rate)
                prior = aim
                loc = aim + Vector(offset)
            # Small, finite response after contact and ground impact only.
            if 166 <= f <= 173:
                loc += Vector(
                    (
                        0.035 * math.sin((f - 166) * 2),
                        0,
                        0.025 * math.cos((f - 166) * 2),
                    )
                ) * (1 - (f - 166) / 8)
            if 277 <= f <= 285:
                loc.z += 0.055 * math.sin((f - 277) * 2) * (1 - (f - 277) / 9)
            if name.startswith("06") and f >= 166:
                # Let the victim exit left, retaining B's follow-through in frame.
                aim.x -= min(0.45, (f - 166) * 0.045)
            cam.location = loc
            cam.rotation_euler = (aim - loc).to_track_quat("-Z", "Y").to_euler()
            cam.keyframe_insert("location", frame=f)
            cam.keyframe_insert("rotation_euler", frame=f)
            positions.append({"frame": f, "position": list(loc), "target": list(aim)})
        for c in cam.animation_data.action.fcurves:
            for k in c.keyframe_points:
                k.interpolation = "LINEAR"
        m = SCENE.timeline_markers.new(name, frame=start)
        m.camera = cam
        shots.append(
            {
                "shot_id": name,
                "start_frame": start,
                "end_frame": end,
                "lens_mm": lens,
                "tracking_subject": subject,
                "keys": positions,
            }
        )
    SCENE.camera = bpy.data.objects["Astra_01_faceoff_OTS"]
    return shots


def effects_edit():
    for obj in bpy.data.objects:
        if obj.name.startswith("BrokenColumn"):
            obj.hide_render = True
    for obj in bpy.data.objects:
        if obj.name.startswith(("vfx-001", "vfx-004", "vfx-005", "vfx-006")):

            if obj.animation_data and obj.animation_data.action:
                c = obj.animation_data.action.fcurves.find("hide_render")
                if c:
                    for k in c.keyframe_points:
                        k.co.y = 1
            obj.hide_render = True  # Motion must read without static speed bars or contact-obscuring rings.
        if obj.name.startswith("vfx-007"):
            obj.location.x -= 1.3
            if obj.animation_data and obj.animation_data.action:
                for c in obj.animation_data.action.fcurves:
                    if c.data_path == "scale":
                        for k in c.keyframe_points:
                            k.co.y *= 0.45
        if obj.name.startswith(("vfx-002", "vfx-003")):
            # Fragments settle out, rather than hanging in the counterattack silhouette.
            c = obj.animation_data.action.fcurves.find("hide_render")
            if c:
                for k in c.keyframe_points:
                    if k.co.x >= 128:
                        k.co.y = 1
            obj.hide_render = False
            obj.keyframe_insert("hide_render", frame=127)
            obj.hide_render = True
            obj.keyframe_insert("hide_render", frame=128)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "review").mkdir(exist_ok=True)
    (OUT / "renders/preview").mkdir(parents=True, exist_ok=True)
    body_edit()
    surface = motion_edit()
    effects_edit()
    shots = camera_edit()
    SCENE["wws_director_pass"] = "astra_v1"
    SCENE["wws_parent_scene"] = "blender_combat_v3/scene.blend"
    SCENE.render.resolution_x = 360
    SCENE.render.resolution_y = 640
    SCENE.render.resolution_percentage = 100
    SCENE.render.engine = "BLENDER_WORKBENCH"
    SCENE.frame_start = 1
    SCENE.frame_end = 360
    SCENE.render.fps = 30
    SCENE.use_nodes = False
    SCENE.render.image_settings.file_format = "FFMPEG"
    SCENE.render.ffmpeg.format = "MPEG4"
    SCENE.render.ffmpeg.codec = "H264"
    SCENE.render.ffmpeg.constant_rate_factor = "MEDIUM"
    SCENE.render.filepath = str(OUT / "renders/preview/fight.mp4")
    evaluate(163)
    error = (point(B, "forearm.R", True) - surface).length
    report = {
        "contact_target": list(surface),
        "contact_error": error,
        "source_checksum": SCENE.get("wws_source_checksum"),
        "outcome_digest": SCENE.get("wws_source_outcome_digest"),
        "shots": shots,
    }
    (OUT / "review/director_edits.json").write_text(json.dumps(report, indent=2))
    evaluate(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "scene.blend"))
    SCENE.render.image_settings.file_format = "PNG"
    for f in (
        20,
        70,
        87,
        100,
        145,
        158,
        163,
        165,
        172,
        184,
        210,
        245,
        277,
        287,
        305,
        340,
    ):
        evaluate(f)
        SCENE.render.filepath = str(OUT / f"review/frame_{f:03d}.png")
        bpy.ops.render.render(write_still=True)
    if "--render" in sys.argv:
        SCENE.render.image_settings.file_format = "FFMPEG"
        SCENE.render.filepath = str(OUT / "renders/preview/fight.mp4")
        bpy.ops.render.render(animation=True)
    print("DIRECTOR PASS", json.dumps({"contact_error": error, "output": str(OUT)}))


if __name__ == "__main__":
    main()
