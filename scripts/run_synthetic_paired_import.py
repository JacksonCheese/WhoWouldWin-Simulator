"""Run the successful Blender-side paired-source importer smoke test."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/combat_motion_lab_source_readiness"
MODULE = ROOT / "src/whowouldwin/cinematic/assets/blender_import.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_importer():
    spec = importlib.util.spec_from_file_location("wws_paired_import_smoke", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    definition_path = OUTPUT / "synthetic/paired_import_smoke.json"
    definition = json.loads(definition_path.read_text())
    importer = load_importer()
    actions = importer.import_paired_animation_performance(
        definition,
        OUTPUT,
        {"fighter_a": bpy.data.objects["fighter_a_Rig"], "fighter_b": bpy.data.objects["fighter_b_Rig"]},
    )
    actor_reports = {}
    for actor_id, action in actions.items():
        frame_range = [round(float(value), 3) for value in action.frame_range]
        root_curves = [
            curve.data_path for curve in action.fcurves
            if curve.data_path == "location" or (
                curve.data_path.endswith("location") and
                any(f'pose.bones["{name}"]' in curve.data_path for name in ("root", "Root", "Hips", "pelvis"))
            )
        ]
        actor_reports[actor_id] = {
            "action": action.name,
            "frame_range": frame_range,
            "paired_performance": action.get("wws_paired_performance"),
            "paired_actor": action.get("wws_paired_actor"),
            "quality_status": action.get("wws_quality_status"),
            "root_translation_curves_after_extraction": root_curves,
        }
    shared_timeline = len({tuple(item["frame_range"]) for item in actor_reports.values()}) == 1
    report = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Pipeline smoke test only. This rejected diagnostic fixture is not production animation.",
        "source_definition": str(definition_path),
        "source_definition_sha256": digest(definition_path),
        "source_blend_sha256": digest(OUTPUT / definition["path"]),
        "importer_sha256": digest(MODULE),
        "actors": actor_reports,
        "shared_timeline_preserved": shared_timeline,
        "root_motion_separated": all(not item["root_translation_curves_after_extraction"] for item in actor_reports.values()),
        "passed": shared_timeline and all(not item["root_translation_curves_after_extraction"] for item in actor_reports.values()),
        "production_approved": False,
    }
    path = OUTPUT / "review/synthetic-import-smoke.json"
    path.write_text(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit("Synthetic paired import smoke failed")
    print("SYNTHETIC_PAIRED_IMPORT_OK", json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
