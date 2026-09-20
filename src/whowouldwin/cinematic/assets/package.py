"""Load character packages without coupling them to combat data."""

from __future__ import annotations

import json
from pathlib import Path

from .schemas import (
    AbilityDefinition,
    CharacterPackage,
    CharacterPackageManifest,
    RigAdapterDefinition,
    VFXDefinition,
)


def package_manifest_path(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.is_dir():
        path = path / "manifest.json"
    return path


def resolve_package_path(
    root: Path, value: str, *, allow_external: bool = False
) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not allow_external and not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Asset path escapes character package: {value}")
    return resolved


def _load_many(
    root: Path,
    paths: list[str],
    model,
    *,
    allow_external: bool,
) -> list:
    values = []
    for value in paths:
        path = resolve_package_path(root, value, allow_external=allow_external)
        raw = json.loads(path.read_text(encoding="utf-8"))
        records = raw if isinstance(raw, list) else [raw]
        values.extend(model.model_validate(record) for record in records)
    return values


def load_character_package(path: Path) -> CharacterPackage:
    manifest_path = package_manifest_path(path)
    manifest = CharacterPackageManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    root = manifest_path.parent
    adapter_path = resolve_package_path(
        root, manifest.rig_adapter, allow_external=manifest.allow_external_assets
    )
    adapter = RigAdapterDefinition.model_validate_json(
        adapter_path.read_text(encoding="utf-8")
    )
    abilities = _load_many(
        root,
        manifest.ability_definitions,
        AbilityDefinition,
        allow_external=manifest.allow_external_assets,
    )
    vfx = _load_many(
        root,
        manifest.vfx_definitions,
        VFXDefinition,
        allow_external=manifest.allow_external_assets,
    )
    return CharacterPackage(
        root=str(root),
        manifest_path=str(manifest_path),
        manifest=manifest,
        rig_adapter=adapter,
        abilities=abilities,
        vfx=vfx,
    )


def model_path(package: CharacterPackage) -> Path:
    return resolve_package_path(
        Path(package.root),
        package.manifest.model_path,
        allow_external=package.manifest.allow_external_assets,
    )

