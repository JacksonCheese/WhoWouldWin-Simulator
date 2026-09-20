"""Aggregate isolated FBX audits into the Mixamo intake deliverables."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "outputs/combat_motion_lab_source_readiness"
INCOMING = PROJECT / "source/incoming/combat_mixamo"
RAW = PROJECT / "review/combat-mixamo-files"
REVIEW = PROJECT / "review"

CATEGORIES = {
    "BigFrontKick_mixamo.fbx": ["attack_reference", "non_production_retarget_test"],
    "Boxing_mixamo.fbx": ["attack_reference", "non_production_retarget_test"],
    "FightingIdle_mixamo.fbx": ["idle_reference", "non_production_retarget_test"],
    "KnifeFight_mixamo.fbx": ["attack_reference", "non_production_retarget_test"],
    "KnockOut_Loser_mixamo.fbx": ["reaction_reference", "non_production_retarget_test"],
    "KnockOut_Winner_mixamo.fbx": ["reaction_reference", "idle_reference", "non_production_retarget_test"],
    "RoundHouseKick_mixamo.fbx": ["attack_reference", "non_production_retarget_test"],
    "ShadowBoxing_mixamo.fbx": ["attack_reference", "non_production_retarget_test"],
    "SwordFight_mixamo.fbx": ["attack_reference", "non_production_retarget_test"],
    "SwordIdleLight_mixamo.fbx": ["idle_reference", "non_production_retarget_test"],
    "SwordIdleMedium_mixamo.fbx": ["idle_reference", "non_production_retarget_test"],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def primary_action(item: dict) -> dict:
    animated = [action for action in item["actions"] if action["animated_bones"]]
    return max(animated, key=lambda action: (len(action["animated_bones"]), action["fcurve_count"]))


def max_candidate_drift(item: dict) -> float | None:
    values = []
    for rig in item["armatures"]:
        for foot in rig["foot_drift_candidates"]:
            values.extend(window["horizontal_drift"] for window in foot["candidate_contact_windows"])
    return max(values) if values else None


def main() -> None:
    items = [json.loads(path.read_text()) for path in sorted(RAW.glob("*.json"))]
    if {item["filename"] for item in items} != set(CATEGORIES):
        raise SystemExit("Per-file audits do not match the 11-file intake inventory")
    summarized = []
    for item in sorted(items, key=lambda value: value["filename"]):
        action = primary_action(item)
        rig = item["armatures"][0]
        summarized.append({
            "filename": item["filename"],
            "bytes": item["bytes"],
            "sha256": item["sha256"],
            "blender_import_frame_rate": item["scene_frame_rate"],
            "frame_range": item["observed_action_frame_range"],
            "duration_seconds": item["duration_seconds_from_observed_range"],
            "armature_count": item["armature_count"],
            "animated_performer_count": item["animated_performer_count"],
            "armature_name": rig["name"],
            "bone_count": rig["bone_count"],
            "primary_action": action["name"],
            "all_imported_action_names": [entry["name"] for entry in item["actions"]],
            "primary_action_fcurves": action["fcurve_count"],
            "primary_action_animated_bones": len(action["animated_bones"]),
            "root_motion": {
                "has_baked_object_location": bool(action["object_location_curves"]),
                "has_baked_bone_location": bool(action["bone_location_curves"]),
                "hips_world_sample": rig["root_world_samples"].get("mixamorig:Hips"),
                "policy_for_wws_test": "extract",
            },
            "maximum_low_height_candidate_drift": max_candidate_drift(item),
            "drift_measurement_limit": "Low-height windows are numerical candidates, not supplied authored support phases; purposeful travel can be included.",
            "possible_uses": CATEGORIES[item["filename"]],
            "paired_performance_eligible": False,
        })

    event_path = PROJECT / "source/events.json"
    representative = json.loads((REVIEW / "combat-mixamo-diagnostic/representative-retarget-report.json").read_text())
    payload = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "A",
        "classification_text": "Useful only as individual reference/test clips.",
        "archive_label": "Combat.zip",
        "intake_root": str(INCOMING),
        "fbx_count": len(summarized),
        "all_files_imported": True,
        "all_files_single_performer": all(item["animated_performer_count"] == 1 for item in summarized),
        "contains_valid_synchronized_paired_performance": False,
        "blender_timebase_note": "Blender 4.5.13 imported every Action at the scene evaluation rate of 24 fps; no independent native source timebase was supplied.",
        "common_rig": {
            "armature": "mixamorig:Reference",
            "bone_count": 52,
            "wws_required_roles_mappable": 20,
            "wws_required_roles_total": 20,
            "distinct_root_bone": False,
            "root_mapping_note": "Mixamo Hips must serve as both source root reference and pelvis; WWS world root motion remains separate.",
            "available": ["pelvis", "spine chain", "chest", "neck", "head", "clavicles", "arms", "forearms", "hands", "finger chains", "thighs", "shins", "feet", "toe bases"],
            "not_available": ["second performer", "partner targets", "scapula controls", "upper-arm twist bones", "forearm twist bones", "heel controls", "ball-of-foot controls", "IK pole controls"],
        },
        "missing_paired_source_capabilities": {
            "partner_relative_contact": True,
            "synchronized_two_actor_timing": True,
            "authored_parries": True,
            "contact_hold_recoil_release_metadata": True,
            "support_foot_phases": True,
            "heel_ball_toe_release_metadata": True,
            "commercial_use_provenance": True,
        },
        "dedicated_dodge_reference_found": False,
        "representative_diagnostic_retarget": {
            **representative,
            "preview": "review/combat-mixamo-diagnostic/big-front-kick-retarget.mp4",
            "contact_sheet": "review/combat-mixamo-diagnostic/big-front-kick-retarget-contact-sheet.png",
            "visual_assessment": "Imports and retargets, but remains a single unpartnered action. The raw mapping needs rest-pose/orientation cleanup and its measured low-height foot interval drifts; it is not production animation.",
        },
        "files": summarized,
        "production_animation_gate": "CLOSED",
        "canonical_event_sha256": digest(event_path),
        "canonical_event_modified": False,
    }
    (REVIEW / "combat-mixamo-intake.json").write_text(json.dumps(payload, indent=2))

    rows = []
    for item in summarized:
        uses = ", ".join(value.replace("_", " ") for value in item["possible_uses"] if value != "non_production_retarget_test")
        drift = item["maximum_low_height_candidate_drift"]
        rows.append(
            f"| `{item['filename']}` | {item['frame_range'][0]}–{item['frame_range'][1]} | "
            f"{item['duration_seconds']:.2f}s | 1 | `{item['primary_action']}` | {uses} | "
            f"{drift:.6f} |"
        )
    report = f'''# Combat Mixamo Intake Report

## Classification

**A. Useful only as individual reference/test clips.** All 11 FBX files import, but every file contains one animated `mixamorig:Reference` armature and one primary 52-bone humanoid Action. No file contains two animated performers, a shared partner timeline, or partner-authored contact.

The production animation gate remains closed. These files were not copied, renamed, combined, or presented as `paired_hero_exchange.blend`.

## Inventory

Blender 4.5.13 evaluated each import at 24 fps. The durations below use that imported timebase; the archive supplied no separately verified native frame-rate document.

| File | Frames | Duration | Animated performers | Primary Action | Reference use | Max low-height candidate drift |
| --- | ---: | ---: | ---: | --- | --- | ---: |
{chr(10).join(rows)}

The FBX importer also creates small helper Actions for leaf objects. The JSON report preserves every Action name; the table shows the only Action that animates the complete humanoid armature.

## Rig and root motion

All files use the same Mixamo-style 52-bone armature. The required WWS body roles can be mapped, and finger chains plus toe-base bones are present. There is no distinct source root above `mixamorig:Hips`, no scapula or twist bones, and no heel/ball controls. The Actions contain baked translation channels. The diagnostic retarget uses WWS root extraction so body animation remains separate from world trajectory.

## Missing paired-performance requirements

Every file lacks:

- a second synchronized performer;
- partner-relative attack, slip, parry, guard, contact, and recoil paths;
- authored parry/contact timing between two bodies;
- contact, hold, recoil, release, and separation metadata;
- declared support-foot phases;
- heel, ball, toe, and recovery release metadata;
- verified commercial-use provenance for this supplied archive.

There is no dedicated dodge clip in the intake. Attack files may help an animator study shape and timing; knockout files may help reaction reference; idle files may help stance reference. None can establish the required paired exchange.

## Diagnostic retarget

`BigFrontKick_mixamo.fbx` was retargeted to disposable copies of the WWS debug rigs. Production objects and Actions were not modified. Root translation was separated and cleanup controls were left disabled. The test imported technically, but a candidate low-height left-foot interval at frames 81–85 drifted `0.404373` scene units. The preview also remains visibly unpartnered and needs rest-pose/orientation cleanup. It is useful only as a pipeline test.

## Provenance and authority

The files are recorded as extracted from the user-supplied `Combat.zip` archive. Commercial-use rights remain unverified. The simulator and canonical event log were not changed; event SHA-256 remains `{payload['canonical_event_sha256']}`.
'''
    (REVIEW / "combat-mixamo-intake-report.md").write_text(report)

    provenance = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_archive_label": "Combat.zip",
        "extracted_location": str(INCOMING),
        "supplied_by": "user",
        "source_type": "individual_mixamo_fbx_clips",
        "commercial_use_rights": "UNVERIFIED",
        "production_approved": False,
        "paired_performance": False,
        "files": [{"filename": item["filename"], "sha256": item["sha256"]} for item in summarized],
        "canonical_event_sha256": payload["canonical_event_sha256"],
        "existing_provenance_records_replaced": False,
    }
    (REVIEW / "combat-mixamo-provenance.json").write_text(json.dumps(provenance, indent=2))
    print(json.dumps({
        "classification": "A",
        "files": len(summarized),
        "all_single_performer": payload["all_files_single_performer"],
        "gate": "CLOSED",
    }, indent=2))


if __name__ == "__main__":
    main()
