"""Validate the hand-authored exchange without altering its choreography."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(bpy.data.filepath).resolve().parent
END = 108
TOLERANCE = .045


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_collision_module():
    path = ROOT / "scripts/blender_first_production_fight_v2.py"
    spec = importlib.util.spec_from_file_location("ha_validation_math", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def intentional(frame, a, b):
    roles = {(a.fighter, a.role), (b.fighter, b.role)}
    parry = 32 <= frame <= 38 and any(("naruto", role) in roles for role in ("hand.L", "forearm.L")) and any(
        ("omniman", role) in roles for role in ("hand.L", "forearm.L", "upper_arm.L")
    )
    rasengan = 81 <= frame <= 85 and ("naruto", "hand.R") in roles and ("omniman", "chest") in roles
    return parry or rasengan


def pair_gap(mathlib, rig_a, fighter_a, role_a, rig_b, fighter_b, role_b):
    a = mathlib.capsule_for(rig_a, fighter_a, role_a)
    b = mathlib.capsule_for(rig_b, fighter_b, role_b)
    return mathlib.segment_distance(a.a, a.b, b.a, b.b) - a.radius - b.radius


def foot_drift(rig, fighter, side, start, end):
    points = []
    for frame in range(start, end + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        bone = rig.pose.bones["Foot_" + side]
        points.append(rig.matrix_world @ bone.head)
    anchor = points[0]
    horizontal = [((p.x - anchor.x) ** 2 + (p.y - anchor.y) ** 2) ** .5 for p in points]
    vertical = [abs(p.z - anchor.z) for p in points]
    return {
        "fighter": fighter, "side": side, "frames": [start, end],
        "max_horizontal_drift": round(max(horizontal), 6),
        "max_vertical_drift": round(max(vertical), 6),
        "max_world_drift": round(max((p - anchor).length for p in points), 6),
    }


def main():
    mathlib = load_collision_module()
    scene = bpy.context.scene
    omni = bpy.data.objects["fighter_a_ProductionRig"]
    naruto = bpy.data.objects["fighter_b_ProductionRig"]
    issues = []
    contacts = {"omni_attack_miss": [], "counter_parry": [], "rasengan_contact": []}
    ground = []
    for frame in range(1, END + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        oc = mathlib.fighter_capsules(omni, "omniman")
        nc = mathlib.fighter_capsules(naruto, "naruto")
        for a in oc:
            for b in nc:
                depth = a.radius + b.radius - mathlib.segment_distance(a.a, a.b, b.a, b.b)
                if depth > TOLERANCE:
                    allowed = intentional(frame, a, b)
                    issues.append({
                        "frame": frame, "proxy_pair": [a.role, b.role],
                        "penetration_depth": round(depth, 6), "intentional": allowed,
                        "category": "body_body" if a.role in {"head", "chest", "pelvis"} and b.role in {"head", "chest", "pelvis"} else "limb_body",
                    })
        for fighter, caps in (("omniman", oc), ("naruto", nc)):
            for cap in caps:
                if cap.role.startswith("foot"):
                    lowest = min(cap.a.z, cap.b.z)
                    ground.append({"frame": frame, "fighter": fighter, "foot": cap.role, "lowest_z": round(lowest, 6)})
        if 12 <= frame <= 23:
            contacts["omni_attack_miss"].append({"frame": frame, "surface_gap": round(pair_gap(mathlib, omni, "omniman", "hand.R", naruto, "naruto", "head"), 6)})
        if 30 <= frame <= 42:
            contacts["counter_parry"].append({"frame": frame, "surface_gap": round(pair_gap(mathlib, naruto, "naruto", "hand.L", omni, "omniman", "forearm.L"), 6)})
        if 78 <= frame <= 90:
            contacts["rasengan_contact"].append({"frame": frame, "surface_gap": round(pair_gap(mathlib, naruto, "naruto", "hand.R", omni, "omniman", "chest"), 6)})
    unsupported = [issue for issue in issues if not issue["intentional"]]
    summaries = {}
    for name, values in contacts.items():
        nearest = min(values, key=lambda x: abs(x["surface_gap"]))
        summaries[name] = {
            "nearest_frame": nearest["frame"], "nearest_surface_gap": nearest["surface_gap"],
            "minimum_surface_gap": min(x["surface_gap"] for x in values),
            "maximum_surface_gap": max(x["surface_gap"] for x in values),
        }
    pins = [
        foot_drift(omni, "omniman", "R", 1, 8), foot_drift(omni, "omniman", "R", 36, 40),
        foot_drift(omni, "omniman", "L", 52, 60), foot_drift(omni, "omniman", "R", 79, 84),
        foot_drift(naruto, "naruto", "L", 1, 7), foot_drift(naruto, "naruto", "R", 52, 58),
        foot_drift(naruto, "naruto", "R", 81, 84), foot_drift(naruto, "naruto", "L", 98, 104),
    ]
    report = {
        "schema_version": 1, "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scene": str(Path(bpy.data.filepath)), "scene_sha256": digest(Path(bpy.data.filepath)),
        "source_events_sha256": scene.get("wws_source_events_sha256"), "frames_evaluated": END, "fps": 30,
        "presentation_only": True, "clearance_solver_used": False, "tolerance": TOLERANCE,
        "intentional_contact_windows": [{"frames": [32, 38], "event": "counter parry"}, {"frames": [81, 85], "event": "Rasengan contact/hold"}],
        "planned_contact_metrics": summaries, "issue_count": len(issues),
        "intentional_issue_count": len(issues) - len(unsupported), "unsupported_issue_count": len(unsupported),
        "max_unsupported_penetration": max((x["penetration_depth"] for x in unsupported), default=0),
        "worst_unsupported": sorted(unsupported, key=lambda x: x["penetration_depth"], reverse=True)[:40],
        "all_issues": issues,
        "ground": {"minimum_z": min(x["lowest_z"] for x in ground), "below_tolerance_count": sum(x["lowest_z"] < -TOLERANCE for x in ground)},
    }
    foot_report = {
        "schema_version": 1, "scene_sha256": report["scene_sha256"], "units": "Blender scene units",
        "measurement": "maximum evaluated production-rig Foot bone-head displacement from the first frame of each declared planted interval",
        "declared_support_intervals": pins,
        "maximum_world_drift": max(x["max_world_drift"] for x in pins),
        "passes_numerical_plant_threshold": max(x["max_world_drift"] for x in pins) <= .035,
        "threshold": .035,
    }
    review = OUTPUT / "review"
    review.mkdir(parents=True, exist_ok=True)
    (review / "contact-penetration-report.json").write_text(json.dumps(report, indent=2))
    (review / "foot-drift-report.json").write_text(json.dumps(foot_report, indent=2))
    print("HA_VALIDATION=" + json.dumps({
        "unsupported": len(unsupported), "max_penetration": report["max_unsupported_penetration"],
        "contacts": summaries, "max_foot_drift": foot_report["maximum_world_drift"],
        "foot_pass": foot_report["passes_numerical_plant_threshold"],
    }))


if __name__ == "__main__":
    main()
