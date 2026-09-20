"""Inspect one FBX in a clean Blender process for non-production intake review."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import bpy


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def action_report(action) -> dict:
    object_location = []
    bone_location = []
    animated_bones = set()
    for curve in action.fcurves:
        path = curve.data_path
        if path == "location":
            object_location.append({"axis": curve.array_index, "keys": len(curve.keyframe_points)})
        if 'pose.bones["' in path:
            bone = path.split('pose.bones["', 1)[1].split('"]', 1)[0]
            animated_bones.add(bone)
            if path.endswith("location"):
                bone_location.append({"bone": bone, "axis": curve.array_index, "keys": len(curve.keyframe_points)})
    return {
        "name": action.name,
        "frame_range": [round(float(value), 4) for value in action.frame_range],
        "fcurve_count": len(action.fcurves),
        "animated_bones": sorted(animated_bones),
        "object_location_curves": object_location,
        "bone_location_curves": bone_location,
    }


def sample_world(rig, bone_name: str, frame: int):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    bone = rig.pose.bones.get(bone_name)
    if bone is None:
        return None
    point = rig.matrix_world @ bone.head
    return [float(point.x), float(point.y), float(point.z)]


def contiguous(values: list[int]) -> list[list[int]]:
    runs: list[list[int]] = []
    for frame in values:
        if not runs or frame != runs[-1][-1] + 1:
            runs.append([frame])
        else:
            runs[-1].append(frame)
    return runs


def foot_drift(rig, bone_name: str, start: int, end: int) -> dict | None:
    points = {}
    for frame in range(start, end + 1):
        value = sample_world(rig, bone_name, frame)
        if value is not None:
            points[frame] = value
    if not points:
        return None
    min_z = min(point[2] for point in points.values())
    scale = max(1.0, max(abs(v) for point in points.values() for v in point))
    height_tolerance = max(0.025, scale * 0.003)
    candidate = [frame for frame, point in points.items() if point[2] <= min_z + height_tolerance]
    windows = []
    for frames in contiguous(candidate):
        if len(frames) < 3:
            continue
        anchor = points[frames[0]]
        distances = [
            ((points[frame][0] - anchor[0]) ** 2 + (points[frame][1] - anchor[1]) ** 2) ** 0.5
            for frame in frames
        ]
        windows.append({
            "frames": [frames[0], frames[-1]],
            "sample_count": len(frames),
            "horizontal_drift": round(max(distances), 6),
        })
    return {
        "bone": bone_name,
        "minimum_world_z": round(min_z, 6),
        "contact_height_tolerance": round(height_tolerance, 6),
        "candidate_contact_windows": windows,
        "method": "Low-height numerical candidate windows; no authored support-foot metadata was supplied.",
    }


def main() -> None:
    args = parse_args()
    source = Path(args.input).resolve()
    output = Path(args.output).resolve()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    before_actions = set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=str(source), automatic_bone_orientation=False)
    scene = bpy.context.scene
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    new_actions = [action for action in bpy.data.actions if action not in before_actions]
    action_reports = [action_report(action) for action in new_actions]
    all_ranges = [item["frame_range"] for item in action_reports if item["frame_range"][1] > item["frame_range"][0]]
    if all_ranges:
        start = int(min(item[0] for item in all_ranges))
        end = int(max(item[1] for item in all_ranges))
    else:
        start, end = int(scene.frame_start), int(scene.frame_end)
    armature_reports = []
    animated_performers = 0
    for rig in armatures:
        assigned = rig.animation_data.action if rig.animation_data else None
        nla_actions = []
        if rig.animation_data:
            for track in rig.animation_data.nla_tracks:
                nla_actions.extend(strip.action.name for strip in track.strips if strip.action)
        action_names = sorted(set(([assigned.name] if assigned else []) + nla_actions))
        if action_names:
            animated_performers += 1
        bones = []
        for bone in rig.data.bones:
            bones.append({
                "name": bone.name,
                "parent": bone.parent.name if bone.parent else None,
                "deform": bool(bone.use_deform),
            })
        root_candidates = [
            bone.name for bone in rig.pose.bones
            if bone.parent is None or any(token in bone.name.lower() for token in ("root", "hips", "pelvis"))
        ]
        sample_bones = {}
        for bone_name in root_candidates[:6]:
            first = sample_world(rig, bone_name, start)
            last = sample_world(rig, bone_name, end)
            if first and last:
                sample_bones[bone_name] = {
                    "start": [round(value, 6) for value in first],
                    "end": [round(value, 6) for value in last],
                    "displacement": [round(last[i] - first[i], 6) for i in range(3)],
                }
        foot_names = [bone.name for bone in rig.pose.bones if "foot" in bone.name.lower()]
        armature_reports.append({
            "name": rig.name,
            "bone_count": len(bones),
            "bones": bones,
            "assigned_actions": action_names,
            "root_candidates": root_candidates,
            "root_world_samples": sample_bones,
            "foot_drift_candidates": [
                item for item in (foot_drift(rig, name, start, end) for name in foot_names) if item
            ],
        })
    payload = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "diagnostic_non_production_intake",
        "source": str(source),
        "filename": source.name,
        "bytes": source.stat().st_size,
        "sha256": digest(source),
        "scene_frame_rate": float(scene.render.fps) / float(scene.render.fps_base),
        "scene_frame_range_after_import": [int(scene.frame_start), int(scene.frame_end)],
        "observed_action_frame_range": [start, end],
        "duration_seconds_from_observed_range": round(max(0, end - start) / (float(scene.render.fps) / float(scene.render.fps_base)), 6),
        "armature_count": len(armatures),
        "animated_performer_count": animated_performers,
        "contains_more_than_one_animated_performer": animated_performers > 1,
        "mesh_count": sum(1 for obj in scene.objects if obj.type == "MESH"),
        "actions": action_reports,
        "armatures": armature_reports,
        "commercial_provenance_verified": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        "filename": source.name,
        "armatures": len(armatures),
        "animated_performers": animated_performers,
        "actions": [item["name"] for item in action_reports],
        "range": [start, end],
        "fps": payload["scene_frame_rate"],
    }))


if __name__ == "__main__":
    main()
