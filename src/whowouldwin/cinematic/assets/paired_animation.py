"""Validation helpers for synchronized two-actor animation sources."""
from __future__ import annotations

from pathlib import Path

from .schemas import PairedPerformanceDefinition, RigAdapterDefinition


def validate_paired_source(definition: PairedPerformanceDefinition, root: str | Path) -> dict:
    """Return actionable source readiness without importing Blender data."""
    root = Path(root).resolve()
    source = Path(definition.path)
    source = source.resolve() if source.is_absolute() else (root / source).resolve()
    errors = []
    warnings = []
    if not source.exists():
        errors.append({
            "code": "paired_source_missing",
            "path": str(source),
            "message": "The synchronized two-actor animation source does not exist.",
            "suggestion": "Supply the approved paired .blend, .fbx, .glb, or .gltf file described by SOURCE_REQUIREMENTS.md.",
        })
    elif source.suffix.lower().lstrip(".") != definition.format.value:
        errors.append({
            "code": "paired_source_format_mismatch",
            "path": str(source),
            "message": f"Manifest format {definition.format.value} does not match {source.suffix}.",
            "suggestion": "Correct the manifest or export the source in the declared format.",
        })
    for actor in definition.actors:
        adapter = Path(actor.rig_adapter)
        adapter = adapter.resolve() if adapter.is_absolute() else (root / adapter).resolve()
        if not adapter.exists():
            errors.append({
                "code": "paired_rig_adapter_missing",
                "actor_id": actor.actor_id,
                "path": str(adapter),
                "message": "The actor-specific source rig adapter is missing.",
                "suggestion": "Map source bone names to the WWS humanoid contract; do not guess ambiguous roles.",
            })
        else:
            try:
                RigAdapterDefinition.model_validate_json(adapter.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append({
                    "code": "paired_rig_adapter_invalid",
                    "actor_id": actor.actor_id,
                    "path": str(adapter),
                    "message": f"The source rig adapter is invalid: {exc}",
                    "suggestion": "Map every required WWS humanoid role to a verified source bone name.",
                })
    if len({actor.source_armature for actor in definition.actors}) != 2:
        errors.append({
            "code": "paired_armatures_not_distinct",
            "message": "The two actors must bind to distinct source armatures.",
            "suggestion": "Export both performers on the same timeline with separate armatures.",
        })
    if len({actor.action_name for actor in definition.actors}) != 2:
        errors.append({
            "code": "paired_actions_not_distinct",
            "message": "The two actors must bind to distinct synchronized Actions.",
            "suggestion": "Name and export one Action/take per performer without changing frame ranges.",
        })
    if not definition.contacts:
        errors.append({
            "code": "paired_contacts_unspecified",
            "message": "No partner-relative contact phases are declared.",
            "suggestion": "Author approach, contact, hold, and release frames before using the performance.",
        })
    if not definition.support_phases:
        errors.append({
            "code": "support_phases_unspecified",
            "message": "No support-foot phases are declared.",
            "suggestion": "Mark planted, heel-release, toe-release, and recovery intervals.",
        })
    elif {phase.actor_id for phase in definition.support_phases} != {"fighter_a", "fighter_b"}:
        errors.append({
            "code": "support_phases_incomplete",
            "message": "Support-foot phases must cover both performers.",
            "suggestion": "Mark planted and heel/ball/toe release phases for fighter_a and fighter_b.",
        })
    for phase in definition.support_phases:
        if None in (
            phase.heel_release_frame,
            phase.ball_release_frame,
            phase.toe_release_frame,
            phase.recovery_frame,
        ):
            errors.append({
                "code": "support_release_metadata_incomplete",
                "actor_id": phase.actor_id,
                "side": phase.side,
                "message": "Support phase lacks heel, ball, toe, or recovery timing.",
                "suggestion": "Review and record all release and trailing-leg recovery frames from the authored source.",
            })
    if not definition.provenance.commercial_use_allowed:
        errors.append({
            "code": "commercial_use_not_granted",
            "message": "The source provenance does not grant commercial use.",
            "suggestion": "Acquire written commercial-use rights before importing into production.",
        })
    if not definition.provenance.redistribution_allowed:
        warnings.append({
            "code": "redistribution_not_granted",
            "message": "The source cannot be redistributed with project assets.",
            "suggestion": "Store it outside distributable packages and retain acquisition records.",
        })
    return {
        "performance_id": definition.performance_id,
        "valid": not errors,
        "source_path": str(source),
        "quality_status": definition.quality_status,
        "errors": errors,
        "warnings": warnings,
    }
