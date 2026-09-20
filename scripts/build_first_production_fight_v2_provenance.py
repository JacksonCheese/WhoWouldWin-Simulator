"""Write final hashes and timestamps for the certified V2 build artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/first_production_fight_v2"


def describe(relative: str) -> dict:
    path = ROOT / relative
    result = {"path": relative, "exists": path.exists()}
    if not path.exists():
        return result
    stat = path.stat()
    result.update({
        "size": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    })
    return result


artifacts = [
    "scripts/blender_first_production_fight_v2.py",
    "scripts/render_first_production_fight_v2_review.py",
    "scripts/build_first_production_fight_v2_review_assets.py",
    "src/whowouldwin/cinematic/blender_backend/base_humanoid.py",
    "assets/characters/base_male_athletic/manifest.json",
    "assets/characters/base_male_athletic/rig_adapter.json",
    "outputs/first_production_fight_v2/scene.blend",
    "outputs/first_production_fight/source/events.json",
    "outputs/first_production_fight_v2/source/events.json",
    "outputs/first_production_fight_v2/review/scene-build-audit.json",
    "outputs/first_production_fight_v2/review/collision_report.json",
    "outputs/first_production_fight_v2/review/mesh_collision_report.json",
    "outputs/first_production_fight_v2/review/mesh_collision_assessment.json",
    "outputs/first_production_fight_v2/review/hand_mesh_clearance_report.json",
    "outputs/first_production_fight_v2/review/camera_report.json",
    "outputs/first_production_fight_v2/review/blender-runtime-diagnostics.json",
    "outputs/first_production_fight_v2/review/collision_contact_sheet.png",
    "outputs/first_production_fight_v2/review/rasengan-contact.mp4",
    "outputs/first_production_fight_v2/renders/clean-motion/fight.mp4",
    "outputs/first_production_fight_v2/renders/collision-debug/fight.mp4",
    "outputs/first_production_fight_v2/renders/quality-preview/fight.mp4",
    "outputs/first_production_fight_v2/review/base_humanoid.blend",
    "outputs/first_production_fight_v2/review/base_humanoid_deformation.mp4",
    "outputs/first_production_fight_v2/review/hand_pose_sheet.png",
    "outputs/first_production_fight_v2/review/v2-certification.md",
    "outputs/first_production_fight_v2/production_review.md",
]

audit_path = OUTPUT / "review/scene-build-audit.json"
audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else None
payload = {
    "schema_version": 2,
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "phase": "final_certified_build",
    "latest_correction": {
        "source": "scripts/blender_first_production_fight_v2.py",
        "needle": "(360, (-0.82, -0.78, 0.03), 0.12)",
        "present": "(360, (-0.82, -0.78, 0.03), 0.12)" in (ROOT / "scripts/blender_first_production_fight_v2.py").read_text(encoding="utf-8"),
    },
    "scene_audit": audit,
    "render_provenance": {
        "method": "All V2 videos were emitted by blender_first_production_fight_v2.py after deterministic scene reconstruction from the recorded builder revision.",
        "embedded_builder_hash_matches_final_source": bool(audit and audit.get("builder_hash_matches_saved_scene")),
    },
    "artifacts": [describe(item) for item in artifacts],
}
(OUTPUT / "review/build-provenance.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(OUTPUT / "review/build-provenance.json")
