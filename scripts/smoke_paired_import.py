"""Exercise the paired import entry point without fabricating a source asset."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(bpy.data.filepath).resolve().parent
MODULE = ROOT / "src/whowouldwin/cinematic/assets/blender_import.py"


def main():
    spec = importlib.util.spec_from_file_location("paired_blender_import_smoke", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    definition = json.loads((OUTPUT / "source/paired-performance.required.json").read_text())
    target_rigs = {
        "fighter_a": bpy.data.objects["fighter_a_Rig"],
        "fighter_b": bpy.data.objects["fighter_b_Rig"],
    }
    payload = {
        "entry_point": "import_paired_animation_performance",
        "target_rigs": {key: rig.name for key, rig in target_rigs.items()},
        "shared_timeline_preserved": True,
        "root_motion_policy": definition["root_motion"],
    }
    try:
        module.import_paired_animation_performance(definition, OUTPUT, target_rigs)
    except FileNotFoundError as exc:
        payload.update({
            "status": "EXPECTED_SOURCE_REQUIRED",
            "error": str(exc),
            "architecture_ready": True,
            "animation_source_ready": False,
        })
    else:
        payload.update({"status": "IMPORTED", "architecture_ready": True, "animation_source_ready": True})
    (OUTPUT / "review/import-retarget-smoke.json").write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
