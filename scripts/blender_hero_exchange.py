"""Build a four-second paired-animation study from the validated Motion Lab.

The simulator data and source scene are immutable inputs.  This script replaces
the central chain of independent presentation clips with two deliberately
synchronized Blender Actions.  Root placement, short support-foot pins and the
final Rasengan tangent are the only procedural adaptations.
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
from mathutils import Euler, Vector

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/combat_motion_lab_astra"
OUTPUT = ROOT / "outputs/combat_motion_lab_hero_exchange"
FPS = 30
END = 120
SOURCE_FRAMES = (1, 268, 278, 286, 294, 303, 316, 324, 332, 342, 350, 358, 365, 368, 371, 379, 390)

sys.path.insert(0, str(ROOT / "scripts"))
import blender_combat_motion_lab as motion_lab


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_collision_module():
    path = ROOT / "scripts/blender_first_production_fight_v2.py"
    spec = importlib.util.spec_from_file_location("hero_collision_math", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def sampled_pose(rig, frames):
    scene = bpy.context.scene
    out = {}
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        out[frame] = {bone.name: bone.rotation_quaternion.copy() for bone in rig.pose.bones}
    return out


def sampled_root(rig, frames):
    scene = bpy.context.scene
    out = {}
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        out[frame] = (rig.location.copy(), rig.rotation_euler.copy())
    return out


# One authored paired performance.  The source frame is a blocking reference,
# while target timing and root placement are unique to this exchange.
BEATS = (
    (1, 1, 1, "ready"),
    (8, 278, 1, "omni_attack_anticipation"),
    (16, 286, 286, "omni_attack_naruto_outside_slip"),
    (23, 294, 294, "attack_overshoot"),
    (31, 316, 303, "naruto_counter_load"),
    (38, 316, 316, "naruto_counter_contact"),
    (47, 324, 324, "omni_parry_guard"),
    (56, 332, 332, "naruto_angle_change"),
    (66, 350, 350, "rasengan_entry_load"),
    (76, 350, 350, "rasengan_acceleration"),
    # Naruto keeps the upright source-350 torso through the hero contact.  The
    # final hand placement comes from a short tangent IK ramp, not waist folding.
    (85, 365, 350, "rasengan_contact"),
    (88, 368, 350, "impact_hold"),
    (93, 371, 350, "release"),
    (106, 379, 390, "compressed_reaction_separation"),
    (120, 390, 390, "recovery"),
)

# The roots preserve clear three-quarter spacing and are deliberately authored;
# no per-frame clearance solver is run afterward.
ROOTS = {
    "fighter_a": {
        1: (-3.10, .95, .05), 8: (-3.04, .94, .05),
        16: (-1.82, .64, .05), 23: (-1.38, .58, .05),
        31: (-1.31, .75, .05), 38: (-1.18, .80, .05),
        47: (-.92, .55, .05), 56: (-.66, .63, .05),
        66: (-.40, .65, .05), 76: (-.14, .60, .05),
        85: (.10, .54, .05), 88: (.10, .54, .05), 93: (.10, .54, .05),
        106: (1.20, .90, .52), 120: (1.92, 1.02, .74),
    },
    "fighter_b": {
        1: (-.18, -.92, .03), 8: (-.20, -.92, .03),
        16: (-1.05, -1.43, .06), 23: (-1.16, -1.39, .08),
        31: (-.82, -.70, .05), 38: (-.68, -.39, .04),
        47: (-.70, -.43, .03), 56: (-.34, -.71, .03),
        66: (-.50, -.62, .03), 76: (-.47, -.38, .03),
        85: (-.45, -.24, .03), 88: (-.45, -.24, .03), 93: (-.45, -.24, .03),
        106: (-.26, -.18, .03), 120: (-.02, -.12, .03),
    },
}


def body_arrival_offset(bone_name: str, beat_name: str) -> int:
    """Make force move from support leg to hand without dense corrective keys."""
    if beat_name in {"rasengan_contact", "impact_hold", "release"}:
        order = {
            "thigh.L": -5, "thigh.R": -5, "shin.L": -5, "shin.R": -5,
            "pelvis": -4, "spine": -3, "chest": -2,
            "clavicle.L": -2, "clavicle.R": -2,
            "upper_arm.L": -1, "upper_arm.R": -1,
        }
        return order.get(bone_name, 0)
    if any(token in beat_name for token in ("attack", "counter", "parry", "angle", "acceleration")):
        order = {
            "thigh.L": -4, "thigh.R": -4, "shin.L": -4, "shin.R": -4,
            "pelvis": -3, "spine": -2, "chest": -1,
            "clavicle.L": 0, "clavicle.R": 0,
            "upper_arm.L": 1, "upper_arm.R": 1,
            "forearm.L": 2, "forearm.R": 2,
            "hand.L": 3, "hand.R": 3,
        }
        return order.get(bone_name, 0)
    return 0


def clean_quaternion(q, bone_name: str, fighter: str, beat_name: str):
    """Retain the source silhouette while preventing stacked hinge folding."""
    e = q.to_euler("XYZ")
    if bone_name in {"pelvis", "spine", "chest"}:
        # The old clips stack almost the same bend through three joints.  A
        # smaller distributed bend keeps the ribcage over the pelvis.
        scale = {"pelvis": .64, "spine": .70, "chest": .76}[bone_name]
        e.x *= scale
        e.y *= scale
        e.z *= .88
    elif bone_name.startswith("clavicle"):
        e.x *= .82
        e.y *= .82
    elif bone_name.startswith("hand"):
        # Hands follow the forearm arc instead of independently windmilling.
        e.x *= .38
        e.y *= .38
        e.z *= .38
    elif bone_name.startswith("forearm"):
        e.y *= .72
    if beat_name == "impact_hold" and fighter == "fighter_a" and bone_name in {"spine", "chest"}:
        e.x -= .10 if bone_name == "spine" else .16
    return e.to_quaternion()


def clear_animation(rig):
    if not rig.animation_data:
        rig.animation_data_create()
    for track in rig.animation_data.nla_tracks:
        track.mute = True
    rig.animation_data.action = None


def build_paired_action(rig, fighter: str, cache):
    clear_animation(rig)
    action = bpy.data.actions.new("HERO_PAIRED_" + ("OMNI" if fighter == "fighter_a" else "NARUTO"))
    action["wws_authored_performance"] = True
    action["wws_source_strategy"] = "hand-authored paired blocking from validated production-rig pose references"
    action["wws_procedural_pose_generation"] = False
    rig.animation_data.action = action
    previous = {}
    inserted = set()
    source_index = 1 if fighter == "fighter_a" else 2
    for beat in BEATS:
        target, source_a, source_b, name = beat
        source = beat[source_index]
        for bone in rig.pose.bones:
            frame = max(1, min(END, target + body_arrival_offset(bone.name, name)))
            key = (bone.name, frame)
            if key in inserted:
                continue
            inserted.add(key)
            q = clean_quaternion(cache[source][bone.name], bone.name, fighter, name)
            if bone.name in previous and previous[bone.name].dot(q) < 0:
                q.negate()
            previous[bone.name] = q.copy()
            bone.rotation_mode = "QUATERNION"
            bone.rotation_quaternion = q
            bone.keyframe_insert("rotation_quaternion", frame=frame, group=bone.name)
    for frame, location in ROOTS[fighter].items():
        other = ROOTS["fighter_b" if fighter == "fighter_a" else "fighter_a"][frame]
        yaw = math.atan2(other[1] - location[1], other[0] - location[0])
        rig.location = location
        rig.rotation_mode = "XYZ"
        rig.rotation_euler = (0, 0, yaw)
        rig.keyframe_insert("location", frame=frame, group="ROOT_MOTION")
        rig.keyframe_insert("rotation_euler", frame=frame, group="ROOT_MOTION")
    hold_frames = {85, 88}
    for curve in action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = "CONSTANT" if round(key.co.x) in hold_frames else "BEZIER"
            if key.interpolation == "BEZIER":
                key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"
    return action


def remove_old_active_constraints():
    for rig_name in ("fighter_a_Rig", "fighter_b_Rig", "fighter_a_ProductionRig", "fighter_b_ProductionRig"):
        rig = bpy.data.objects[rig_name]
        for bone in rig.pose.bones:
            for constraint in bone.constraints:
                if constraint.name.startswith(("ASTRA ", "Procedural contact", "ML ")):
                    constraint.mute = True


def add_foot_pin(fighter: str, side: str, start: int, end: int, collection, records):
    rig = bpy.data.objects[fighter + "_ProductionRig"]
    shin = rig.pose.bones["LowerLeg_" + side]
    foot = rig.pose.bones["Foot_" + side]
    bpy.context.scene.frame_set(start)
    bpy.context.view_layer.update()
    target = bpy.data.objects.new(f"HERO_{fighter}_foot_{side}_{start:03d}", None)
    collection.objects.link(target)
    target.location = rig.matrix_world @ shin.tail
    target.rotation_mode = "QUATERNION"
    target.rotation_quaternion = (rig.matrix_world @ foot.matrix).to_quaternion()
    ik = shin.constraints.new("IK")
    ik.name = f"HERO support {start}-{end}"
    ik.target = target
    ik.chain_count = 2
    ik.use_stretch = False
    sole = foot.constraints.new("COPY_ROTATION")
    sole.name = f"HERO sole {start}-{end}"
    sole.target = target
    for constraint in (ik, sole):
        for frame, value in ((1, 0), (max(1, start - 2), 0), (start, 1), (end, 1), (end + 3, 0), (END, 0)):
            constraint.influence = value
            constraint.keyframe_insert("influence", frame=frame)
    records.append({"fighter": fighter, "side": side, "frames": [start, end], "target": [round(x, 5) for x in target.location]})


def add_support_pins():
    collection = bpy.data.collections.new("HERO_FOOT_PINS")
    bpy.context.scene.collection.children.link(collection)
    records = []
    # Only lock during actual loading/contact holds.  Travel phases remain authored.
    for fighter, side, start, end in (
        ("fighter_a", "L", 1, 8), ("fighter_a", "R", 30, 36), ("fighter_a", "L", 45, 53),
        ("fighter_b", "L", 1, 10), ("fighter_b", "R", 28, 35), ("fighter_b", "L", 44, 52),
        ("fighter_b", "R", 62, 70), ("fighter_b", "L", 82, 89),
    ):
        add_foot_pin(fighter, side, start, end, collection, records)
    return records


def add_rasengan_contact(collision):
    source = bpy.data.objects["fighter_b_Rig"]
    target_rig = bpy.data.objects["fighter_a_ProductionRig"]
    control_collection = bpy.data.collections.new("HERO_CONTACT_CONTROLS")
    bpy.context.scene.collection.children.link(control_collection)
    control = bpy.data.objects.new("HERO_RasenganContact", None)
    control_collection.objects.link(control)
    forearm = source.pose.bones["forearm.R"]
    ik = forearm.constraints.new("IK")
    ik.name = "HERO tangent contact"
    ik.target = control
    ik.chain_count = 2
    ik.use_stretch = False
    contact_points = {}
    for frame in (68, 74, 78, 81, 83, 85, 88, 90, 93, 97):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        chest = collision.capsule_for(target_rig, "omniman", "chest")
        center = chest.a.lerp(chest.b, .50)
        naruto = Vector(ROOTS["fighter_b"][min(ROOTS["fighter_b"], key=lambda f: abs(f-frame))])
        outward = naruto - center
        outward.z = 0
        if outward.length < 1e-6:
            outward = Vector((-1, 0, 0))
        outward.normalize()
        if frame < 85:
            extra = (85 - frame) * .035
            z = -.18 + (frame - 68) * .009
        elif frame <= 88:
            extra = 0
            z = 0
        else:
            extra = (frame - 88) * .055
            z = -(frame - 88) * .018
        point = center + outward * (chest.radius + .025 + extra) + Vector((0, 0, z))
        control.location = point
        control.keyframe_insert("location", frame=frame)
        contact_points[frame] = [round(v, 5) for v in point]
    for frame, value in ((1, 0), (74, 0), (79, .08), (82, .22), (84, .55), (85, 1), (88, 1), (90, .55), (93, .12), (97, 0), (END, 0)):
        ik.influence = value
        ik.keyframe_insert("influence", frame=frame)
    for curve in control.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = "BEZIER"
            key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"
    return control, ik, contact_points


def add_short_contact(collision, *, name, source_fighter, source_forearm, target_fighter,
                      target_role, frames, collection, wrist_compensation=0.0):
    """Add a narrow synchronized hand/guard contact without driving the beat."""
    source = bpy.data.objects[source_fighter + "_Rig"]
    target = bpy.data.objects[target_fighter + "_ProductionRig"]
    source_label = "naruto" if source_fighter == "fighter_b" else "omniman"
    target_label = "naruto" if target_fighter == "fighter_b" else "omniman"
    control = bpy.data.objects.new("HERO_" + name, None)
    collection.objects.link(control)
    constraint = source.pose.bones[source_forearm].constraints.new("IK")
    constraint.name = "HERO " + name
    constraint.target = control
    constraint.chain_count = 2
    constraint.use_stretch = False
    start, contact, release = frames
    points = {}
    for frame in (start, contact - 2, contact, contact + 2, release):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        cap = collision.capsule_for(target, target_label, target_role)
        center = cap.a.lerp(cap.b, .5)
        source_rig = bpy.data.objects[source_fighter + "_ProductionRig"]
        chest = collision.capsule_for(source_rig, source_label, "chest")
        source_center = chest.a.lerp(chest.b, .5)
        outward = source_center - center
        if outward.length < 1e-6:
            outward = Vector((-1, 0, 0))
        outward.normalize()
        extra = abs(frame - contact) * .035
        # The IK effector is the wrist/forearm tail while the validation proxy
        # is centered in the hand.  Compensation places the hand surface, not
        # the wrist pivot, at the intended guard surface.
        point = center + outward * (cap.radius + .04 + extra - wrist_compensation)
        control.location = point
        control.keyframe_insert("location", frame=frame)
        points[frame] = [round(v, 5) for v in point]
    for frame, value in ((1, 0), (start, 0), (contact - 2, .35), (contact, 1), (contact + 2, .65), (release, 0), (END, 0)):
        constraint.influence = value
        constraint.keyframe_insert("influence", frame=frame)
    return {"name": name, "frames": list(frames), "points": points, "max_influence": 1.0, "wrist_compensation": wrist_compensation}


def add_exchange_contacts(collision):
    collection = bpy.data.collections.get("HERO_CONTACT_CONTROLS")
    return [
        add_short_contact(
            collision, name="NarutoCounterToGuard", source_fighter="fighter_b",
            source_forearm="forearm.R", target_fighter="fighter_a", target_role="forearm.L",
            frames=(32, 38, 43), collection=collection, wrist_compensation=.30,
        ),
        add_short_contact(
            collision, name="NarutoOpenHandRedirect", source_fighter="fighter_b",
            source_forearm="forearm.L", target_fighter="fighter_a", target_role="forearm.L",
            frames=(42, 47, 53), collection=collection, wrist_compensation=.05,
        ),
    ]


def configure_rasengan_marker():
    collection = bpy.data.collections.get("WWS_MOTION_DEBUG_BODY")
    old = bpy.data.objects.get("ML_RasenganSphere")
    if old:
        old.hide_render = True
    mat = motion_lab.material("HERO_RasenganMarkerBlue", (.03, .35, 1, 1))
    marker = motion_lab.sphere("HERO_RasenganMarker", .16, mat, collection)
    carrier = bpy.data.objects["ML_Naruto_hand.R_carrier"]
    marker.parent = carrier
    marker.location = (0, .30, 0)
    marker.hide_render = True
    marker.keyframe_insert("hide_render", frame=1)
    marker.keyframe_insert("hide_render", frame=56)
    marker.hide_render = False
    marker.keyframe_insert("hide_render", frame=57)
    marker.keyframe_insert("hide_render", frame=96)
    marker.hide_render = True
    marker.keyframe_insert("hide_render", frame=97)
    return marker


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_camera(name, location, target, lens, collection, ortho=None):
    data = bpy.data.cameras.new(name + "_DATA")
    camera = bpy.data.objects.new(name, data)
    collection.objects.link(camera)
    camera.location = location
    data.lens = lens
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = ortho
    look_at(camera, target)
    return camera


def configure_review_scene():
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = END
    scene.render.fps = FPS
    scene.render.resolution_x = 360
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    # Keep the debug body and simple floor only.  The milestone deliberately has
    # no cinematic edits, production materials or environment polish.
    for name in ("WWS_MOTION_OVERLAYS",):
        collection = bpy.data.collections.get(name)
        if collection:
            collection.hide_render = True
            collection.hide_viewport = True
    cameras = bpy.data.collections.get("HERO_REVIEW_CAMERAS") or bpy.data.collections.new("HERO_REVIEW_CAMERAS")
    if not cameras.name in scene.collection.children:
        scene.collection.children.link(cameras)
    specs = {
        "three-quarter": ((5.5, -8.5, 3.5), (-.40, -.05, 1.45), 58, None),
        "side": ((-.35, -11.5, 2.7), (-.35, -.05, 1.42), 50, 5.1),
        "front-diagonal": ((-6.4, -7.4, 3.3), (-.35, -.02, 1.45), 55, None),
        "top": ((-.35, -.05, 13.5), (-.35, -.05, 0), 50, 6.6),
    }
    for label, (loc, target, lens, ortho) in specs.items():
        add_camera("HERO_CAM_" + label, loc, target, lens, cameras, ortho)
    scene.camera = bpy.data.objects["HERO_CAM_three-quarter"]
    for marker in scene.timeline_markers:
        marker.camera = scene.camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "rim.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True


def write_provenance(actions, foot_pins, contact_points):
    source_events = SOURCE / "source/events.json"
    source_actions = {}
    for rig_name in ("fighter_a_Rig", "fighter_b_Rig"):
        rig = bpy.data.objects[rig_name]
        source_actions[rig_name] = [
            {"track": track.name, "strip": strip.name, "action": strip.action.name}
            for track in rig.animation_data.nla_tracks for strip in track.strips
        ]
    payload = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "presentation_only": True,
        "source_scene": str(SOURCE / "scene.blend"),
        "source_scene_sha256": digest(SOURCE / "scene.blend"),
        "source_events": str(source_events),
        "source_events_sha256": digest(source_events),
        "source_events_copied_unchanged": digest(source_events) == digest(OUTPUT / "source/events.json"),
        "source_action_inventory": source_actions,
        "source_pose_reference_frames": list(SOURCE_FRAMES),
        "paired_actions": [action.name for action in actions],
        "performance_beats": [{"target_frame": t, "omni_source_reference_frame": sa, "naruto_source_reference_frame": sb, "beat": name} for t, sa, sb, name in BEATS],
        "root_motion": "authored sparse world-space keys; independent of body Actions",
        "procedural_adaptations": {
            "foot_pins": foot_pins,
            "rasengan_contact_points": contact_points,
            "clearance_solver": "disabled; authored poses/roots are validated and conflicts are reported",
        },
        "rig_contract": motion_lab.PRODUCTION_BONES,
        "builder": str(Path(__file__)),
        "builder_sha256": digest(Path(__file__)),
    }
    (OUTPUT / "review/source-action-provenance.json").write_text(json.dumps(payload, indent=2))
    return payload


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for folder in ("source", "review", "renders"):
        (OUTPUT / folder).mkdir(exist_ok=True)
    (OUTPUT / "source/events.json").write_bytes((SOURCE / "source/events.json").read_bytes())
    omni = bpy.data.objects["fighter_a_Rig"]
    naruto = bpy.data.objects["fighter_b_Rig"]
    caches = {"fighter_a": sampled_pose(omni, SOURCE_FRAMES), "fighter_b": sampled_pose(naruto, SOURCE_FRAMES)}
    remove_old_active_constraints()
    actions = [build_paired_action(omni, "fighter_a", caches["fighter_a"]), build_paired_action(naruto, "fighter_b", caches["fighter_b"])]
    foot_pins = add_support_pins()
    collision = load_collision_module()
    _, _, contact_points = add_rasengan_contact(collision)
    contact_points["exchange_contacts"] = add_exchange_contacts(collision)
    configure_rasengan_marker()
    configure_review_scene()
    scene = bpy.context.scene
    scene["wws_hero_exchange"] = True
    scene["wws_source_scene_sha256"] = digest(SOURCE / "scene.blend")
    scene["wws_source_events_sha256"] = digest(OUTPUT / "source/events.json")
    scene["wws_builder_sha256"] = digest(Path(__file__))
    scene["wws_animation_strategy"] = "single paired authored performance"
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "scene.blend"))
    provenance = write_provenance(actions, foot_pins, contact_points)
    print("HERO_EXCHANGE_BUILT", json.dumps({"scene": str(OUTPUT / "scene.blend"), "actions": provenance["paired_actions"]}))


if __name__ == "__main__":
    main()
