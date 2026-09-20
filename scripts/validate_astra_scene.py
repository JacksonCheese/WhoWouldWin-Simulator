"""Validate the saved directing pass inside Blender; report geometric limits honestly."""

import bpy
import json
import math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/blender_combat_v3_astra"
s = bpy.context.scene
a = bpy.data.objects["fighter_a_Rig"]
b = bpy.data.objects["fighter_b_Rig"]
base = json.loads((ROOT / "outputs/blender_combat_v3/blender_plan.json").read_text())


def evaluate(frame):
    s.frame_set(frame)
    bpy.context.view_layer.update()
    return bpy.context.evaluated_depsgraph_get()


def world(rig, bone, tail=False):
    r = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    p = r.pose.bones[bone]
    return r.matrix_world @ (p.tail if tail else p.head)


assert s["wws_source_checksum"] == base["source_checksum"]
assert s["wws_source_outcome_digest"] == base["source_outcome_digest"]
assert all(p.rotation_mode == "XYZ" for rig in (a, b) for p in rig.pose.bones)
assert len([x for x in bpy.data.actions if x.name.startswith("WWS_LIB_")]) == 40
assert s.frame_end == 360 and s.render.fps == 30

snapshots = {}
for frame in (
    145,
    158,
    163,
    164,
    165,
    167,
    173,
    184,
    202,
    245,
    277,
    281,
    290,
    300,
    311,
    340,
):
    evaluate(frame)
    snapshots[frame] = {
        r.name: {
            bone: list(world(r, bone))
            for bone in ("pelvis", "chest", "head", "hand.R", "foot.L", "foot.R")
        }
        for r in (a, b)
    }
    assert all(
        math.isfinite(v)
        for r in snapshots[frame].values()
        for p in r.values()
        for v in p
    )
freeze = max(
    (Vector(snapshots[163][r.name][bone]) - Vector(snapshots[f][r.name][bone])).length
    for r in (a, b)
    for bone in snapshots[163][r.name]
    for f in (164, 165)
)
assert freeze < 0.005, freeze

evaluate(163)
target = bpy.data.objects["fighter_b_IK_hand.R"].matrix_world.translation
error = (world(b, "forearm.R", True) - target).length
assert error < 0.005, error
# Test the evaluated skin too: reaching an arbitrary empty alone does not establish a hit.
o = bpy.data.objects["fighter_a_SkinnedBody"].evaluated_get(
    bpy.context.evaluated_depsgraph_get()
)
m = o.to_mesh()
tree = BVHTree.FromPolygons(
    [o.matrix_world @ v.co for v in m.vertices], [list(p.vertices) for p in m.polygons]
)
nearest = tree.find_nearest(target)
skin_distance = nearest[3]
o.to_mesh_clear()
assert skin_distance < 0.25, skin_distance

evaluate(163)
impact_axis = a.location - b.location
evaluate(167)
start = a.location.copy()
evaluate(173)
travel = a.location - start
assert impact_axis.dot(travel) > 0
# VFX suppression must survive timeline evaluation, rather than being reset by animation.
for f in (60, 100, 163, 170, 190, 220):
    evaluate(f)
    assert all(
        o.hide_render
        for o in bpy.data.objects
        if o.name.startswith(("vfx-001", "vfx-004", "vfx-005", "vfx-006"))
    )

occupancy = []
for f, rig in (
    (70, a),
    (145, b),
    (163, b),
    (184, a),
    (210, a),
    (277, a),
    (305, a),
    (340, b),
):
    evaluate(f)
    obj = bpy.data.objects[rig.name.replace("_Rig", "_SkinnedBody")].evaluated_get(
        bpy.context.evaluated_depsgraph_get()
    )
    mesh = obj.to_mesh()
    coords = [
        world_to_camera_view(s, s.camera, obj.matrix_world @ v.co)
        for v in mesh.vertices
    ]
    occupancy.append(
        {
            "frame": f,
            "actor": rig.name,
            "projected_height_fraction": max(p.y for p in coords)
            - min(p.y for p in coords),
            "projected_width_fraction": max(p.x for p in coords)
            - min(p.x for p in coords),
        }
    )
    obj.to_mesh_clear()
report = {
    "checks_passed": True,
    "source_checksum": s["wws_source_checksum"],
    "outcome_digest": s["wws_source_outcome_digest"],
    "contact_ik_error": error,
    "contact_target_distance_to_evaluated_skin": skin_distance,
    "three_frame_hold_max_bone_displacement": freeze,
    "launch_alignment_dot": impact_axis.normalized().dot(travel.normalized()),
    "camera_count_in_edit": len(s.timeline_markers),
    "native_actions": 40,
    "nla_tracks": {r.name: len(r.animation_data.nla_tracks) for r in (a, b)},
    "occupancy": occupancy,
    "key_pose_samples": snapshots,
    "qualification": "Geometry checks establish target reach and preservation, not production-quality animation. Skin distance is unsigned; no full collision solver or rig deformation certification.",
}
(OUT / "review/scene_validation.json").write_text(json.dumps(report, indent=2))
print(
    json.dumps(
        {k: v for k, v in report.items() if k not in ("key_pose_samples", "occupancy")},
        indent=2,
    )
)
