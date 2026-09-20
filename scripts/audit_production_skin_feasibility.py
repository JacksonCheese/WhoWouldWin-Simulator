"""Read-only technical audit for the production-skin feasibility scene."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.kdtree import KDTree


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/combat_motion_lab_hand_authored_root_revision"
OUTPUT = ROOT / "outputs/combat_motion_lab_production_skin_feasibility"
EXPECTED = "4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861"
ACTIONS = ("HA_BODY_OMNI", "HA_BODY_NARUTO", "HA_ROOT_fighter_a", "HA_ROOT_fighter_b")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def action_signature(action):
    payload = []
    for curve in sorted(action.fcurves, key=lambda c: (c.data_path, c.array_index)):
        payload.append({
            "data_path": curve.data_path,
            "array_index": curve.array_index,
            "keys": [
                [round(k.co.x, 7), round(k.co.y, 9), k.interpolation]
                for k in curve.keyframe_points
            ],
        })
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def signatures(path: Path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    return {name: action_signature(bpy.data.actions[name]) for name in ACTIONS}


def evaluated_vertices(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def minimum_vertex_distance(source_objects, target):
    target_vertices = evaluated_vertices(target)
    tree = KDTree(len(target_vertices))
    for index, point in enumerate(target_vertices):
        tree.insert(point, index)
    tree.balance()
    minimum = float("inf")
    pair = None
    for obj in source_objects:
        for point in evaluated_vertices(obj):
            nearest, index, distance = tree.find(point)
            if distance < minimum:
                minimum = distance
                pair = [obj.name, index, list(point), list(nearest)]
    return minimum, pair


def projected_bounds(names, camera):
    scene = bpy.context.scene
    points = []
    for name in names:
        obj = bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get())
        points.extend(world_to_camera_view(scene, camera, obj.matrix_world @ Vector(corner)) for corner in obj.bound_box)
    xs, ys = [p.x for p in points], [p.y for p in points]
    return {
        "min_x": min(xs), "max_x": max(xs), "min_y": min(ys), "max_y": max(ys),
        "area_fraction": max(0.0, max(xs) - min(xs)) * max(0.0, max(ys) - min(ys)),
        "clips_frame": min(xs) < 0 or max(xs) > 1 or min(ys) < 0 or max(ys) > 1,
    }


def body_min_z(obj):
    return min(point.z for point in evaluated_vertices(obj))


def joint_angle(rig, upper, lower):
    a = rig.matrix_world @ rig.pose.bones[upper].head
    b = rig.matrix_world @ rig.pose.bones[upper].tail
    c = rig.matrix_world @ rig.pose.bones[lower].tail
    return math.degrees((a - b).angle(c - b))


def main():
    source_signatures = signatures(SOURCE / "scene.blend")
    derived_signatures = signatures(OUTPUT / "scene.blend")
    scene = bpy.context.scene
    if source_signatures != derived_signatures:
        raise RuntimeError("Baseline paired body/root Action keys changed")
    if sha256(OUTPUT / "source/events.json") != EXPECTED:
        raise RuntimeError("Canonical event hash changed")

    hero_names = {
        "omniman": ["OmniMan_Body", "OmniMan_HairCap", "OmniMan_Cape", "OmniMan_Mustache_0", "OmniMan_Mustache_1"],
        "naruto": ["Naruto_Body", "Naruto_ForeheadProtectorBand", "Naruto_ForeheadPlate", *[f"Naruto_HairSpike_{i:02d}" for i in range(13)]],
    }
    camera_for_frame = {
        14: "SKINTEST_CAM_AttackSlip", 68: "SKINTEST_CAM_RasenganEntry",
        76: "SKINTEST_CAM_RasenganEntry", 82: "SKINTEST_CAM_RasenganEntry",
        84: "SKINTEST_CAM_RasenganEntry", 85: "SKINTEST_CAM_Recoil",
        90: "SKINTEST_CAM_Recoil", 98: "SKINTEST_CAM_Recoil",
    }
    frames = {}
    for frame, camera_name in camera_for_frame.items():
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        frames[str(frame)] = {
            "body_min_z": {
                "naruto": body_min_z(bpy.data.objects["Naruto_Body"]),
                "omniman": body_min_z(bpy.data.objects["OmniMan_Body"]),
            },
            "screen_bounds": {
                fighter: projected_bounds(names, bpy.data.objects[camera_name])
                for fighter, names in hero_names.items()
            },
            "joint_angles_degrees": {
                "naruto_elbow_R": joint_angle(bpy.data.objects["fighter_b_ProductionRig"], "UpperArm_R", "LowerArm_R"),
                "omniman_elbow_L": joint_angle(bpy.data.objects["fighter_a_ProductionRig"], "UpperArm_L", "LowerArm_L"),
            },
        }

    scene.frame_set(82)
    bpy.context.view_layer.update()
    hand_objects = [
        bpy.data.objects["naruto_R_Palm"], bpy.data.objects["naruto_R_Thumb"],
        *[bpy.data.objects[f"naruto_R_Finger_{i}"] for i in range(4)],
    ]
    hand_distance, hand_pair = minimum_vertex_distance(hand_objects, bpy.data.objects["OmniMan_Body"])
    cape_distance, cape_pair = minimum_vertex_distance([bpy.data.objects["OmniMan_Cape"]], bpy.data.objects["OmniMan_Body"])
    root_collision = json.loads((SOURCE / "review/contact-penetration-report.json").read_text())
    root_foot = json.loads((SOURCE / "review/foot-drift-report.json").read_text())

    report = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_scene_sha256": sha256(SOURCE / "scene.blend"),
        "derived_scene_sha256": sha256(OUTPUT / "scene.blend"),
        "canonical_events_sha256": sha256(OUTPUT / "source/events.json"),
        "timeline": [1, 108],
        "action_signatures": {
            name: {"source": source_signatures[name], "derived": derived_signatures[name], "identical": True}
            for name in ACTIONS
        },
        "body_root_action_separation_preserved": True,
        "frame_metrics": frames,
        "contact_frame_82": {
            "hand_overlay_to_omniman_vertex_distance": hand_distance,
            "nearest_vertex_pair": hand_pair,
            "rasengan_physical_hand_proxy_gap": root_collision["planned_contact_metrics"]["rasengan_contact"]["nearest_surface_gap"],
            "rasengan_marker_surface_gap": json.loads((SOURCE / "review/full-frame-motion.json").read_text())["after"][81]["rasengan_marker_gap"],
            "cape_to_body_vertex_distance": cape_distance,
            "cape_nearest_vertex_pair": cape_pair,
            "note": "Vertex distance is an unsigned sampling diagnostic, not a watertight mesh-intersection proof.",
        },
        "baseline_collision": {
            "unsupported_issue_count": root_collision["unsupported_issue_count"],
            "max_unsupported_penetration": root_collision["max_unsupported_penetration"],
            "intentional_issue_count": root_collision["intentional_issue_count"],
        },
        "baseline_support": {
            "maximum_world_drift": root_foot["maximum_world_drift"],
            "threshold": root_foot["threshold"],
            "passes_threshold": root_foot["passes_threshold"],
            "known_visual_limitation": "Stationary ankle targets coexist with visible sole gaps in inherited Omni-Man poses.",
        },
        "production_approval_claimed": False,
    }
    path = OUTPUT / "review/technical-audit.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print("PRODUCTION_SKIN_AUDIT_COMPLETE", report["derived_scene_sha256"], hand_distance)


if __name__ == "__main__":
    main()
