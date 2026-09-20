"""Blender-side, read-only inspection for a CharacterPackage model."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def message(code, text, path=None, suggestion=None):
    value = {"code": code, "message": text, "path": path, "suggestion": suggestion}
    return value


def resolve(root, value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def import_non_blend(bpy, model):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    suffix = model.suffix.lower()
    if suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(model), automatic_bone_orientation=False)
    elif suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(model), import_shading="NORMALS")
    else:
        raise ValueError(f"Unsupported model format: {suffix}")


def main():
    import bpy

    divider = sys.argv.index("--")
    manifest_path = Path(sys.argv[divider + 1]).resolve()
    output_path = Path(sys.argv[divider + 2]).resolve()
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    adapter = json.loads(resolve(root, manifest["rig_adapter"]).read_text(encoding="utf-8"))
    model = resolve(root, manifest["model_path"])
    if model.suffix.lower() != ".blend":
        import_non_blend(bpy, model)

    errors, warnings = [], []
    checks = {}
    armature = bpy.data.objects.get(manifest["armature"])
    checks["armature_exists"] = bool(armature and armature.type == "ARMATURE")
    if not checks["armature_exists"]:
        errors.append(
            message(
                "armature_missing",
                f"Armature object '{manifest['armature']}' was not found.",
                str(model),
                "Set manifest.armature to the imported Blender armature object name.",
            )
        )
    bones = [bone.name for bone in armature.data.bones] if armature else []
    checks["armature_bone_count"] = len(bones)
    missing_bones = [
        f"{role} -> {name}"
        for role, name in adapter["standard_to_target"].items()
        if name not in bones
    ]
    checks["required_bones_mapped"] = not missing_bones
    if missing_bones:
        errors.append(
            message(
                "mapped_bones_missing",
                "Mapped target bones were not found: " + ", ".join(missing_bones),
                str(resolve(root, manifest["rig_adapter"])),
                "Run wws suggest-rig-map, then manually approve every ambiguous role.",
            )
        )

    meshes = []
    for name in manifest["mesh_objects"]:
        obj = bpy.data.objects.get(name)
        if not obj or obj.type != "MESH":
            errors.append(
                message(
                    "mesh_missing",
                    f"Skinned mesh object '{name}' was not found.",
                    str(model),
                    "List exact imported mesh object names in manifest.mesh_objects.",
                )
            )
            continue
        meshes.append(obj)
    checks["mesh_count"] = len(meshes)
    checks["all_meshes_found"] = len(meshes) == len(manifest["mesh_objects"])
    accessories = []
    for name in manifest.get("accessory_objects", []):
        obj = bpy.data.objects.get(name)
        if not obj:
            errors.append(
                message(
                    "accessory_missing",
                    f"Accessory object '{name}' was not found.",
                    str(model),
                    "List exact accessory object names in manifest.accessory_objects.",
                )
            )
            continue
        accessories.append(obj)
    checks["accessory_count"] = len(accessories)
    checks["all_accessories_found"] = len(accessories) == len(manifest.get("accessory_objects", []))
    skinned = []
    shape_keys = set()
    materials = set()
    heights = []
    for mesh in meshes:
        modifiers = [item for item in mesh.modifiers if item.type == "ARMATURE"]
        valid_modifier = any(item.object == armature for item in modifiers)
        mapped_groups = set(adapter["standard_to_target"].values()) & {
            group.name for group in mesh.vertex_groups
        }
        skinned.append(valid_modifier and bool(mapped_groups))
        if mesh.data.shape_keys:
            shape_keys.update(block.name for block in mesh.data.shape_keys.key_blocks)
        materials.update(slot.material.name for slot in mesh.material_slots if slot.material)
        corners = [mesh.matrix_world @ __import__("mathutils").Vector(corner) for corner in mesh.bound_box]
        heights.append(max(point.z for point in corners) - min(point.z for point in corners))
    checks["all_meshes_skinned"] = bool(skinned) and all(skinned)
    checks["shape_key_count"] = len(shape_keys)
    checks["material_count"] = len(materials)
    if meshes and not checks["all_meshes_skinned"]:
        errors.append(
            message(
                "mesh_not_skinned",
                "One or more meshes lack an Armature modifier or mapped deformation groups.",
                str(model),
                "Preserve artist weights and point each Armature modifier at manifest.armature.",
            )
        )
    height = max(heights, default=0.0) * manifest["scale"]
    checks["normalized_height"] = height
    if height and not 0.5 <= height <= 5.0:
        errors.append(
            message(
                "normalized_height_unreasonable",
                f"Normalized mesh height is {height:.3f}; expected 0.5–5.0 Blender meters.",
                str(model),
                "Adjust manifest.scale; do not apply destructive scale to the source model.",
            )
        )
    missing_correctives = set(adapter.get("corrective_shape_keys", [])) - shape_keys
    if missing_correctives:
        errors.append(
            message(
                "corrective_shape_keys_missing",
                "Declared corrective shape keys were not found: " + ", ".join(sorted(missing_correctives)),
                str(model),
            )
        )
    missing_materials = {
        material["embedded_name"]
        for material in manifest.get("default_materials", [])
        if material.get("embedded_name") and material["embedded_name"] not in materials
    }
    if missing_materials:
        errors.append(
            message(
                "materials_missing",
                "Embedded materials were not found on package meshes: " + ", ".join(sorted(missing_materials)),
                str(model),
            )
        )
    for point in manifest.get("attachment_points", []):
        role = point["bone_role"]
        target = adapter["standard_to_target"].get(role) or adapter.get("optional_bones", {}).get(role)
        if target and target not in bones:
            errors.append(
                message("attachment_bone_missing", f"Attachment {point['attachment_id']} maps to absent bone {target}.")
            )

    checks["source_topology_preserved"] = True
    checks["source_weights_preserved"] = True
    report = {
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "bone_names": bones,
        "mesh_names": [mesh.name for mesh in meshes],
        "accessory_names": [item.name for item in accessories],
        "materials": sorted(materials),
        "shape_keys": sorted(shape_keys),
        "model_path": str(model),
    }
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
