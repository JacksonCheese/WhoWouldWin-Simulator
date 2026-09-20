"""Actionable character-package validation, with optional Blender inspection."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from pydantic import ValidationError

from .animation import resolve_animation
from .package import load_character_package, model_path, package_manifest_path, resolve_package_path
from .schemas import CharacterValidationReport, ValidationMessage


PACKAGE_FOLDERS = ("model", "materials", "animations", "abilities", "vfx", "audio", "metadata")
CORE_ACTIONS = (
    "dash",
    "heavy_cross",
    "hook",
    "kick",
    "dodge",
    "hit_heavy",
    "launch",
    "airborne_tumble",
    "hard_landing",
    "skid",
    "recovery",
)


def find_blender(explicit: Path | None = None) -> Path | None:
    candidates = (
        explicit,
        Path(os.environ["WWS_BLENDER"]) if os.environ.get("WWS_BLENDER") else None,
        Path(found) if (found := shutil.which("blender")) else None,
        Path("/Applications/Blender.app/Contents/MacOS/Blender"),
    )
    return next((path.resolve() for path in candidates if path and path.is_file()), None)


def _error(code: str, message: str, path: Path | None = None, suggestion: str | None = None):
    return ValidationMessage(
        code=code,
        message=message,
        path=str(path) if path else None,
        suggestion=suggestion,
    )


def _blender_inspect(manifest: Path, model: Path, blender: Path) -> dict:
    script = Path(__file__).with_name("blender_inspect.py")
    with tempfile.TemporaryDirectory(prefix="wws-character-") as temporary:
        output = Path(temporary) / "inspection.json"
        command = [str(blender), "--background"]
        if model.suffix.lower() == ".blend":
            command.append(str(model))
        else:
            command.append("--factory-startup")
        command.extend(
            ["--python-exit-code", "1", "--python", str(script), "--", str(manifest), str(output)]
        )
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        if completed.returncode or not output.is_file():
            detail = (completed.stderr or completed.stdout)[-2000:].strip()
            raise RuntimeError(
                f"Blender inspection failed with status {completed.returncode}: {detail}"
            )
        return json.loads(output.read_text(encoding="utf-8"))


def validate_character_package(
    path: Path,
    *,
    blender: Path | None = None,
    inspect_blender: bool = True,
) -> CharacterValidationReport:
    manifest_path = package_manifest_path(path)
    report = CharacterValidationReport(
        package_root=str(manifest_path.parent), valid=False
    )
    if not manifest_path.is_file():
        report.errors.append(
            _error(
                "manifest_missing",
                "Character package has no manifest.json",
                manifest_path,
                "Create the package from assets/characters/README.md.",
            )
        )
        return report
    try:
        package = load_character_package(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        report.errors.append(
            _error("manifest_invalid", str(exc), manifest_path, "Correct the manifest or rig adapter schema.")
        )
        return report

    root = Path(package.root)
    manifest = package.manifest
    adapter = package.rig_adapter
    report.character_id = manifest.character_id
    report.checks["manifest_schema"] = True
    for folder in PACKAGE_FOLDERS:
        if not (root / folder).is_dir():
            report.warnings.append(
                _error(
                    "package_folder_missing",
                    f"Optional package folder is missing: {folder}/",
                    root / folder,
                    "Create it before adding production assets of that type.",
                )
            )

    try:
        source_model = model_path(package)
    except ValueError as exc:
        report.errors.append(_error("model_path_unsafe", str(exc), manifest_path))
        return report
    report.checks["model_exists"] = source_model.is_file()
    if not source_model.is_file():
        report.errors.append(
            _error(
                "model_missing",
                f"Model does not exist: {source_model}",
                source_model,
                "Place a .blend, .fbx, .glb, or .gltf asset at model_path.",
            )
        )
    if manifest.allow_external_assets:
        report.warnings.append(
            _error(
                "external_asset_reference",
                "This package references files outside its own directory.",
                source_model,
                "Copy production assets into model/ before publishing the package.",
            )
        )
    report.checks["scale_declared"] = manifest.scale
    if not 0.01 <= manifest.scale <= 100:
        report.errors.append(
            _error(
                "scale_unreasonable",
                f"Declared normalization scale {manifest.scale} is outside 0.01–100.",
                manifest_path,
                "Use package scale to place an approximately human-sized asset in meters.",
            )
        )
    report.checks["required_bone_roles"] = len(adapter.standard_to_target)

    available_attachments = {point.attachment_id for point in manifest.attachment_points}
    known_roles = set(adapter.standard_to_target) | set(adapter.optional_bones)
    for point in manifest.attachment_points:
        if point.bone_role not in known_roles:
            report.errors.append(
                _error(
                    "attachment_role_unknown",
                    f"Attachment {point.attachment_id} uses unmapped role {point.bone_role}.",
                    manifest_path,
                    "Map the role in rig_adapter.json or change the attachment.",
                )
            )
    report.checks["attachment_points"] = len(available_attachments)
    if not available_attachments:
        report.errors.append(
            _error(
                "attachment_points_missing",
                "No presentation attachment points are declared.",
                manifest_path,
                "Declare at least hand, chest, head, and foot attachment points.",
            )
        )

    clip_ids = {clip.clip_id for clip in manifest.animation_clips}
    for clip in manifest.animation_clips:
        try:
            clip_path = resolve_package_path(
                root, clip.path, allow_external=manifest.allow_external_assets
            )
        except ValueError as exc:
            report.errors.append(_error("animation_path_unsafe", str(exc), manifest_path))
            continue
        if not clip_path.is_file():
            report.errors.append(
                _error(
                    "animation_missing",
                    f"Animation clip file does not exist: {clip_path}",
                    clip_path,
                    "Supply the clip or remove its definition.",
                )
            )
    report.checks["custom_animation_clips"] = len(clip_ids)
    compatible = [action for action in CORE_ACTIONS if resolve_animation(manifest, action)]
    report.checks["core_animation_compatibility"] = len(compatible)
    missing_actions = sorted(set(CORE_ACTIONS) - set(compatible))
    if missing_actions:
        report.errors.append(
            _error(
                "animation_compatibility_missing",
                "No custom or generic-compatible animation for: " + ", ".join(missing_actions),
                manifest_path,
                "Add clips, overrides, or declare generic fallback compatibility.",
            )
        )

    vfx_ids = {item.vfx_id for item in package.vfx}
    for ability in package.abilities:
        if resolve_animation(manifest, ability.animation) is None and ability.animation not in clip_ids:
            report.errors.append(
                _error(
                    "ability_animation_missing",
                    f"Ability {ability.ability_id} references unavailable animation {ability.animation}.",
                    manifest_path,
                )
            )
        missing_vfx = (
            set(ability.startup_vfx + ability.active_vfx + ability.impact_vfx) - vfx_ids
        )
        if missing_vfx:
            report.errors.append(
                _error(
                    "ability_vfx_missing",
                    f"Ability {ability.ability_id} references undefined VFX: {', '.join(sorted(missing_vfx))}.",
                    manifest_path,
                )
            )
        missing_points = set(ability.attachment_points) - available_attachments
        if missing_points:
            report.errors.append(
                _error(
                    "ability_attachment_missing",
                    f"Ability {ability.ability_id} references undefined attachments: {', '.join(sorted(missing_points))}.",
                    manifest_path,
                )
            )
    report.checks["ability_definitions"] = len(package.abilities)
    report.checks["vfx_definitions"] = len(package.vfx)

    if inspect_blender and source_model.is_file():
        executable = find_blender(blender)
        if not executable:
            report.errors.append(
                _error(
                    "blender_missing",
                    "Blender was not found, so armature and skinning could not be inspected.",
                    suggestion="Install Blender or pass --blender; use --skip-blender only for schema checks.",
                )
            )
        else:
            try:
                report.blender = _blender_inspect(manifest_path, source_model, executable)
                for issue in report.blender.get("errors", []):
                    report.errors.append(ValidationMessage.model_validate(issue))
                for issue in report.blender.get("warnings", []):
                    report.warnings.append(ValidationMessage.model_validate(issue))
                report.checks.update(
                    {f"blender_{key}": value for key, value in report.blender.get("checks", {}).items()}
                )
            except RuntimeError as exc:
                report.errors.append(
                    _error(
                        "blender_inspection_failed",
                        str(exc),
                        source_model,
                        "Open the model in Blender and correct import or naming errors.",
                    )
                )
    elif not inspect_blender:
        report.warnings.append(
            _error(
                "blender_inspection_skipped",
                "Armature, weights, shape keys, materials, and embedded actions were not inspected.",
            )
        )

    report.valid = not report.errors
    return report

