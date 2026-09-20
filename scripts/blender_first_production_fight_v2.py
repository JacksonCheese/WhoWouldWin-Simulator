"""Spatial-integrity pass for the first Naruto vs Omni-Man production fight.

The deterministic event log and visible character models are unchanged. This script
builds the validated first-production scene into a new output, re-stages close-range
root spacing, constrains the Rasengan to Omni-Man's chest surface, creates evaluated
bone-following collision proxies, emits per-frame diagnostics, and adds dedicated
technical review renders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/first_production_fight_v2"
BASE_SCRIPT = ROOT / "scripts/blender_first_production_fight.py"
FPS = 30
END = 540
TOLERANCE = 0.045


def load_base():
    spec = importlib.util.spec_from_file_location("wws_first_production_base", BASE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    module.OUTPUT = OUTPUT
    return module


base = load_base()
SCENE = bpy.context.scene

base_humanoid_path = ROOT / "src/whowouldwin/cinematic/blender_backend/base_humanoid.py"
base_humanoid_spec = importlib.util.spec_from_file_location("wws_base_humanoid", base_humanoid_path)
base_humanoid = importlib.util.module_from_spec(base_humanoid_spec)
assert base_humanoid_spec and base_humanoid_spec.loader
sys.modules[base_humanoid_spec.name] = base_humanoid
base_humanoid_spec.loader.exec_module(base_humanoid)


@dataclass(frozen=True)
class Capsule:
    fighter: str
    role: str
    a: Vector
    b: Vector
    radius: float


PROXY_SPECS = {
    "head": ("Head", 0.25),
    "chest": ("SpineUpper", 0.30),
    "pelvis": ("Hips", 0.27),
    "upper_arm.L": ("UpperArm_L", 0.11),
    "upper_arm.R": ("UpperArm_R", 0.11),
    "forearm.L": ("LowerArm_L", 0.085),
    "forearm.R": ("LowerArm_R", 0.085),
    "hand.L": ("Hand_L", 0.09),
    "hand.R": ("Hand_R", 0.09),
    "thigh.L": ("UpperLeg_L", 0.16),
    "thigh.R": ("UpperLeg_R", 0.16),
    "shin.L": ("LowerLeg_L", 0.11),
    "shin.R": ("LowerLeg_R", 0.11),
    "foot.L": ("Foot_L", 0.12),
    "foot.R": ("Foot_R", 0.12),
}


def segment_distance(p1: Vector, q1: Vector, p2: Vector, q2: Vector) -> float:
    """Shortest distance between two 3D line segments."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1.dot(d1), d2.dot(d2), d2.dot(r)
    eps = 1e-9
    if a <= eps and e <= eps:
        return (p1 - p2).length
    if a <= eps:
        s, t = 0.0, max(0.0, min(1.0, f / e))
    else:
        c = d1.dot(r)
        if e <= eps:
            t = 0.0
            s = max(0.0, min(1.0, -c / a))
        else:
            b = d1.dot(d2)
            denom = a * e - b * b
            s = max(0.0, min(1.0, (b * f - c * e) / denom)) if denom else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t = 0.0
                s = max(0.0, min(1.0, -c / a))
            elif t > 1.0:
                t = 1.0
                s = max(0.0, min(1.0, (b - c) / a))
    return (p1 + d1 * s - (p2 + d2 * t)).length


def capsule_for(rig, fighter: str, role: str) -> Capsule:
    bone_name, radius = PROXY_SPECS[role]
    bone = rig.pose.bones[bone_name]
    matrix = rig.matrix_world
    a = matrix @ bone.head
    b = matrix @ bone.tail
    if role == "head":
        center = a.lerp(b, 0.58)
        a = b = center
    elif role.startswith("hand"):
        center = a.lerp(b, 0.65)
        a = b = center
    return Capsule(fighter, role, a, b, radius)


def fighter_capsules(rig, fighter: str) -> list[Capsule]:
    return [capsule_for(rig, fighter, role) for role in PROXY_SPECS]


def intended_contact(frame: int, a: Capsule, b: Capsule) -> bool:
    roles = {(a.fighter, a.role), (b.fighter, b.role)}
    # Brief open-hand parry during the slip.
    if 296 <= frame <= 303:
        return ("naruto", "hand.L") in roles and (
            ("omniman", "hand.L") in roles or ("omniman", "forearm.L") in roles
        )
    # Naruto body counter is the recorded melee hit/block passage.
    if 306 <= frame <= 322:
        return (("naruto", "hand.R") in roles or ("naruto", "forearm.R") in roles) and (
            ("omniman", "chest") in roles or ("omniman", "forearm.L") in roles
        )
    # Guard redirection and guard bypass before the Rasengan entry.
    if 328 <= frame <= 338:
        return any(("naruto", role) in roles for role in ("hand.L", "forearm.L", "upper_arm.L")) and any(
            ("omniman", role) in roles for role in ("hand.L", "forearm.L", "upper_arm.L")
        )
    if 354 <= frame <= 359:
        return ("naruto", "hand.R") in roles and any(
            ("omniman", role) in roles for role in ("hand.L", "forearm.L", "upper_arm.L")
        )
    # The Rasengan contact hold is tangent hand-to-chest contact.
    if 363 <= frame <= 371:
        return ("naruto", "hand.R") in roles and ("omniman", "chest") in roles
    return False


def add_root_key(rig, frame, location, yaw, *, tilt=0.0, roll=0.0, interpolation="BEZIER"):
    base.key_root(rig, frame, location, yaw, tilt=tilt, roll=roll, interpolation=interpolation)


def restage_close_exchange():
    """Create lateral negative space while preserving all event outcomes."""
    omni = bpy.data.objects["fighter_a_Rig"]
    naruto = bpy.data.objects["fighter_b_Rig"]
    # Three-quarter exchange: neither center occupies the other's body volume.
    for frame, loc, yaw in (
        (260, (-4.5, 1.55, 0.08), math.pi - 0.18),
        (278, (-2.75, 1.15, 0.05), math.pi - 0.25),
        (294, (-2.15, 0.95, 0.05), math.pi - 0.32),
        (306, (-1.85, 1.02, 0.05), math.pi - 0.42),
        (320, (-1.55, 1.08, 0.05), math.pi - 0.35),
        (334, (-1.05, 1.05, 0.05), math.pi - 0.20),
        (348, (-0.30, 1.02, 0.05), math.pi - 0.18),
        (360, (0.28, 0.95, 0.05), math.pi - 0.10),
        (365, (0.42, 0.88, 0.05), math.pi - 0.08),
        (368, (0.42, 0.88, 0.05), math.pi - 0.08),
        (371, (0.42, 0.88, 0.05), math.pi - 0.08),
        (380, (2.1, 1.1, 1.5), math.pi + 0.35),
    ):
        add_root_key(omni, frame, loc, yaw, interpolation="CONSTANT" if frame in {365, 371} else "BEZIER")
    for frame, loc, yaw in (
        (260, (-1.55, -1.85, 0.08), 1.18),
        (278, (-2.05, -0.72, 0.03), 0.34),
        (289, (-2.22, -1.18, 0.14), 0.52),  # slip outside Omni-Man's right hand
        (299, (-1.80, -0.83, 0.17), 0.44),
        (300, (-1.76, -0.80, 0.18), 0.43),
        (301, (-1.71, -0.76, 0.18), 0.43),
        (302, (-1.66, -0.72, 0.18), 0.42),
        (303, (-1.62, -0.68, 0.18), 0.42),
        (316, (-1.42, -0.38, 0.12), 0.30),  # counter contact
        (326, (-1.70, -0.70, 0.03), 0.62),  # redirected off the block
        (338, (-0.62, -0.82, 0.03), 0.52),  # angle change
        (350, (-0.75, -0.60, 0.03), 0.22),
        (360, (-0.82, -0.78, 0.03), 0.12),
        (365, (-0.58, -0.46, 0.03), 0.10),
        (368, (-0.58, -0.46, 0.03), 0.10),
        (371, (-0.58, -0.46, 0.03), 0.10),
        (386, (0.25, 0.18, 0.03), 0.06),
    ):
        add_root_key(naruto, frame, loc, yaw, interpolation="CONSTANT" if frame in {365, 371} else "BEZIER")

    # Exact surface contact: target the near surface of Omni-Man's chest, never its center.
    control = bpy.data.objects["fighter_b_IK_hand.R"]
    ik = next(c for c in naruto.pose.bones["forearm.R"].constraints if c.type == "IK")
    approach = Vector((0.42 + 0.46, 0.88 - 0.08, 0))
    approach.normalize()
    chest_center = Vector((0.42, 0.88, 1.73))
    surface = chest_center - approach * 0.39
    for frame, influence, point in (
        (338, 0.0, (-0.25, -0.1, 1.55)),
        (354, 0.55, tuple(surface - approach * 0.35)),
        (362, 0.92, tuple(surface - approach * 0.06)),
        (365, 1.0, tuple(surface)),
        (371, 1.0, tuple(surface)),
        (376, 0.45, tuple(surface + approach * 0.16)),
        (382, 0.0, tuple(surface + approach * 0.35)),
    ):
        base.loc_key(control, frame, point, "BEZIER")
        ik.influence = influence
        ik.keyframe_insert("influence", frame=frame)
    return tuple(surface)


def separate_omniman_reaction_arm():
    """Keep the non-striking arm out of Naruto's Rasengan contact corridor."""
    rig = bpy.data.objects["fighter_a_Rig"]
    action = bpy.data.actions.get("WWS_CHAR_omniman_impact_launch")
    if not action:
        return
    root_action = rig.animation_data.action
    rig.animation_data.action = action
    for frame, upper, fore in (
        (1, (-0.72, -0.18, -1.02), (-0.62, 0.12, -0.10)),
        (4, (-0.38, -0.32, -1.38), (-0.48, 0.28, -0.22)),
        (7, (-0.18, -0.42, -1.52), (-0.35, 0.34, -0.28)),
        (10, (0.20, -0.30, -1.22), (-0.28, 0.25, -0.20)),
        (13, (0.62, -0.18, -0.92), (-0.22, 0.16, -0.12)),
    ):
        for bone_name, rotation in (("upper_arm.L", upper), ("forearm.L", fore)):
            bone = rig.pose.bones[bone_name]
            bone.rotation_mode = "XYZ"
            bone.rotation_euler = rotation
            bone.keyframe_insert("rotation_euler", frame=frame)
    for curve in action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = "BEZIER"
            key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"
    rig.animation_data.action = root_action


def refine_rasengan_tangent() -> tuple[float, float, float]:
    """Place Naruto's hand target against the evaluated chest surface.

    The first authored target is only an estimate because NLA body animation moves
    the chest and hand bones after root staging. This pass evaluates the final rigs
    and moves the IK control until the hand capsule has a shallow, visible contact
    instead of entering the chest or pelvis volume.
    """
    omni = bpy.data.objects["fighter_a_ProductionRig"]
    naruto = bpy.data.objects["fighter_b_ProductionRig"]
    naruto_source = bpy.data.objects["fighter_b_Rig"]
    control = bpy.data.objects["fighter_b_IK_hand.R"]
    # Limit stretch to a modest production correction. This covers differences
    # between the generic clip and the presented proportions without allowing the
    # arm to telescope through the target.
    for rig in (naruto_source, naruto):
        for bone_name in ("upper_arm.R", "forearm.R", "UpperArm_R", "LowerArm_R"):
            bone = rig.pose.bones.get(bone_name)
            if bone:
                bone.ik_stretch = 0.18
    def wrist_target(frame: int) -> tuple[Vector, Vector]:
        SCENE.frame_set(frame)
        bpy.context.view_layer.update()
        chest = capsule_for(omni, "omniman", "chest")
        chest_center = chest.a.lerp(chest.b, 0.5)
        fighter_center = Vector((naruto_source.location.x, naruto_source.location.y, chest_center.z))
        outward = fighter_center - chest_center
        outward.normalize()
        # Aim above the pelvis/chest seam. The Rasengan overlaps the presentation
        # surface; the fist endpoint remains outside the body volume.
        desired_fist = chest_center + outward * (chest.radius + 0.14) + Vector((0, 0, 0.16))
        control.location = chest_center + outward * (chest.radius + 0.25)
        bpy.context.view_layer.update()
        evaluated_hand = capsule_for(naruto, "naruto", "hand.R")
        hand_vector = evaluated_hand.b - evaluated_hand.a
        return desired_fist - hand_vector, outward

    contact_365, outward_365 = wrist_target(365)
    for frame, point in (
        (354, contact_365 + outward_365 * 0.48),
        (358, contact_365 + outward_365 * 0.22),
        (362, contact_365 + outward_365 * 0.07),
        (365, contact_365),
        (368, contact_365),
        (371, contact_365),
        (374, contact_365 + outward_365 * 0.40),
        (375, contact_365 + outward_365 * 0.52),
        (379, contact_365 + outward_365 * 0.72),
    ):
        base.loc_key(control, frame, point, "BEZIER")
    return tuple(contact_365)


def apply_clearance_solver() -> list[dict]:
    """Correct presentation overlap while leaving event timing and outcomes intact.

    The solver evaluates the production rigs rather than the control-rig roots.
    It moves Naruto's presentation root laterally by the minimum amount required
    to clear the deepest unsupported cross-fighter capsule. Authored contact pairs
    are excluded, so the counter and Rasengan still connect. Small corrections are
    keyed frame-by-frame to avoid changing the surrounding choreography.
    """
    omni_source = bpy.data.objects["fighter_a_Rig"]
    naruto_source = bpy.data.objects["fighter_b_Rig"]
    omni_eval = bpy.data.objects["fighter_a_ProductionRig"]
    naruto_eval = bpy.data.objects["fighter_b_ProductionRig"]
    corrections: list[dict] = []
    for frame in range(1, END + 1):
        total_shift = 0.0
        pair = None
        # Three passes handle angled capsules whose separation is not perfectly
        # aligned to the first horizontal correction vector.
        for _ in range(8):
            SCENE.frame_set(frame)
            bpy.context.view_layer.update()
            omni_caps = fighter_capsules(omni_eval, "omniman")
            naruto_caps = fighter_capsules(naruto_eval, "naruto")
            candidates = []
            for a in omni_caps:
                for b in naruto_caps:
                    if intended_contact(frame, a, b):
                        continue
                    # The Rasengan arm is solved by the dedicated tangent pass.
                    # Translating the whole fighter cannot correct a world-space
                    # IK target and would instead create an unnaturally stretched arm.
                    if 348 <= frame <= 379 and b.role in {"hand.R", "forearm.R"}:
                        continue
                    penetration = a.radius + b.radius - segment_distance(a.a, a.b, b.a, b.b)
                    if penetration > TOLERANCE:
                        candidates.append((penetration, a.role, b.role))
            if not candidates:
                break
            penetration, role_a, role_b = max(candidates)
            pair = [role_a, role_b]
            amount = penetration - TOLERANCE + 0.018
            delta = Vector((naruto_source.location.x - omni_source.location.x,
                            naruto_source.location.y - omni_source.location.y, 0.0))
            if delta.length < 1e-5:
                delta = Vector((0.0, -1.0, 0.0))
            else:
                delta.normalize()
            naruto_source.location += delta * amount
            naruto_source.keyframe_insert("location", frame=frame)
            total_shift += amount
        if total_shift:
            action = naruto_source.animation_data.action
            rt = base.rt
            rt.set_key_interpolation(action, frame, "BEZIER")
            for curve in action.fcurves:
                for key in curve.keyframe_points:
                    if abs(key.co.x - frame) < 0.1:
                        key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"
            corrections.append({
                "frame": frame,
                "lateral_shift": round(total_shift, 5),
                "deepest_pair": pair,
            })
    return corrections


def improve_flight_and_cape():
    omni = bpy.data.objects["fighter_a_Rig"]
    # Stronger orientation into velocity and counter-rotation during braking/recovery.
    refinements = (
        (48, (7.2, -0.42, 0.12), 2.93, -0.18, 0.03),
        (56, (5.35, 0.00, 0.50), 2.93, -0.48, 0.12),
        (61, (1.55, 0.78, 0.82), 2.93, -0.72, 0.22),
        (65, (-3.55, 1.85, 0.76), 2.93, -0.70, 0.25),
        (70, (-7.75, 3.52, 0.68), 2.93, -0.48, 0.30),
        (78, (-10.0, 5.55, 0.48), 2.93, -0.12, 0.30),
        (96, (-10.38, 5.83, 0.18), 2.93, 0.30, -0.12),
        (430, (15.6, 1.92, 6.10), 4.75, -0.42, 0.92),
        (448, (18.45, 1.92, 4.55), 5.95, -0.58, -0.35),
        (466, (18.85, 1.48, 3.35), 3.28, -0.18, 0.18),
        (488, (16.2, 1.0, 3.0), 3.22, 0.02, -0.04),
    )
    for frame, loc, yaw, tilt, roll in refinements:
        add_root_key(omni, frame, loc, yaw, tilt=tilt, roll=roll, interpolation="LINEAR" if frame in {61, 65} else "BEZIER")

    cape = bpy.data.objects.get("OmniMan_Cape")
    if cape:
        # Move the rigid development cape behind the back and segment its visual bend
        # through scale/rotation keys. This is authored secondary motion, not cloth.
        cape.location.x -= 0.18
        cape.scale.y = 0.88
        for frame, rot, scale in (
            (1, (0, -0.12, 0), (1, 0.88, 1)),
            (48, (0, -0.22, 0), (1, 0.82, 1.0)),
            (58, (0, 0.58, -0.08), (1, 0.70, 1.18)),
            (66, (0, 1.02, -0.15), (1, 0.62, 1.34)),
            (78, (0, 0.70, -0.20), (1, 0.72, 1.22)),
            (96, (0, -0.52, 0.18), (1, 0.92, 0.88)),
            (118, (0, -0.30, 0.12), (1, 0.86, 0.95)),
            (280, (0, 0.12, -0.05), (1, 0.84, 1.02)),
            (365, (0, -0.42, -0.25), (1, 0.76, 0.95)),
            (382, (0, 0.30, 0.20), (1, 0.70, 1.15)),
            (420, (0, 0.92, 0.35), (1, 0.62, 1.32)),
            (448, (0, -0.70, -0.25), (1, 0.86, 0.88)),
            (470, (0, 0.28, 0.08), (1, 0.74, 1.12)),
            (500, (0, -0.22, 0), (1, 0.88, 1.0)),
        ):
            cape.rotation_euler = rot
            cape.scale = scale
            cape.keyframe_insert("rotation_euler", frame=frame)
            cape.keyframe_insert("scale", frame=frame)


def refine_cameras():
    """Open the exchange to three-quarter negative space and protect contact."""
    def key(name, frame, cam_loc, target_loc, lens):
        cam = bpy.data.objects[name]
        target = bpy.data.objects[name + "_Target"]
        base.camera_key(cam, target, frame, cam_loc, target_loc, lens)

    key("SHOT01_LowFaceoff", 1, (-10.7, 4.75, 1.25), (5.8, -0.2, 1.48), 38)
    key("SHOT01_LowFaceoff", 41, (-9.8, 4.45, 1.20), (6.5, -0.35, 1.52), 43)
    key("SHOT03_NarrowDodge", 62, (-1.1, -4.65, 1.75), (-5.25, 1.25, 1.42), 33)
    key("SHOT03_NarrowDodge", 86, (-5.7, -4.55, 1.62), (-7.4, 3.55, 1.50), 36)
    key("SHOT08_CloseExchange", 279, (-3.2, -4.75, 1.90), (-1.9, 0.15, 1.48), 46)
    key("SHOT08_CloseExchange", 310, (-2.4, -4.55, 1.72), (-1.55, 0.18, 1.48), 52)
    key("SHOT08_CloseExchange", 338, (0.2, -4.25, 1.58), (-0.75, 0.12, 1.47), 54)
    key("SHOT09_RasenganHero", 342, (-1.4, -4.9, 1.95), (-0.25, 0.42, 1.58), 50)
    key("SHOT09_RasenganHero", 362, (-0.9, -4.65, 1.82), (0.00, 0.55, 1.62), 58)
    key("SHOT09_RasenganHero", 365, (-0.65, -4.55, 1.78), (0.02, 0.58, 1.63), 62)
    key("SHOT09_RasenganHero", 371, (-0.65, -4.55, 1.78), (0.02, 0.58, 1.63), 62)
    key("SHOT09_RasenganHero", 381, (-0.65, -4.15, 2.00), (1.25, 0.9, 1.95), 52)
    key("SHOT10_LaunchTrack", 382, (1.2, -4.65, 3.0), (3.1, 1.0, 3.2), 32)
    key("SHOT10_LaunchTrack", 418, (9.5, -4.45, 5.2), (13.4, 1.7, 7.8), 35)


def city_polish():
    asphalt_patch = base.mat("City_AsphaltPatch", (0.035, 0.042, 0.052), roughness=0.95)
    sidewalk_alt = base.mat("City_SidewalkVariation", (0.38, 0.39, 0.40), roughness=0.82)
    sign_red = base.mat("City_SignRed", (0.65, 0.035, 0.025), roughness=0.42, emission=(0.32, 0.01, 0.01))
    roof_dark = base.mat("City_Rooftop", (0.045, 0.052, 0.06), roughness=0.76)
    metal = bpy.data.materials.get("City_Metal")
    city = bpy.data.collections["WWS_CITY_STREET"]

    # Clear the authored storefront impact lane. The original bin occupied the
    # same volume as Omni-Man's recovery pose after the facade breach.
    crash_bin = bpy.data.objects.get("TrashContainer_0")
    if crash_bin:
        crash_bin.location.x = -16.0

    added = []
    for idx, (x, y, sx, sy) in enumerate(((-20, -1.6, 3.5, 1.1), (-5, 2.2, 2.4, 0.8), (10, -1.0, 3.0, 0.9), (24, 1.8, 2.2, 0.7))):
        patch = base.cube(f"AsphaltPatch_{idx}", (x, y, 0.018), (sx, sy, 0.012), asphalt_patch, 0.04)
        patch.rotation_euler[2] = 0.08 * (-1 if idx % 2 else 1)
        added.append(patch)
    for idx, (x, y) in enumerate(((-25, 6.19), (-16, -6.19), (-2, 6.19), (12, -6.19), (25, 6.19))):
        slab = base.cube(f"SidewalkInset_{idx}", (x, y, 0.235), (2.1, 0.58, 0.018), sidewalk_alt, 0.025)
        added.append(slab)
    for idx, (x, y, z) in enumerate(((-20, 6.0, 3.2), (-1, -6.0, 3.0), (15, 6.0, 3.4))):
        sign = base.cube(f"StoreSign_{idx}", (x, y, z), (1.2, 0.08, 0.35), sign_red, 0.05)
        added.append(sign)
    # Rooftop silhouettes add depth without increasing the street footprint.
    for idx, (x, y, z) in enumerate(((-22, 7.2, 6.2), (-2, 7.2, 7.0), (13, -7.2, 6.3), (25, -7.2, 7.0))):
        tank = base.cylinder(f"RoofTank_{idx}", (x, y, z), 0.55, 1.0, roof_dark, 16)
        added.append(tank)
    # Small scattered debris gives scale before the staged destruction.
    for idx in range(18):
        x = -14 + (idx * 17 % 29)
        y = -3.8 + ((idx * 11) % 70) / 10
        chip = base.cube(f"StreetLitter_{idx:02d}", (x, y, 0.06), (0.06 + idx % 3 * 0.025, 0.035, 0.025), roof_dark, 0.01)
        chip.rotation_euler[2] = idx * 0.43
        added.append(chip)
    for obj in added:
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        city.objects.link(obj)


def upgrade_athletic_bodies_and_hands():
    """Apply the shared male-base refinement without replacing either character."""
    for body_name in ("Naruto_Body", "OmniMan_Body"):
        base_humanoid.refine_athletic_body(bpy.data.objects[body_name])

    old = bpy.data.collections.get("WWS_HAND_CONTROLS")
    if old:
        for obj in list(old.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(old)
    collection = bpy.data.collections.new("WWS_HAND_CONTROLS")
    SCENE.collection.children.link(collection)
    skin = bpy.data.materials["CHAR_Skin"]
    SCENE.frame_set(1)
    controls = {}
    for fighter, rig_name in (("naruto", "fighter_b_ProductionRig"), ("omniman", "fighter_a_ProductionRig")):
        rig = bpy.data.objects[rig_name]
        for side in ("L", "R"):
            key = f"{fighter}.{side}"
            controls[key] = base_humanoid.create_hand_controls(
                bpy, rig, f"Hand_{side}", f"{fighter}_{side}", skin, collection
            )

    for frame, pose in ((1, "CLOSED_FIST"), (540, "CLOSED_FIST")):
        base_humanoid.set_hand_pose(controls["omniman.L"], pose, frame)
        base_humanoid.set_hand_pose(controls["omniman.R"], pose, frame)
    for frame, pose in ((1, "RELAXED"), (290, "OPEN_PALM"), (305, "OPEN_PALM"), (312, "CLOSED_FIST"), (540, "RELAXED")):
        base_humanoid.set_hand_pose(controls["naruto.L"], pose, frame)
    for frame, pose in (
        (1, "CLOSED_FIST"), (168, "CUPPED"), (238, "RELAXED"),
        (338, "CUPPED"), (371, "CUPPED"), (380, "OPEN_PALM"), (400, "RELAXED"), (540, "RELAXED"),
    ):
        base_humanoid.set_hand_pose(controls["naruto.R"], pose, frame)
    for control in controls.values():
        for obj in [control.palm, *control.fingers, control.thumb]:
            action = obj.animation_data.action if obj.animation_data else None
            if action:
                for curve in action.fcurves:
                    for keyframe in curve.keyframe_points:
                        keyframe.interpolation = "BEZIER"
                        keyframe.handle_left_type = keyframe.handle_right_type = "AUTO_CLAMPED"
    return controls


def create_proxy_material(name, color):
    material = base.mat(name, color, roughness=0.35, emission=color, alpha=0.28)
    return material


def create_collision_proxies():
    collection = bpy.data.collections.new("WWS_COLLISION_PROXIES")
    SCENE.collection.children.link(collection)
    materials = {
        "omniman": create_proxy_material("Proxy_Omni", (1.0, 0.08, 0.04)),
        "naruto": create_proxy_material("Proxy_Naruto", (0.05, 0.6, 1.0)),
        "environment": create_proxy_material("Proxy_Environment", (1.0, 0.72, 0.02)),
    }
    rigs = {
        "omniman": bpy.data.objects["fighter_a_ProductionRig"],
        "naruto": bpy.data.objects["fighter_b_ProductionRig"],
    }
    SCENE.frame_set(1)
    for fighter, rig in rigs.items():
        for role, (bone_name, radius) in PROXY_SPECS.items():
            bone = rig.pose.bones[bone_name]
            a = rig.matrix_world @ bone.head
            b = rig.matrix_world @ bone.tail
            center = a.lerp(b, 0.5)
            length = max(0.08, (b - a).length)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, location=center)
            obj = bpy.context.object
            obj.name = f"COLLISION_{fighter}_{role}"
            obj.data.materials.append(materials[fighter])
            obj.display_type = "WIRE"
            obj.show_in_front = True
            obj.scale = (radius, length * 0.5 + radius * 0.4, radius)
            obj.rotation_mode = "QUATERNION"
            obj.rotation_quaternion = (rig.matrix_world @ bone.matrix).to_quaternion()
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            world = obj.matrix_world.copy()
            obj.parent = rig
            obj.parent_type = "BONE"
            obj.parent_bone = bone_name
            obj.matrix_world = world
            obj["wws_proxy_role"] = role
            obj["wws_fighter"] = fighter
            for source in list(obj.users_collection):
                source.objects.unlink(obj)
            collection.objects.link(obj)
    environment_names = (
        "CrashWall_Intact", "ParkedCar_", "ParkedCarCabin_", "StreetlightPole_",
        "FireHydrant", "TrashContainer_", "TrafficPole",
    )
    for source in list(bpy.data.objects):
        if not any(source.name == token or source.name.startswith(token) for token in environment_names):
            continue
        bpy.ops.mesh.primitive_cube_add(location=source.matrix_world.translation)
        proxy = bpy.context.object
        proxy.name = "COLLISION_ENV_" + source.name
        proxy.data.materials.append(materials["environment"])
        proxy.display_type = "WIRE"
        proxy.show_in_front = True
        proxy.dimensions = source.dimensions
        proxy.rotation_mode = source.rotation_mode
        proxy.rotation_euler = source.rotation_euler
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        proxy["wws_environment_source"] = source.name
        for owner in list(proxy.users_collection):
            owner.objects.unlink(proxy)
        collection.objects.link(proxy)
    collection.hide_render = True
    collection.hide_viewport = True
    return collection


def capsule_aabb_penetration(cap: Capsule, obj) -> float:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    lower = Vector((min(p.x for p in corners), min(p.y for p in corners), min(p.z for p in corners)))
    upper = Vector((max(p.x for p in corners), max(p.y for p in corners), max(p.z for p in corners)))
    deepest = 0.0
    for step in range(7):
        point = cap.a.lerp(cap.b, step / 6)
        closest = Vector((
            min(max(point.x, lower.x), upper.x),
            min(max(point.y, lower.y), upper.y),
            min(max(point.z, lower.z), upper.z),
        ))
        distance = (point - closest).length
        if distance:
            deepest = max(deepest, cap.radius - distance)
        else:
            face_clearance = min(
                point.x - lower.x, upper.x - point.x,
                point.y - lower.y, upper.y - point.y,
                point.z - lower.z, upper.z - point.z,
            )
            deepest = max(deepest, cap.radius + face_clearance)
    return deepest


def environment_collisions(frame, fighter: str, caps: list[Capsule], environment_objects):
    issues = []
    intentional_wall = fighter == "omniman" and 72 <= frame <= 145
    for cap in caps:
        # Foot capsules are centered on the ankle/foot bone and deliberately
        # extend around the sole. Bone endpoints provide the meaningful floor
        # test and avoid reporting a correctly planted foot as buried geometry.
        lowest = min(cap.a.z, cap.b.z) if cap.role.startswith("foot") else min(cap.a.z, cap.b.z) - cap.radius
        if lowest < -TOLERANCE:
            issues.append({
                "frame": frame, "objects": [fighter, "ground"], "proxy_pair": [cap.role, "ground"],
                "penetration_depth": round(-lowest, 5), "intentional": False,
            })
        # Crash facade plane; only the staged impact window is intentional.
        for point in (cap.a, cap.b):
            if -13.2 <= point.x <= -7.8 and 0 <= point.z <= 4.0:
                depth = point.y + cap.radius - 6.10
                if depth > TOLERANCE:
                    issues.append({
                        "frame": frame, "objects": [fighter, "CrashWall"], "proxy_pair": [cap.role, "wall"],
                        "penetration_depth": round(depth, 5), "intentional": intentional_wall,
                    })
                    break
        for obj in environment_objects:
            if obj.hide_render or obj.name.startswith("CrashWall_"):
                continue
            penetration = capsule_aabb_penetration(cap, obj)
            if penetration > TOLERANCE:
                issues.append({
                    "frame": frame,
                    "objects": [fighter, obj.name],
                    "proxy_pair": [cap.role, "environment_aabb"],
                    "penetration_depth": round(penetration, 5),
                    "intentional": False,
                    "category": "environment",
                })
    return issues


def collision_report(surface_contact, clearance_corrections):
    omni_rig = bpy.data.objects["fighter_a_ProductionRig"]
    naruto_rig = bpy.data.objects["fighter_b_ProductionRig"]
    issues = []
    max_body = 0.0
    environment_objects = [
        obj for obj in bpy.data.objects
        if obj.name.startswith(("ParkedCar_", "ParkedCarCabin_", "StreetlightPole_", "TrashContainer_"))
        or obj.name in {"FireHydrant", "TrafficPole"}
    ]
    for frame in range(1, END + 1):
        SCENE.frame_set(frame)
        bpy.context.view_layer.update()
        omni = fighter_capsules(omni_rig, "omniman")
        naruto = fighter_capsules(naruto_rig, "naruto")
        for a in omni:
            for b in naruto:
                penetration = a.radius + b.radius - segment_distance(a.a, a.b, b.a, b.b)
                if penetration <= TOLERANCE:
                    continue
                intentional = intended_contact(frame, a, b)
                category = "body_body" if a.role in {"chest", "pelvis", "head"} and b.role in {"chest", "pelvis", "head"} else "limb_body"
                if category == "body_body" and not intentional:
                    max_body = max(max_body, penetration)
                issues.append({
                    "frame": frame, "objects": [a.fighter, b.fighter],
                    "proxy_pair": [a.role, b.role], "category": category,
                    "penetration_depth": round(penetration, 5), "intentional": intentional,
                })
        issues.extend(environment_collisions(frame, "omniman", omni, environment_objects))
        issues.extend(environment_collisions(frame, "naruto", naruto, environment_objects))
    unintentional = [item for item in issues if not item["intentional"]]
    worst = sorted(unintentional, key=lambda item: item["penetration_depth"], reverse=True)[:24]
    report = {
        "schema_version": 1,
        "frames_evaluated": END,
        "fps": FPS,
        "tolerance": TOLERANCE,
        "presentation_only": True,
        "environment_proxies_evaluated": [obj.name for obj in environment_objects] + ["ground", "CrashWall_Intact"],
        "surface_contact_world": [round(value, 5) for value in surface_contact],
        "clearance_solver": {
            "correction_count": len(clearance_corrections),
            "total_lateral_shift": round(sum(item["lateral_shift"] for item in clearance_corrections), 5),
            "corrections": clearance_corrections,
        },
        "intentional_contact_windows": [
            {"frames": [296, 303], "pair": ["naruto hand.L", "omniman hand/forearm.L"], "purpose": "open-hand parry"},
            {"frames": [306, 322], "pair": ["naruto hand/forearm.R", "omniman chest/forearm.L"], "event": "event-000244"},
            {"frames": [328, 338], "pair": ["naruto left arm", "omniman left guard"], "purpose": "guard redirection"},
            {"frames": [354, 359], "pair": ["naruto hand.R", "omniman left guard"], "purpose": "guard bypass"},
            {"frames": [363, 371], "pair": ["naruto hand.R", "omniman chest"], "event": "event-000221"},
        ],
        "issue_count": len(issues),
        "unintentional_issue_count": len(unintentional),
        "max_unintentional_body_penetration": round(max_body, 5),
        "worst_frames": sorted({item["frame"] for item in worst})[:12],
        "worst_unintentional": worst,
        "all_issues": issues,
    }
    path = OUTPUT / "review/collision_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def camera_report():
    rigs = {
        "omniman": bpy.data.objects["fighter_a_ProductionRig"],
        "naruto": bpy.data.objects["fighter_b_ProductionRig"],
    }
    markers = sorted((m for m in SCENE.timeline_markers if m.camera), key=lambda m: m.frame)
    samples = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].frame - 1 if index + 1 < len(markers) else END
        frame = (marker.frame + end) // 2
        SCENE.frame_set(frame)
        camera = marker.camera
        fighters = {}
        for fighter, rig in rigs.items():
            points = []
            for role in ("head", "chest", "pelvis", "hand.L", "hand.R", "foot.L", "foot.R"):
                cap = capsule_for(rig, fighter, role)
                for world in (cap.a, cap.b):
                    ndc = world_to_camera_view(SCENE, camera, world)
                    points.append(ndc)
            visible = [p for p in points if p.z > 0]
            xs = [p.x for p in visible]
            ys = [p.y for p in visible]
            bbox = [min(xs), min(ys), max(xs), max(ys)] if xs else [0, 0, 0, 0]
            area = max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])
            fighters[fighter] = {
                "visible": bool(visible and bbox[2] >= 0 and bbox[0] <= 1 and bbox[3] >= 0 and bbox[1] <= 1),
                "normalized_bbox": [round(v, 4) for v in bbox],
                "frame_area": round(area, 4),
                "excessive_frame_area": area > 0.72,
            }
        a_box = fighters["omniman"]["normalized_bbox"]
        b_box = fighters["naruto"]["normalized_bbox"]
        overlap_w = max(0.0, min(a_box[2], b_box[2]) - max(a_box[0], b_box[0]))
        overlap_h = max(0.0, min(a_box[3], b_box[3]) - max(a_box[1], b_box[1]))
        overlap = overlap_w * overlap_h
        smaller = min(fighters["omniman"]["frame_area"], fighters["naruto"]["frame_area"])
        occlusion_ratio = overlap / smaller if smaller else 0.0
        samples.append({
            "shot": marker.name, "start": marker.frame, "end": end, "sample_frame": frame,
            "fighters": fighters,
            "bbox_occlusion_ratio": round(occlusion_ratio, 4),
            "potential_subject_blocking": occlusion_ratio > 0.82,
        })

    limb_checks = []
    for frame, fighter, role, label in (
        (289, "omniman", "hand.R", "blitz miss"),
        (316, "naruto", "hand.R", "counter"),
        (365, "naruto", "hand.R", "Rasengan impact"),
    ):
        SCENE.frame_set(frame)
        camera = max((m for m in markers if m.frame <= frame), key=lambda m: m.frame).camera
        point = capsule_for(rigs[fighter], fighter, role).a
        ndc = world_to_camera_view(SCENE, camera, point)
        limb_checks.append({
            "frame": frame, "label": label, "fighter": fighter, "role": role,
            "normalized_position": [round(ndc.x, 4), round(ndc.y, 4), round(ndc.z, 4)],
            "in_frame": ndc.z > 0 and 0 <= ndc.x <= 1 and 0 <= ndc.y <= 1,
        })
    report = {
        "schema_version": 1,
        "checks": samples,
        "important_limb_checks": limb_checks,
        "method": "bone-proxy camera projection with 2D overlap warning; visual occlusion confirmed by review contact sheets",
    }
    (OUTPUT / "review/camera_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def mesh_level_report():
    """Run exact evaluated-mesh checks over the critical contact interval.

    BVH triangle overlap is intentionally limited to selected frames. It catches
    visible skinned-mesh intersections that the lightweight capsule pass can miss
    without turning the presentation layer into a general collision engine.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    naruto_body = bpy.data.objects["Naruto_Body"]
    omni_body = bpy.data.objects["OmniMan_Body"]
    cape = bpy.data.objects.get("OmniMan_Cape")
    naruto_rig = bpy.data.objects["fighter_b_ProductionRig"]
    omni_rig = bpy.data.objects["fighter_a_ProductionRig"]
    key_frames = [296, 303, 316, 332, 336, 357, 360, 362, 365, 368, 371, 375, 379]

    def evaluated_world_bvh(obj):
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        matrix = evaluated.matrix_world
        vertices = [matrix @ vertex.co for vertex in mesh.vertices]
        polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
        bvh = BVHTree.FromPolygons(vertices, polygons, all_triangles=False, epsilon=0.0005)
        evaluated.to_mesh_clear()
        return bvh

    checks = []
    for frame in key_frames:
        SCENE.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph.update()
        naruto_bvh = evaluated_world_bvh(naruto_body)
        omni_bvh = evaluated_world_bvh(omni_body)
        body_pairs = naruto_bvh.overlap(omni_bvh)
        hand = capsule_for(naruto_rig, "naruto", "hand.R")
        hand_center = hand.a.lerp(hand.b, 0.5)
        nearest = omni_bvh.find_nearest(hand_center)
        hand_surface_distance = float(nearest[3]) if nearest else None
        cape_omni_pairs = []
        cape_naruto_pairs = []
        if cape and not cape.hide_render:
            cape_bvh = evaluated_world_bvh(cape)
            cape_omni_pairs = cape_bvh.overlap(omni_bvh)
            cape_naruto_pairs = cape_bvh.overlap(naruto_bvh)
        checks.append({
            "frame": frame,
            "phase": (
                "parry" if frame <= 303 else "counter" if frame <= 316 else
                "guard_redirect" if frame <= 336 else "missed_counter" if frame <= 360 else
                "rasengan_approach" if frame <= 362 else "rasengan_contact" if frame <= 371 else
                "release"
            ),
            "body_triangle_overlap_pairs": len(body_pairs),
            "body_mesh_intersection": bool(body_pairs),
            "rasengan_hand_to_omni_surface_distance": round(hand_surface_distance, 5) if hand_surface_distance is not None else None,
            "cape_omni_overlap_pairs": len(cape_omni_pairs),
            "cape_naruto_overlap_pairs": len(cape_naruto_pairs),
            "cape_hits_opponent": bool(cape_naruto_pairs),
        })
    payload = {
        "schema_version": 1,
        "method": "evaluated modifier-stack BVH triangle overlap plus nearest-surface distance",
        "frames": checks,
        "unacceptable_body_intersection_frames": [item["frame"] for item in checks if item["body_mesh_intersection"]],
        "cape_opponent_intersection_frames": [item["frame"] for item in checks if item["cape_hits_opponent"]],
    }
    (OUTPUT / "review/mesh_collision_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def add_static_contact_camera():
    cam, target = base.camera("V2_RasenganContactReview", (-2.8, -5.8, 2.0), 58, (-0.15, 0.4, 1.55))
    base.camera_key(cam, target, 270, (-3.1, -5.8, 2.0), (-1.6, 0.0, 1.5), 52)
    base.camera_key(cam, target, 365, (-2.6, -5.6, 1.85), (-0.05, 0.52, 1.62), 62)
    base.camera_key(cam, target, 405, (-2.2, -5.4, 2.05), (2.8, 1.1, 2.4), 48)
    return cam


def sound_manifest():
    cues = [
        (1.60, "flight_launch", "omniman"), (1.95, "flight_whoosh", "omniman"),
        (2.25, "melee_swish_miss", "omniman"), (3.66, "concrete_break", "environment"),
        (3.72, "glass_break", "environment"), (6.15, "rasengan_charge", "naruto"),
        (8.90, "melee_swish", "omniman"), (10.50, "punch", "naruto"),
        (10.78, "block", "omniman"), (11.55, "rasengan_movement", "naruto"),
        (12.17, "rasengan_impact", "naruto"), (12.47, "shockwave", "environment"),
        (12.58, "debris", "environment"), (14.20, "flight_whoosh", "omniman"),
        (14.95, "flight_brake", "omniman"), (16.10, "debris_settle", "environment"),
    ]
    payload = {
        "schema_version": 1, "fps": FPS, "audio_implemented": False,
        "cues": [{"time_seconds": time, "frame": round(time * FPS), "cue": cue, "source": source} for time, cue, source in cues],
    }
    (OUTPUT / "review/sound-cues.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def configure_lookdev():
    # Blender's Eevee settings moved between 4.x point releases.  Keep this
    # deliberately conservative so the same scene builds on supported LTS
    # versions instead of depending on removed GTAO properties.
    try:
        SCENE.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    if hasattr(SCENE, "eevee"):
        SCENE.eevee.taa_render_samples = 2
        SCENE.eevee.taa_samples = 2
        SCENE.eevee.volumetric_samples = 2
    if hasattr(SCENE.render, "use_motion_blur"):
        SCENE.render.use_motion_blur = True
        SCENE.render.motion_blur_shutter = 0.34


def save_manifest(report, mesh_report):
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    manifest.update({
        "milestone": "first_production_fight_v2_spatial_integrity",
        "parent_output": "../first_production_fight",
        "collision_report": "review/collision_report.json",
        "camera_report": "review/camera_report.json",
        "mesh_collision_report": "review/mesh_collision_report.json",
        "collision_debug": "renders/collision-debug/fight.mp4",
        "clean_motion_preview": "renders/clean-motion/fight.mp4",
        "quality_preview": "renders/quality-preview/fight.mp4",
        "rasengan_contact_review": "review/rasengan-contact.mp4",
        "collision_tolerance": TOLERANCE,
        "max_unintentional_body_penetration": report["max_unintentional_body_penetration"],
        "mesh_intersection_frames": mesh_report["unacceptable_body_intersection_frames"],
    })
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def set_vfx_hidden(hidden: bool):
    states = []
    tokens = ("Dust", "ImpactArc", "Shockwave", "RoadCrack", "Crater", "WallDebris")
    for obj in bpy.data.objects:
        if any(token in obj.name for token in tokens):
            states.append((obj, obj.hide_render))
            obj.hide_render = hidden
    return states


def restore_hidden(states):
    for obj, hidden in states:
        obj.hide_render = hidden


def render(path: Path, *, width: int, height: int, engine: str, start=1, end=END, camera=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    SCENE.frame_start, SCENE.frame_end = start, end
    SCENE.render.resolution_x, SCENE.render.resolution_y = width, height
    SCENE.render.resolution_percentage = 100
    SCENE.render.fps = FPS
    SCENE.render.engine = engine
    if camera:
        SCENE.camera = camera
    if engine == "BLENDER_WORKBENCH":
        SCENE.display.shading.light = "STUDIO"
        SCENE.display.shading.studio_light = "rim.sl"
        SCENE.display.shading.color_type = "MATERIAL"
        SCENE.display.shading.show_shadows = True
        SCENE.display.shading.show_cavity = True
        SCENE.display.shading.cavity_type = "WORLD"
    SCENE.render.image_settings.file_format = "FFMPEG"
    SCENE.render.ffmpeg.format = "MPEG4"
    SCENE.render.ffmpeg.codec = "H264"
    SCENE.render.ffmpeg.constant_rate_factor = "MEDIUM"
    SCENE.render.filepath = str(path)
    bpy.ops.render.render(animation=True)


def render_outputs(proxy_collection, contact_camera):
    all_outputs = "--render-all" in sys.argv
    if all_outputs or "--render-debug" in sys.argv:
        proxy_collection.hide_render = False
        proxy_collection.hide_viewport = False
        state = set_vfx_hidden(True)
        render(OUTPUT / "renders/collision-debug/fight.mp4", width=360, height=640, engine="BLENDER_WORKBENCH")
        restore_hidden(state)
        proxy_collection.hide_render = True
        proxy_collection.hide_viewport = True
    if all_outputs or "--render-clean" in sys.argv:
        state = set_vfx_hidden(True)
        render(OUTPUT / "renders/clean-motion/fight.mp4", width=360, height=640, engine="BLENDER_WORKBENCH")
        restore_hidden(state)
    if all_outputs or "--render-contact" in sys.argv:
        state = set_vfx_hidden(True)
        markers = [(m.name, m.frame, m.camera) for m in SCENE.timeline_markers]
        for marker in list(SCENE.timeline_markers):
            SCENE.timeline_markers.remove(marker)
        render(OUTPUT / "review/rasengan-contact.mp4", width=540, height=720, engine="BLENDER_WORKBENCH", start=270, end=405, camera=contact_camera)
        for name, frame, camera in markers:
            marker = SCENE.timeline_markers.new(name, frame=frame)
            marker.camera = camera
        restore_hidden(state)
    if all_outputs or "--render-quality" in sys.argv:
        proxy_collection.hide_render = True
        SCENE.camera = bpy.data.objects["SHOT01_LowFaceoff"]
        render(OUTPUT / "renders/quality-preview/fight.mp4", width=720, height=1280, engine="BLENDER_EEVEE_NEXT")


def main():
    # Build the existing character fight into a new directory, without rendering it.
    original_argv = list(sys.argv)
    sys.argv = [arg for arg in sys.argv if not arg.startswith("--render")]
    base.main()
    sys.argv = original_argv
    upgrade_athletic_bodies_and_hands()
    restage_close_exchange()
    separate_omniman_reaction_arm()
    improve_flight_and_cape()
    refine_cameras()
    city_polish()
    configure_lookdev()
    proxies = create_collision_proxies()
    contact_camera = add_static_contact_camera()
    surface = refine_rasengan_tangent()
    corrections = apply_clearance_solver()
    report = collision_report(surface, corrections)
    mesh_report = mesh_level_report()
    camera_report()
    sound_manifest()
    save_manifest(report, mesh_report)
    builder_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    SCENE["wws_spatial_integrity_pass"] = True
    SCENE["wws_collision_tolerance"] = TOLERANCE
    SCENE["wws_collision_report"] = "review/collision_report.json"
    SCENE["wws_simulation_unchanged"] = True
    SCENE["wws_builder_sha256"] = builder_hash
    SCENE["wws_build_utc"] = datetime.now(timezone.utc).isoformat()
    SCENE["wws_frame360_correction"] = "naruto_root=(-0.82,-0.78,0.03),yaw=0.12"
    SCENE.frame_start, SCENE.frame_end = 1, END
    SCENE.render.resolution_x, SCENE.render.resolution_y = 360, 640
    SCENE.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "scene.blend"))
    render_outputs(proxies, contact_camera)
    SCENE.frame_start, SCENE.frame_end = 1, END
    SCENE.render.resolution_x, SCENE.render.resolution_y = 360, 640
    SCENE.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "scene.blend"))
    print(json.dumps({
        "output": str(OUTPUT), "frames": END,
        "collision_issues": report["issue_count"],
        "unintentional_issues": report["unintentional_issue_count"],
        "max_unintentional_body_penetration": report["max_unintentional_body_penetration"],
        "worst_frames": report["worst_frames"],
    }, indent=2))


if __name__ == "__main__":
    main()
