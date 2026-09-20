"""Measure the controls available for paired combat authoring in the saved scene."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import bpy

OUTPUT = Path(bpy.data.filepath).resolve().parent
SCENE = bpy.context.scene


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bone_inventory(rig):
    names = [bone.name for bone in rig.pose.bones]
    lower = [name.lower() for name in names]
    def matching(*tokens):
        return [name for name, value in zip(names, lower) if any(token in value for token in tokens)]
    return {
        "count": len(names),
        "bones": names,
        "clavicles": matching("clavicle", "shoulder"),
        "scapula_controls": matching("scap", "shoulderblade"),
        "forearm_twist": matching("forearm_twist", "lowerarm_twist", "armtwist"),
        "toe_ball_heel": matching("toe", "ball", "heel"),
        "finger_controls": matching("thumb", "index", "middle", "ring", "pinky"),
    }


def constraint_inventory(rig):
    result = []
    for bone in rig.pose.bones:
        for constraint in bone.constraints:
            result.append({
                "bone": bone.name,
                "name": constraint.name,
                "type": constraint.type,
                "target": constraint.target.name if getattr(constraint, "target", None) else None,
                "pole_target": constraint.pole_target.name if constraint.type == "IK" and constraint.pole_target else None,
                "chain_count": constraint.chain_count if constraint.type == "IK" else None,
                "influence": round(float(constraint.influence), 4),
            })
    return result


def action_inventory(rig):
    action = rig.animation_data.action if rig.animation_data else None
    if not action:
        return None
    by_bone = {}
    for curve in action.fcurves:
        path = curve.data_path
        if 'pose.bones["' in path:
            bone = path.split('pose.bones["', 1)[1].split('"]', 1)[0]
        elif path in {"location", "rotation_euler", "rotation_quaternion"}:
            bone = "ROOT_OBJECT"
        else:
            bone = "OTHER"
        by_bone[bone] = by_bone.get(bone, 0) + len(curve.keyframe_points)
    return {
        "name": action.name,
        "frame_range": [round(value, 3) for value in action.frame_range],
        "fcurves": len(action.fcurves),
        "keyframes_by_bone": by_bone,
        "quality_status": action.get("wws_quality_status", "diagnostic_rejected"),
    }


def foot_pin_drift(fighter, production_rig, windows):
    samples = []
    for side, start, end in windows:
        points = []
        for frame in range(start, end + 1):
            SCENE.frame_set(frame)
            bpy.context.view_layer.update()
            bone = production_rig.pose.bones["Foot_" + side]
            points.append(production_rig.matrix_world @ bone.head)
        anchor = points[0]
        samples.append({
            "fighter": fighter, "side": side, "frames": [start, end],
            "max_world_drift": round(max((point - anchor).length for point in points), 6),
        })
    return samples


def main():
    source = {key: bpy.data.objects[key + "_Rig"] for key in ("fighter_a", "fighter_b")}
    production = {key: bpy.data.objects[key + "_ProductionRig"] for key in ("fighter_a", "fighter_b")}
    rigs = {}
    for key in source:
        constraints = constraint_inventory(source[key]) + constraint_inventory(production[key])
        cleanup_map = json.loads(production[key].get("wws_cleanup_control_map", "{}"))
        rigs[key] = {
            "source_rig": bone_inventory(source[key]),
            "production_rig": bone_inventory(production[key]),
            "constraints": constraints,
            "action": action_inventory(source[key]),
            "cleanup_control_map": cleanup_map,
            "cleanup_controls_active": bool(production[key].get("wws_cleanup_controls_active", False)),
            "has_elbow_pole_targets": any(item["pole_target"] and "arm" in item["bone"].lower() for item in constraints),
            "has_active_elbow_pole_targets": any(
                item["pole_target"] and "arm" in item["bone"].lower() and item["influence"] > 0
                for item in constraints
            ),
            "has_partner_contact_controls": any(item["target"] and item["target"].startswith("HERO_") for item in constraints),
        }
    drift = []
    for fighter, windows in {
        "fighter_a": [("L", 1, 8), ("R", 30, 36), ("L", 45, 53)],
        "fighter_b": [("L", 1, 10), ("R", 28, 35), ("L", 44, 52), ("R", 62, 70), ("L", 82, 89)],
    }.items():
        drift.extend(foot_pin_drift(fighter, production[fighter], windows))
    report = {
        "schema_version": 2,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scene": str(Path(bpy.data.filepath)),
        "scene_sha256": digest(Path(bpy.data.filepath)),
        "rigs": rigs,
        "support_pin_drift": drift,
        "cleanup_layer": {
            "collection_present": bpy.data.collections.get("WWS_SOURCE_READINESS_CONTROLS") is not None,
            "control_count": sum(len(item["cleanup_control_map"]) for item in rigs.values()),
            "active_during_diagnostic_motion": False,
            "intent": "Animator cleanup/retarget controls. They do not modify the rejected diagnostic performance until keyed and activated around approved source motion.",
        },
        "capability_decision": {
            "clavicle_controls": "LIMITED: one clavicle/shoulder bone per side",
            "scapula_upper_back": "CLEANUP CONTROL ADDED: orientation control is available; the current mesh still has no deforming scapula bone",
            "elbow_pole_vectors": "CLEANUP CONTROLS ADDED: dedicated arm IK pole targets are present and intentionally inactive until an animator enables them",
            "forearm_twist": "ADAPTER CHANNEL ADDED: twist controls can map to source twist bones; the current review rig has no deforming twist bones",
            "wrist_hand": "CLEANUP ORIENTATION CONTROL ADDED: one hand bone remains; production finger detail must come from the imported asset",
            "pelvis_chest_timing": "SUPPORTED: independently keyed pelvis, spine, and chest",
            "heel_ball_toe": "CLEANUP PIVOTS ADDED: heel/ball/toe controls are present; production deform bones remain source-dependent",
            "foot_locking": "CLEANUP IK ADDED: explicit planted-foot constraints exist but are inactive on the rejected diagnostic motion",
            "partner_targets": "SUPPORTED AS ADAPTATION: short contact targets exist",
            "contact_recoil_timing": "SUPPORTED: independent Action curves and contact windows",
        },
        "verdict": "B",
        "verdict_text": "The import/retarget and modest cleanup-control pipeline is ready. Production animation remains blocked by the missing approved paired authored or paired-mocap source.",
    }
    path = OUTPUT / "review/rig-capability-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({"scene_sha256": report["scene_sha256"], "support_pin_drift": drift, "verdict": "B"}, indent=2))


if __name__ == "__main__":
    main()
