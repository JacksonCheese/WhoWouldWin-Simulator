"""Read-only contact and penetration diagnostics for the paired hero exchange."""
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
TOLERANCE = .045
END = 120


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_collision_module():
    path = ROOT / "scripts/blender_first_production_fight_v2.py"
    spec = importlib.util.spec_from_file_location("hero_validation_math", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def intentional(frame, a, b):
    roles = {(a.fighter, a.role), (b.fighter, b.role)}
    if 43 <= frame <= 51:
        return any(("naruto", role) in roles for role in ("hand.L", "forearm.L", "hand.R")) and any(
            ("omniman", role) in roles for role in ("hand.L", "forearm.L", "upper_arm.L")
        )
    if 84 <= frame <= 89:
        return ("naruto", "hand.R") in roles and ("omniman", "chest") in roles
    return False


def pair_gap(mathlib, rig_a, fighter_a, role_a, rig_b, fighter_b, role_b):
    a = mathlib.capsule_for(rig_a, fighter_a, role_a)
    b = mathlib.capsule_for(rig_b, fighter_b, role_b)
    distance = mathlib.segment_distance(a.a, a.b, b.a, b.b)
    return distance - a.radius - b.radius


def main():
    mathlib = load_collision_module()
    scene = bpy.context.scene
    omni_rig = bpy.data.objects["fighter_a_ProductionRig"]
    naruto_rig = bpy.data.objects["fighter_b_ProductionRig"]
    all_issues = []
    foot_samples = []
    planned = []
    for frame in range(1, END + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        omni = mathlib.fighter_capsules(omni_rig, "omniman")
        naruto = mathlib.fighter_capsules(naruto_rig, "naruto")
        for a in omni:
            for b in naruto:
                penetration = a.radius + b.radius - mathlib.segment_distance(a.a, a.b, b.a, b.b)
                if penetration <= TOLERANCE:
                    continue
                allowed = intentional(frame, a, b)
                category = "body_body" if a.role in {"head", "chest", "pelvis"} and b.role in {"head", "chest", "pelvis"} else "limb_body"
                all_issues.append({
                    "frame": frame,
                    "objects": [a.fighter, b.fighter],
                    "proxy_pair": [a.role, b.role],
                    "category": category,
                    "penetration_depth": round(penetration, 5),
                    "intentional": allowed,
                })
        for fighter, caps in (("omniman", omni), ("naruto", naruto)):
            for cap in caps:
                if not cap.role.startswith("foot"):
                    continue
                lowest = min(cap.a.z, cap.b.z)
                if lowest < -TOLERANCE:
                    all_issues.append({
                        "frame": frame, "objects": [fighter, "ground"],
                        "proxy_pair": [cap.role, "ground"], "category": "ground",
                        "penetration_depth": round(-lowest, 5), "intentional": False,
                    })
                foot_samples.append({"frame": frame, "fighter": fighter, "foot": cap.role, "lowest_z": round(lowest, 5)})
        for label, role_a, role_b, window in (
            ("omni_attack_miss", "hand.R", "head", (14, 23)),
            ("guard_redirect", "hand.L", "forearm.L", (43, 51)),
            ("rasengan_contact", "hand.R", "chest", (84, 89)),
        ):
            if window[0] <= frame <= window[1]:
                if label == "omni_attack_miss":
                    gap = pair_gap(mathlib, omni_rig, "omniman", role_a, naruto_rig, "naruto", role_b)
                else:
                    gap = pair_gap(mathlib, naruto_rig, "naruto", role_a, omni_rig, "omniman", role_b)
                planned.append({"event": label, "frame": frame, "surface_gap": round(gap, 5), "intent": "miss" if label.endswith("miss") else "contact"})
    unsupported = [issue for issue in all_issues if not issue["intentional"]]
    worst = sorted(unsupported, key=lambda item: item["penetration_depth"], reverse=True)[:30]
    contacts = {}
    for event in {item["event"] for item in planned}:
        values = [item for item in planned if item["event"] == event]
        nearest = min(values, key=lambda item: abs(item["surface_gap"]))
        contacts[event] = {
            "nearest_frame": nearest["frame"],
            "nearest_surface_gap": nearest["surface_gap"],
            "minimum_surface_gap": min(item["surface_gap"] for item in values),
            "maximum_surface_gap": max(item["surface_gap"] for item in values),
            "intent": nearest["intent"],
        }
    report = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "presentation_only": True,
        "scene": str(Path(bpy.data.filepath)),
        "scene_sha256": digest(Path(bpy.data.filepath)),
        "source_scene_sha256": scene.get("wws_source_scene_sha256"),
        "source_events_sha256": scene.get("wws_source_events_sha256"),
        "frames_evaluated": END,
        "fps": 30,
        "tolerance": TOLERANCE,
        "clearance_solver_used": False,
        "intentional_windows": [
            {"frames": [43, 51], "purpose": "open-hand guard redirect"},
            {"frames": [84, 89], "purpose": "Rasengan tangent contact and hit hold"},
        ],
        "planned_contact_metrics": contacts,
        "issue_count": len(all_issues),
        "intentional_issue_count": len(all_issues) - len(unsupported),
        "unsupported_issue_count": len(unsupported),
        "max_unsupported_penetration": max((item["penetration_depth"] for item in unsupported), default=0),
        "worst_frames": sorted({item["frame"] for item in worst}),
        "worst_unsupported": worst,
        "all_issues": all_issues,
        "foot_ground_summary": {
            "minimum_z": min((sample["lowest_z"] for sample in foot_samples), default=0),
            "below_tolerance_count": sum(sample["lowest_z"] < -TOLERANCE for sample in foot_samples),
        },
    }
    path = OUTPUT / "review/contact-penetration-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({key: report[key] for key in ("frames_evaluated", "unsupported_issue_count", "max_unsupported_penetration", "planned_contact_metrics", "foot_ground_summary")}, indent=2))


if __name__ == "__main__":
    main()
