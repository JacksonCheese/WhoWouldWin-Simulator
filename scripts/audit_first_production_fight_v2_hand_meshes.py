"""Focused evaluated-mesh audit for V2 hands, bodies, and cape."""

from __future__ import annotations

import json
from pathlib import Path

import bpy
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/first_production_fight_v2/review/hand_mesh_clearance_report.json"
FRAMES = [296, 303, 316, 332, 336, 357, 360, 362, 365, 368, 371, 375, 379]


def world_bvh(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    matrix = evaluated.matrix_world
    vertices = [matrix @ vertex.co for vertex in mesh.vertices]
    polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
    bvh = BVHTree.FromPolygons(vertices, polygons, all_triangles=False, epsilon=0.0005)
    evaluated.to_mesh_clear()
    return bvh


def hand_objects(prefix):
    return [obj for obj in bpy.data.objects if obj.name.startswith(prefix) and obj.type == "MESH"]


scene = bpy.context.scene
depsgraph = bpy.context.evaluated_depsgraph_get()
naruto_body = bpy.data.objects["Naruto_Body"]
omni_body = bpy.data.objects["OmniMan_Body"]
cape = bpy.data.objects["OmniMan_Cape"]
checks = []
for frame in FRAMES:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    depsgraph.update()
    naruto_bvh = world_bvh(naruto_body, depsgraph)
    omni_bvh = world_bvh(omni_body, depsgraph)
    entries = {}
    for label, objects, target in (
        ("naruto_right_hand_vs_omniman", hand_objects("naruto_R_"), omni_bvh),
        ("naruto_left_hand_vs_omniman", hand_objects("naruto_L_"), omni_bvh),
        ("omniman_right_hand_vs_naruto", hand_objects("omniman_R_"), naruto_bvh),
        ("omniman_left_hand_vs_naruto", hand_objects("omniman_L_"), naruto_bvh),
    ):
        intersecting = []
        triangle_pairs = 0
        for obj in objects:
            overlaps = world_bvh(obj, depsgraph).overlap(target)
            if overlaps:
                intersecting.append(obj.name)
                triangle_pairs += len(overlaps)
        entries[label] = {
            "intersecting_parts": intersecting,
            "triangle_overlap_pairs": triangle_pairs,
        }
    cape_naruto = world_bvh(cape, depsgraph).overlap(naruto_bvh)
    checks.append({
        "frame": frame,
        "hands": entries,
        "cape_vs_naruto_triangle_overlap_pairs": len(cape_naruto),
    })

payload = {
    "schema_version": 1,
    "method": "world-space evaluated modifier-stack BVH overlap of visible palm/finger/thumb meshes against opponent body",
    "frames": checks,
    "frame_360_omniman_hand_r_intersects_naruto": bool(
        next(item for item in checks if item["frame"] == 360)["hands"]["omniman_right_hand_vs_naruto"]["triangle_overlap_pairs"]
    ),
}
OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload, indent=2))
