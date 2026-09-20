"""Build the non-destructive source-readiness scene and modest rig controls."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/combat_motion_lab_paired_source_gate"
OUTPUT = ROOT / "outputs/combat_motion_lab_source_readiness"
CONTROL_MODULE = ROOT / "src/whowouldwin/cinematic/assets/rig_controls.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_controls():
    spec = importlib.util.spec_from_file_location("wws_source_readiness_controls", CONTROL_MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for folder in ("source", "review", "renders", "synthetic"):
        (OUTPUT / folder).mkdir(exist_ok=True)
    shutil.copy2(SOURCE / "source/events.json", OUTPUT / "source/events.json")
    shutil.copy2(SOURCE / "source/paired-performance.required.json", OUTPUT / "source/paired-performance.required.json")
    controls_module = load_controls()
    collection = bpy.data.collections.new("WWS_SOURCE_READINESS_CONTROLS")
    bpy.context.scene.collection.children.link(collection)
    mappings = {}
    for fighter in ("fighter_a", "fighter_b"):
        rig = bpy.data.objects[fighter + "_ProductionRig"]
        mappings[fighter] = controls_module.create_cleanup_controls(
            bpy, rig, prefix="WWS_" + fighter, collection=collection
        )
    collection.hide_render = True
    collection.hide_viewport = False
    scene = bpy.context.scene
    scene["wws_source_readiness"] = True
    scene["wws_cleanup_controls_active"] = False
    scene["wws_approved_paired_source"] = False
    scene["wws_source_scene_sha256"] = digest(SOURCE / "scene.blend")
    scene["wws_source_events_sha256"] = digest(OUTPUT / "source/events.json")
    scene["wws_control_module_sha256"] = digest(CONTROL_MODULE)
    scene["wws_build_utc"] = datetime.now(timezone.utc).isoformat()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "scene.blend"))
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scene_sha256": digest(OUTPUT / "scene.blend"),
        "source_scene_sha256": digest(SOURCE / "scene.blend"),
        "events_sha256": digest(OUTPUT / "source/events.json"),
        "event_hash_matches_source": digest(OUTPUT / "source/events.json") == digest(SOURCE / "source/events.json"),
        "control_module_sha256": digest(CONTROL_MODULE),
        "controls": mappings,
        "control_count": sum(len(item) for item in mappings.values()),
        "controls_active": False,
        "visible_motion_changed": False,
        "approved_paired_source_present": False,
    }
    (OUTPUT / "review/source-readiness-provenance.json").write_text(json.dumps(payload, indent=2))
    print("SOURCE_READINESS_BUILT", json.dumps(payload))


if __name__ == "__main__":
    main()
