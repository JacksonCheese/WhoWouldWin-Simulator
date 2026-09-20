"""Validate V4 rig adaptation, deformation data, contact, and provenance in Blender.

The checks are intentionally engineering checks. They cannot certify the artistic
quality of weight painting or motion, which remains a visual review responsibility.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/blender_combat_v4_humanoid"
SOURCE = ROOT / "outputs/blender_combat_v3_astra"
SCENE = bpy.context.scene
STANDARD = (
    "root", "pelvis", "spine", "chest", "neck", "head",
    "clavicle.L", "clavicle.R", "upper_arm.L", "upper_arm.R",
    "forearm.L", "forearm.R", "hand.L", "hand.R", "thigh.L",
    "thigh.R", "shin.L", "shin.R", "foot.L", "foot.R",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(frame: int) -> None:
    SCENE.frame_set(frame)
    bpy.context.view_layer.update()


def world(rig, bone: str, tail: bool = False) -> Vector:
    evaluated = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    pose = evaluated.pose.bones[bone]
    return evaluated.matrix_world @ (pose.tail if tail else pose.head)


def connected_components(mesh) -> int:
    adjacency = {vertex.index: set() for vertex in mesh.vertices}
    for edge in mesh.edges:
        left, right = edge.vertices
        adjacency[left].add(right)
        adjacency[right].add(left)
    remaining = set(adjacency)
    count = 0
    while remaining:
        count += 1
        queue = deque([remaining.pop()])
        while queue:
            for neighbor in adjacency[queue.popleft()]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)
    return count


def mesh_report(body, rig, mapping: dict[str, str]) -> dict:
    components = connected_components(body.data)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    non_manifold_edges = sum(1 for edge in bm.edges if not edge.is_manifold)
    bm.free()
    allowed_groups = set(mapping.values())
    unweighted = 0
    max_influences = 0
    minimum_sum = 1.0
    unexpected_groups = set()
    for vertex in body.data.vertices:
        weights = [group.weight for group in vertex.groups if group.weight > 1e-8]
        if not weights:
            unweighted += 1
        else:
            minimum_sum = min(minimum_sum, sum(weights))
            max_influences = max(max_influences, len(weights))
        for membership in vertex.groups:
            name = body.vertex_groups[membership.group].name
            if name not in allowed_groups:
                unexpected_groups.add(name)
    modifiers = {modifier.type for modifier in body.modifiers}
    armature_mod = next(mod for mod in body.modifiers if mod.type == "ARMATURE")
    assert armature_mod.object == rig
    assert components == 1
    assert non_manifold_edges == 0
    assert unweighted == 0
    assert max_influences <= 4
    assert minimum_sum > 0.999
    assert not unexpected_groups
    assert {"ARMATURE", "CORRECTIVE_SMOOTH"} <= modifiers
    return {
        "vertices": len(body.data.vertices),
        "polygons": len(body.data.polygons),
        "connected_components": components,
        "non_manifold_edges": non_manifold_edges,
        "unweighted_vertices": unweighted,
        "max_weight_influences": max_influences,
        "minimum_weight_sum": minimum_sum,
        "modifiers": sorted(modifiers),
    }


def skin_distance(body, point: Vector) -> float:
    evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    tree = BVHTree.FromPolygons(
        [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices],
        [list(polygon.vertices) for polygon in mesh.polygons],
    )
    nearest = tree.find_nearest(point)
    evaluated.to_mesh_clear()
    if nearest is None:
        raise AssertionError("No evaluated skin surface found")
    return nearest[3]


def main() -> None:
    source_manifest = json.loads((SOURCE / "director_manifest.json").read_text())
    assert SCENE["wws_source_checksum"] == source_manifest["source_checksum"]
    assert SCENE["wws_source_outcome_digest"] == source_manifest["source_outcome_digest"]
    assert len([action for action in bpy.data.actions if action.name.startswith("WWS_LIB_")]) == 40
    assert SCENE.frame_end == 360 and SCENE.render.fps == 30

    rigs = {}
    bodies = {}
    mappings = {}
    mesh_checks = {}
    source_tracks = {}
    for fighter in ("fighter_a", "fighter_b"):
        source_rig = bpy.data.objects[f"{fighter}_Rig"]
        rig = bpy.data.objects[f"{fighter}_ProductionRig"]
        body = bpy.data.objects[f"{fighter}_ProductionBody"]
        mapping = json.loads(rig["wws_standard_to_target"])
        assert set(mapping) == set(STANDARD)
        assert all(mapping[name] in rig.data.bones for name in STANDARD)
        assert rig["wws_source_rig"] == source_rig.name
        assert body.parent == rig
        assert bpy.data.objects[f"{fighter}_SkinnedBody"].hide_render
        rigs[fighter], bodies[fighter], mappings[fighter] = rig, body, mapping
        mesh_checks[fighter] = mesh_report(body, rig, mapping)
        source_tracks[fighter] = len(source_rig.animation_data.nla_tracks)

    snapshots = {}
    sample_frames = (145, 158, 163, 164, 165, 172, 184, 210, 245, 271, 277, 287, 300, 311)
    sample_bones = ("pelvis", "chest", "head", "hand.R", "foot.L", "foot.R")
    for frame in sample_frames:
        evaluate(frame)
        snapshots[frame] = {}
        for fighter, rig in rigs.items():
            mapping = mappings[fighter]
            points = {bone: list(world(rig, mapping[bone])) for bone in sample_bones}
            assert all(math.isfinite(value) for point in points.values() for value in point)
            snapshots[frame][fighter] = points

    freeze = max(
        (Vector(snapshots[163][fighter][bone]) - Vector(snapshots[frame][fighter][bone])).length
        for fighter in rigs
        for bone in sample_bones
        for frame in (164, 165)
    )
    assert freeze < 0.005, freeze

    evaluate(163)
    contact_target = bpy.data.objects["fighter_b_IK_hand.R"].matrix_world.translation
    contact_error = (
        world(rigs["fighter_b"], mappings["fighter_b"]["forearm.R"], tail=True)
        - contact_target
    ).length
    contact_skin_distance = skin_distance(bodies["fighter_a"], contact_target)
    assert contact_error < 0.01, contact_error
    assert contact_skin_distance < 0.03, contact_skin_distance

    # The attacker remains planted across the contact hold. These are evaluated
    # target-rig foot endpoints, so the check includes adapter and target IK.
    foot_samples = {}
    for frame in (163, 164, 165):
        evaluate(frame)
        foot_samples[frame] = {
            side: world(rigs["fighter_b"], mappings["fighter_b"][f"foot.{side}"], tail=True)
            for side in ("L", "R")
        }
    planted_slide = max(
        (foot_samples[frame][side] - foot_samples[163][side]).length
        for frame in (164, 165)
        for side in ("L", "R")
    )
    assert planted_slide < 0.01, planted_slide

    evaluate(172)
    launch_start = rigs["fighter_a"].matrix_world.translation.copy()
    evaluate(210)
    launch_travel = rigs["fighter_a"].matrix_world.translation - launch_start
    assert launch_travel.length > 1.0

    report = {
        "checks_passed": True,
        "source_checksum": SCENE["wws_source_checksum"],
        "outcome_digest": SCENE["wws_source_outcome_digest"],
        "source_events_sha256": sha256(SOURCE / "source/events.json"),
        "native_actions": 40,
        "source_nla_tracks": source_tracks,
        "rig_contract_bones": list(STANDARD),
        "rig_mappings": mappings,
        "mesh_checks": mesh_checks,
        "contact_ik_error": contact_error,
        "contact_target_distance_to_evaluated_skin": contact_skin_distance,
        "three_frame_hold_max_bone_displacement": freeze,
        "contact_hold_max_foot_slide": planted_slide,
        "launch_travel": list(launch_travel),
        "static_review_camera": SCENE.objects["V4_StaticMotionReview"].name,
        "key_pose_samples": snapshots,
        "qualification": (
            "Checks establish rig isolation, closed connected geometry, normalized weights, "
            "evaluated contact, planted hit-stop, finite deformation, and provenance. They do "
            "not certify artist-authored topology, fingers, facial rigging, or production polish."
        ),
    }
    path = OUT / "review/validation.json"
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({key: value for key, value in report.items() if key != "key_pose_samples"}, indent=2))


if __name__ == "__main__":
    main()
