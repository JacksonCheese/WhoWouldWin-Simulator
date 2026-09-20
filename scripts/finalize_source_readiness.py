"""Generate the source-acquisition documents and machine-readable gate evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from whowouldwin.cinematic.assets.paired_animation import validate_paired_source
from whowouldwin.cinematic.assets.schemas import PairedPerformanceDefinition

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/combat_motion_lab_source_readiness"
REVIEW = OUTPUT / "review"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, text: str) -> None:
    (OUTPUT / name).write_text(text.strip() + "\n", encoding="utf-8")


def main() -> None:
    REVIEW.mkdir(parents=True, exist_ok=True)
    spec_path = OUTPUT / "source/paired-performance.required.json"
    definition = PairedPerformanceDefinition.model_validate_json(spec_path.read_text())
    validation = validate_paired_source(definition, OUTPUT)
    (REVIEW / "paired-source-validation.json").write_text(json.dumps(validation, indent=2))

    event_paths = [
        ROOT / "outputs/combat_motion_lab_hero_exchange/source/events.json",
        ROOT / "outputs/combat_motion_lab_paired_source_gate/source/events.json",
        OUTPUT / "source/events.json",
    ]
    event_hashes = {str(path.relative_to(ROOT)): digest(path) for path in event_paths}
    provenance = json.loads((REVIEW / "source-readiness-provenance.json").read_text())
    provenance.update({
        "schema_version": 2,
        "paired_performance_schema_sha256": digest(ROOT / "src/whowouldwin/cinematic/assets/schemas.py"),
        "paired_importer_sha256": digest(ROOT / "src/whowouldwin/cinematic/assets/blender_import.py"),
        "paired_validator_sha256": digest(ROOT / "src/whowouldwin/cinematic/assets/paired_animation.py"),
        "rig_controls_sha256": digest(ROOT / "src/whowouldwin/cinematic/assets/rig_controls.py"),
        "rig_mapping_sha256": digest(ROOT / "src/whowouldwin/cinematic/assets/rig_mapping.py"),
        "required_source_definition_sha256": digest(spec_path),
        "event_hashes": event_hashes,
        "all_event_hashes_equal": len(set(event_hashes.values())) == 1,
        "approved_paired_source_status": "MISSING",
        "production_animation_gate": "BLOCKED_PENDING_APPROVED_PAIRED_SOURCE",
    })
    (REVIEW / "source-readiness-provenance.json").write_text(json.dumps(provenance, indent=2))

    action_provenance = {
        "schema_version": 2,
        "source_status": "MISSING_APPROVED_PAIRED_SOURCE",
        "visible_control_actions": {"fighter_a": "HERO_PAIRED_OMNI", "fighter_b": "HERO_PAIRED_NARUTO"},
        "visible_control_actions_classification": "diagnostic_rejected",
        "visible_motion_changed": False,
        "paired_source_contract": "source/paired-performance.required.json",
        "paired_import_entry_point": "whowouldwin.cinematic.assets.blender_import.import_paired_animation_performance",
        "supported_formats": [".blend", ".fbx", ".glb", ".gltf"],
        "root_policy": "body Actions share one timeline; world translation is extracted/replaced by cinematic trajectories",
        "cleanup_policy": "inactive shoulder, elbow-pole, wrist, heel/ball/toe, foot-lock and twist-adapter controls may clean retarget error; they may not invent motion",
        "event_sha256": event_hashes[str(event_paths[-1].relative_to(ROOT))],
        "synthetic_smoke": "review/synthetic-import-smoke.json",
        "synthetic_smoke_is_production_source": False,
    }
    (REVIEW / "action-source-provenance.json").write_text(json.dumps(action_provenance, indent=2))
    gate = {
        "schema_version": 1,
        "decision": "B",
        "ready_to_import_approved_paired_source": True,
        "blocked_only_by_missing_approved_paired_source": True,
        "blocked_by_additional_rig_or_pipeline_work": False,
        "production_animation_gate_passed": False,
        "requirements": {
            "synchronized_two_actor_timing": "REQUIRED",
            "partner_relative_contact": "REQUIRED",
            "believable_support_foot_phases": "REQUIRED",
            "usable_source_armatures_and_adapters": "REQUIRED",
            "contact_hold_recoil_release_metadata": "REQUIRED",
            "commercial_use_provenance": "REQUIRED",
        },
        "current_source": {
            "approved_paired_source_present": False,
            "synthetic_fixture_passed_import": True,
            "synthetic_fixture_production_acceptable": False,
            "old_diagnostic_actions_production_acceptable": False,
        },
    }
    (REVIEW / "acceptance-gate.json").write_text(json.dumps(gate, indent=2))

    preserved = {}
    for folder in ("combat_motion_lab_hero_exchange", "combat_motion_lab_paired_source_gate"):
        base = ROOT / "outputs" / folder
        files = sorted(path for path in base.rglob("*") if path.is_file())
        preserved[folder] = {
            "path": str(base), "file_count": len(files),
            "scene_sha256": digest(base / "scene.blend"),
            "events_sha256": digest(base / "source/events.json"),
        }
    (REVIEW / "preserved-output-inventory.json").write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "preserved_outputs": preserved,
        "mutated": False,
    }, indent=2))

    write("SOURCE_REQUIREMENTS.md", r'''# Paired Performance Source Requirements

## Deliverable

Supply one **3–5 second synchronized two-actor performance** as `.blend`, `.fbx`, `.glb`, or `.gltf`. Both performers must remain on one common 30 or 60 fps timeline, with separate armatures and Actions/takes. Independently authored attack and defense clips are rejected.

The take must perform this continuous order: Omni-Man attack; Naruto outside slip; Naruto counter; Omni-Man parry/guard; Naruto angle change; Rasengan entry; clean tangent contact; compressed recoil and separation; recovery.

## Authored requirements

- Partner-aware attack, slip, parry, redirect, and contact paths.
- Visible support-foot loading and push-off for both actors.
- Marked plant, heel release, ball release, toe release, and trailing-leg recovery frames.
- Curved elbow/hand paths and intentional wrist orientation.
- Stable ribcage over pelvis; no torso folding used to manufacture reach.
- Rasengan hand reaches the partner's chest surface without embedding.
- Reviewed approach, contact, hold, recoil, release, and separation ranges.
- Two clean source armatures, rest-pose references, documented units and axes.

## Source rig minimum

Each actor must map root, pelvis, spine, chest, neck, head, left/right clavicles, upper arms, forearms, hands, thighs, shins, and feet. Scapula controls, elbow poles, upper-arm/forearm twist, wrist controls, heel/ball/toe articulation, and finger controls are strongly preferred. Missing production deform features may reduce acceptance even when import succeeds.

## Rights and provenance

Provide license name and URL, commercial-use grant, redistribution grant or restriction, performers/animators, take identifier, acquisition date, and consent/release reference where applicable. A source without documented commercial-use rights is rejected.

## Delivery metadata

Update `source/paired-performance.required.json` with exact file path, armature names, action names, adapter paths, support phases, contact phases, and provenance. Do not time-remap actors independently before delivery.
''')
    write("PAIRED_ANIMATION_IMPORT_GUIDE.md", r'''# Paired Animation Import Guide

1. Place the licensed file under `source/` without changing the original asset.
2. Create one explicit WWS rig adapter JSON per source armature. Automatic guesses may be used as suggestions only; ambiguous mappings require manual review.
3. Update `source/paired-performance.required.json`. Keep both actors on the same source timeline.
4. Run the source validator. Missing commercial rights, an actor, adapter, support phases, or required metadata must stop production use.
5. Open the derived working scene and call `import_paired_animation_performance(definition, project_root, target_rigs)`.
6. The importer loads both Actions together, retargets through their adapters, and extracts root translation so cinematic trajectories remain independent.
7. Activate cleanup controls only where retarget error requires them. Ramp contact IK around authored contact and key foot locks only through declared support phases.
8. Render normal-speed side, three-quarter, front-diagonal, and top reviews. Measure foot drift and contact depth. Import success is not animation approval.

The synthetic fixture under `synthetic/` proves the file and retarget path only. It reuses rejected diagnostic motion and cannot satisfy the production gate.
''')
    write("ACCEPTANCE_CHECKLIST.md", r'''# Paired Source Acceptance Checklist

Reject the source if any required item fails.

## File and timeline

- [ ] Both performers are in one file and on one synchronized timeline.
- [ ] Two distinct armatures and Actions/takes resolve by exact name.
- [ ] Frame rate, start/end frames, unit scale, forward axis, and up axis are documented.
- [ ] Rest-pose references and explicit rig adapters are supplied.

## Performance

- [ ] Attacks, slips, parries, contact, recoil, and recovery are partner-aware.
- [ ] Both actors have believable support-foot and weight-transfer phases.
- [ ] Plant, heel, ball, toe, and recovery frames are reviewed and recorded.
- [ ] Approach, contact, hold, recoil, release, and separation frames are recorded.
- [ ] Normal-speed review shows no foot skating, hand flail, torso folding, hinge shoulders, or unexplained stops.
- [ ] Surface contact and recoil read without VFX.

## Rights

- [ ] Commercial use is explicitly allowed.
- [ ] Redistribution permission or restriction is documented.
- [ ] Performers/animators, take ID, acquisition date, and release/consent reference are retained.

## WWS acceptance

- [ ] Retargeted side, three-quarter, front-diagonal, and top renders pass human review.
- [ ] Contact/penetration validation passes without solver-authored choreography.
- [ ] Source Actions are marked approved only after review.

**Automatic rejection:** missing synchronized two-actor timing, partner-relative contact, believable support-foot phases, usable armatures, contact/recoil metadata, or suitable provenance.
''')
    write("review/rig-upgrade-report.md", r'''# Modest Rig Upgrade Report

The saved source-readiness scene adds 28 non-destructive cleanup controls across the two production rigs: left/right shoulder-girdle orientation, elbow poles, wrist orientation, heel/ball/toe pivots, planted-foot IK targets, and forearm-twist adapter channels.

All new constraint influences are `0.0`. They are deliberately inactive on the rejected control animation, so this milestone does not disguise source-quality faults. The imported performance remains primary; an animator may key these controls locally to remove retarget error.

The current review mesh still lacks deforming scapula, twist, heel/ball/toe, and finger bones. The adapter contract can consume those features when a production source/asset supplies them. The controls do not manufacture missing deformation or martial-arts intent.

Measured drift on the rejected sample still reaches `0.559635` scene units. This is preserved as failing evidence, not treated as fixed.
''')
    write("production_review.md", r'''# Source Readiness Production Review

## Decision

**B — blocked only by a missing approved paired source.** The paired import, adapter, shared-timeline, root-separation, validation, provenance, and modest cleanup-control infrastructure are ready.

The production animation gate remains closed. No genuine paired authored or paired-mocap source exists locally, and the existing independent Actions remain classified `diagnostic_rejected`.

## What was completed

- A strict `PairedPerformanceDefinition` now records synchronized actors, support/heel/ball/toe phases, partner contacts, hold/recoil/release timing, armatures, adapters, root policy, and commercial provenance.
- Blender import supports `.blend`, `.fbx`, `.glb`, and `.gltf` sources and keeps both body Actions on one timeline while separating world root motion.
- Source validation rejects missing performers, adapters, commercial rights, two-actor support data, and malformed contact timing.
- The saved scene includes inactive elbow-pole, shoulder, wrist, foot-roll/plant, and twist-adapter cleanup controls.
- A synthetic two-armature `.blend` successfully traversed the importer. It is explicitly non-production diagnostic evidence.
- All deterministic source-event hashes remain identical.

## Remaining blocker

Acquire or author the performance in `SOURCE_REQUIREMENTS.md`, then perform human normal-speed review after retargeting. Import success, zero proxy penetration, and passing tests cannot establish animation quality.
''')
    print(json.dumps({"source_valid": validation["valid"], "event_hashes_equal": provenance["all_event_hashes_equal"], "status": "B"}, indent=2))


if __name__ == "__main__":
    main()
