"""Record build metadata from the saved First Production Fight V2 scene."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/first_production_fight_v2"
BUILDER = ROOT / "scripts/blender_first_production_fight_v2.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


scene = bpy.context.scene
scene.frame_set(360)
naruto = bpy.data.objects["fighter_b_Rig"]
omni = bpy.data.objects["fighter_a_ProductionRig"]
naruto_production = bpy.data.objects["fighter_b_ProductionRig"]

def bone_point(rig, bone_name):
    bone = rig.pose.bones[bone_name]
    return rig.matrix_world @ bone.tail

omni_hand = bone_point(omni, "Hand_R")
naruto_head = bone_point(naruto_production, "Head")

payload = {
    "schema_version": 1,
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "blend_filepath": bpy.data.filepath,
    "blend_sha256": digest(Path(bpy.data.filepath)),
    "builder_path": str(BUILDER.relative_to(ROOT)),
    "builder_sha256": digest(BUILDER),
    "embedded_builder_sha256": scene.get("wws_builder_sha256"),
    "builder_hash_matches_saved_scene": digest(BUILDER) == scene.get("wws_builder_sha256"),
    "embedded_build_utc": scene.get("wws_build_utc"),
    "embedded_frame360_correction": scene.get("wws_frame360_correction"),
    "frame_range": [scene.frame_start, scene.frame_end],
    "frame_360": {
        "naruto_source_root_location": [round(value, 6) for value in naruto.location],
        "omniman_hand_r_world": [round(value, 6) for value in omni_hand],
        "naruto_head_world": [round(value, 6) for value in naruto_head],
        "hand_r_to_head_bone_distance": round((omni_hand - naruto_head).length, 6),
    },
    "simulation_unchanged": bool(scene.get("wws_simulation_unchanged")),
}
target = OUTPUT / "review/scene-build-audit.json"
target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload, indent=2))
