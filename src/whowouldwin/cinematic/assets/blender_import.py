"""Blender-native model and animation import for CharacterPackages.

This module deliberately avoids Pydantic so it can be copied beside the standalone
Blender runtime. It creates derived scene data and never saves over source assets.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def load_package_files(manifest_path: str | Path):
    manifest_path = Path(manifest_path).resolve()
    if manifest_path.is_dir():
        manifest_path = manifest_path / "manifest.json"
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    adapter = json.loads(
        _resolve(root, manifest["rig_adapter"]).read_text(encoding="utf-8")
    )
    return root, manifest, adapter


def _link_object(bpy, collection, obj):
    if not obj.users_collection:
        collection.objects.link(obj)


def _append_blend_objects(bpy, model: Path, names: list[str]):
    with bpy.data.libraries.load(str(model), link=False) as (source, target):
        missing = set(names) - set(source.objects)
        if missing:
            raise ValueError("Objects missing from Blender asset: " + ", ".join(sorted(missing)))
        target.objects = names
    return [obj for obj in target.objects if obj is not None]


def _import_exchange_objects(bpy, model: Path):
    before = set(bpy.data.objects)
    suffix = model.suffix.lower()
    if suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(model), automatic_bone_orientation=False)
    elif suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(model), import_shading="NORMALS")
    else:
        raise ValueError(f"Unsupported character model format: {suffix}")
    return [obj for obj in bpy.data.objects if obj not in before]


def _clone_existing(bpy, armature, meshes, character_id):
    rig = armature.copy()
    rig.data = armature.data.copy()
    rig.name = f"WWS_{character_id}_Rig"
    bpy.context.collection.objects.link(rig)
    copies = []
    for source in meshes:
        mesh = source.copy()
        mesh.data = source.data.copy()
        mesh.name = f"WWS_{character_id}_{source.name}_Mesh"
        bpy.context.collection.objects.link(mesh)
        for modifier in mesh.modifiers:
            if modifier.type == "ARMATURE" and modifier.object == armature:
                modifier.object = rig
        if mesh.parent == armature:
            mesh.parent = rig
        copies.append(mesh)
    return rig, copies, [rig, *copies]


def _normalization_roots(bpy, character_id, forward, up, scale):
    from bpy_extras.io_utils import axis_conversion

    trajectory = bpy.data.objects.new(f"WWS_{character_id}_TrajectoryRoot", None)
    normalization = bpy.data.objects.new(f"WWS_{character_id}_NormalizationRoot", None)
    bpy.context.collection.objects.link(trajectory)
    bpy.context.collection.objects.link(normalization)
    normalization.parent = trajectory
    normalization.matrix_parent_inverse.identity()
    conversion = axis_conversion(
        from_forward=forward,
        from_up=up,
        to_forward="-Y",
        to_up="Z",
    ).to_4x4()
    normalization.matrix_basis = conversion
    normalization.scale = (scale, scale, scale)
    return trajectory, normalization


def import_character_model(manifest_path: str | Path, *, character_id: str | None = None):
    """Import a package model into a derived collection and normalize via wrappers."""
    import bpy

    root, manifest, adapter = load_package_files(manifest_path)
    character_id = character_id or manifest["character_id"]
    model = _resolve(root, manifest["model_path"])
    requested = [
        manifest["armature"],
        *manifest["mesh_objects"],
        *manifest.get("accessory_objects", []),
    ]
    if model.suffix.lower() == ".blend":
        imported = _append_blend_objects(bpy, model, requested)
    else:
        imported = _import_exchange_objects(bpy, model)
    armature = next(
        (obj for obj in imported if obj.name == manifest["armature"] and obj.type == "ARMATURE"),
        None,
    )
    meshes = [obj for obj in imported if obj.name in manifest["mesh_objects"] and obj.type == "MESH"]
    accessories = [
        obj for obj in imported
        if obj.name in manifest.get("accessory_objects", [])
    ]
    imported_armatures = [obj for obj in imported if obj.type == "ARMATURE"]
    imported_meshes = [obj for obj in imported if obj.type == "MESH"]
    if armature is None and len(imported_armatures) == 1:
        armature = imported_armatures[0]
    if len(meshes) != len(manifest["mesh_objects"]) and len(imported_meshes) == len(
        manifest["mesh_objects"]
    ):
        meshes = imported_meshes
    if armature is None:
        raise ValueError(f"Imported armature not found: {manifest['armature']}")
    if len(meshes) != len(manifest["mesh_objects"]):
        raise ValueError("One or more manifest mesh objects were not imported")

    collection = bpy.data.collections.new(f"WWS_CHARACTER_{character_id}")
    bpy.context.scene.collection.children.link(collection)
    for obj in imported:
        _link_object(bpy, collection, obj)
    trajectory, normalization = _normalization_roots(
        bpy,
        character_id,
        manifest["forward_axis"],
        manifest["up_axis"],
        manifest["scale"],
    )
    for obj in imported:
        if obj.parent not in imported:
            world = obj.matrix_world.copy()
            obj.parent = normalization
            obj.matrix_world = world
    trajectory["wws_character_package"] = str(Path(manifest_path).resolve())
    trajectory["wws_character_id"] = character_id
    armature["wws_rig_adapter"] = adapter["adapter_id"]
    return {
        "manifest": manifest,
        "adapter": adapter,
        "collection": collection,
        "trajectory_root": trajectory,
        "normalization_root": normalization,
        "rig": armature,
        "meshes": meshes,
        "accessories": accessories,
        "imported_objects": imported,
        "source_model": str(model),
    }


def derive_existing_character(manifest_path: str | Path):
    """Create editable working copies when the package source is the open .blend."""
    import bpy

    _, manifest, adapter = load_package_files(manifest_path)
    armature = bpy.data.objects.get(manifest["armature"])
    meshes = [bpy.data.objects.get(name) for name in manifest["mesh_objects"]]
    if armature is None or armature.type != "ARMATURE" or any(mesh is None for mesh in meshes):
        raise ValueError("Open scene does not contain the package armature and meshes")
    rig, mesh_copies, objects = _clone_existing(
        bpy, armature, meshes, manifest["character_id"]
    )
    collection = bpy.data.collections.new(f"WWS_CHARACTER_{manifest['character_id']}")
    bpy.context.scene.collection.children.link(collection)
    for obj in objects:
        for source_collection in list(obj.users_collection):
            source_collection.objects.unlink(obj)
        collection.objects.link(obj)
    rig["wws_character_package"] = str(Path(manifest_path).resolve())
    rig["wws_character_id"] = manifest["character_id"]
    rig["wws_rig_adapter"] = adapter["adapter_id"]
    armature.hide_viewport = True
    armature.hide_render = True
    for mesh in meshes:
        mesh.hide_viewport = True
        mesh.hide_render = True
    return {
        "manifest": manifest,
        "adapter": adapter,
        "collection": collection,
        "trajectory_root": None,
        "normalization_root": None,
        "rig": rig,
        "meshes": mesh_copies,
        "imported_objects": objects,
        "source_model": str(_resolve(Path(manifest_path).resolve().parent, manifest["model_path"])),
    }


def retarget_package_to_source(binding, source_rig, *, source_body=None):
    """Drive an imported target from standard source motion and source root trajectory."""
    import bpy

    target_rig = binding["rig"]
    trajectory = binding["trajectory_root"] or target_rig
    root_constraint = trajectory.constraints.new("COPY_TRANSFORMS")
    root_constraint.name = "WWS separated root trajectory"
    root_constraint.target = source_rig
    root_constraint.owner_space = "WORLD"
    root_constraint.target_space = "WORLD"

    mapping = binding["adapter"]["standard_to_target"]
    offsets = binding["adapter"].get("rotation_offsets_degrees", {})
    for role, target_name in mapping.items():
        source_bone = source_rig.pose.bones.get(role)
        target_bone = target_rig.pose.bones.get(target_name)
        if source_bone is None or target_bone is None or role == "root":
            continue
        target_bone.rotation_mode = "XYZ"
        if role in offsets:
            target_bone.rotation_euler = tuple(math.radians(value) for value in offsets[role])
        constraint = target_bone.constraints.new("COPY_ROTATION")
        constraint.name = f"WWS retarget {role}"
        constraint.target = source_rig
        constraint.subtarget = role
        try:
            constraint.owner_space = "LOCAL_OWNER_ORIENT"
            constraint.target_space = "LOCAL_OWNER_ORIENT"
        except TypeError:
            constraint.owner_space = "LOCAL"
            constraint.target_space = "LOCAL"
        constraint.mix_mode = "REPLACE"
    source_prefix = source_rig.name.removesuffix("_Rig")
    for role, control_name in (
        ("forearm.R", f"{source_prefix}_IK_hand.R"),
        ("foot.L", f"{source_prefix}_IK_foot.L"),
        ("foot.R", f"{source_prefix}_IK_foot.R"),
    ):
        target_name = mapping.get(role)
        target_bone = target_rig.pose.bones.get(target_name) if target_name else None
        source_bone = source_rig.pose.bones.get(role)
        control = bpy.data.objects.get(control_name)
        source_ik = next(
            (item for item in source_bone.constraints if item.type == "IK"), None
        ) if source_bone else None
        if not target_bone or not control or not source_ik:
            continue
        constraint = target_bone.constraints.new("IK")
        constraint.name = f"WWS contact adaptation {role}"
        constraint.target = control
        constraint.chain_count = 2
        constraint.use_tail = True
        target_bone.ik_stretch = 0.03
        constraint.influence = 0.0
        driver = constraint.driver_add("influence").driver
        variable = driver.variables.new()
        variable.name = "source_influence"
        variable.type = "SINGLE_PROP"
        variable.targets[0].id = source_rig
        escaped = source_ik.name.replace('"', '\\"')
        variable.targets[0].data_path = (
            f'pose.bones["{role}"].constraints["{escaped}"].influence'
        )
        driver.expression = "source_influence"
    if source_body:
        source_body.hide_viewport = True
        source_body.hide_render = True
    return binding


def import_animation_clip(definition: dict, package_root: str | Path):
    """Import an authored Action and its optional source armature without vendor assumptions."""
    import bpy

    root = Path(package_root).resolve()
    path = _resolve(root, definition["path"])
    action_name = definition.get("action_name")
    source_name = definition.get("source_armature")
    if path.suffix.lower() == ".blend":
        with bpy.data.libraries.load(str(path), link=False) as (source, target):
            if action_name and action_name not in source.actions:
                raise ValueError(f"Action '{action_name}' not found in {path}")
            target.actions = [action_name] if action_name else source.actions[:1]
            if source_name:
                if source_name not in source.objects:
                    raise ValueError(f"Animation armature '{source_name}' not found in {path}")
                target.objects = [source_name]
        action = next((item for item in target.actions if item), None)
        source_rig = next((item for item in target.objects if item), None) if source_name else None
    else:
        imported = _import_exchange_objects(bpy, path)
        source_rig = next(
            (obj for obj in imported if obj.type == "ARMATURE" and (not source_name or obj.name == source_name)),
            None,
        )
        if source_rig is None:
            raise ValueError(f"No animation armature found in {path}")
        action = source_rig.animation_data.action if source_rig.animation_data else None
    if action is None:
        raise ValueError(f"No Blender Action found in {path}")
    action = action.copy()
    action.name = f"WWS_IMPORTED_{definition['clip_id']}"
    action["wws_clip_id"] = definition["clip_id"]
    action["wws_action_class"] = definition["action"]
    action["wws_root_motion_policy"] = definition.get("root_motion", "replace")
    action["wws_phases"] = json.dumps(definition.get("phases", {}), sort_keys=True)
    return {"action": action, "source_rig": source_rig, "definition": definition}


def strip_root_motion(action, root_bones=("root", "Root", "Hips", "pelvis")):
    """Remove world translation from a derived Action when trajectories own motion."""
    for curve in list(action.fcurves):
        object_translation = curve.data_path == "location"
        root_bone_translation = curve.data_path.endswith("location") and any(
            f'pose.bones["{bone}"]' in curve.data_path for bone in root_bones
        )
        if object_translation or root_bone_translation:
            action.fcurves.remove(curve)
    return action


def _retarget_imported_action(imported, definition, package_root, target_rig):
    """Bake an arbitrary source armature onto the standard source rig when mapped."""
    import bpy

    source_rig = imported["source_rig"]
    action = imported["action"]
    if source_rig is None:
        return action
    standard_roles = {
        "root", "pelvis", "spine", "chest", "neck", "head", "clavicle.L",
        "clavicle.R", "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R",
        "hand.L", "hand.R", "thigh.L", "thigh.R", "shin.L", "shin.R",
        "foot.L", "foot.R",
    }
    if standard_roles <= {bone.name for bone in source_rig.pose.bones}:
        return action
    adapter_value = definition.get("rig_adapter")
    if not adapter_value:
        raise ValueError(
            f"Clip {definition['clip_id']} uses a non-standard source rig and needs rig_adapter"
        )
    adapter = json.loads(
        _resolve(Path(package_root), adapter_value).read_text(encoding="utf-8")
    )
    temporary_constraints = []
    for role, source_name in adapter["standard_to_target"].items():
        target_bone = target_rig.pose.bones.get(role)
        if role == "root" or not target_bone or source_name not in source_rig.pose.bones:
            continue
        constraint = target_bone.constraints.new("COPY_ROTATION")
        constraint.name = f"WWS temporary clip retarget {role}"
        constraint.target = source_rig
        constraint.subtarget = source_name
        try:
            constraint.owner_space = "LOCAL_OWNER_ORIENT"
            constraint.target_space = "LOCAL_OWNER_ORIENT"
        except TypeError:
            constraint.owner_space = "LOCAL"
            constraint.target_space = "LOCAL"
        temporary_constraints.append((target_bone, constraint))
    source_rig.animation_data_create()
    source_rig.animation_data.action = action
    start, end = (round(value) for value in action.frame_range)
    bpy.ops.object.select_all(action="DESELECT")
    target_rig.select_set(True)
    bpy.context.view_layer.objects.active = target_rig
    target_rig.animation_data_create()
    target_rig.animation_data.action = None
    bpy.ops.nla.bake(
        frame_start=start,
        frame_end=end,
        step=1,
        only_selected=False,
        visual_keying=True,
        clear_constraints=False,
        clear_parents=False,
        use_current_action=False,
        clean_curves=True,
        bake_types={"POSE"},
    )
    baked = target_rig.animation_data.action
    baked.name = f"WWS_RETARGETED_{definition['clip_id']}"
    for bone, constraint in temporary_constraints:
        bone.constraints.remove(constraint)
    return baked


def load_package_animation_overrides(manifest_path, standard_source_rig):
    """Return generic-clip keys mapped to imported/retargeted Blender Actions."""
    root, manifest, _ = load_package_files(manifest_path)
    definitions = {item["clip_id"]: item for item in manifest.get("animation_clips", [])}
    overrides = {}
    for generic_clip, clip_id in manifest.get("custom_animation_overrides", {}).items():
        definition = definitions.get(clip_id)
        if definition is None:
            raise ValueError(f"Undefined animation override clip: {clip_id}")
        imported = import_animation_clip(definition, root)
        action = _retarget_imported_action(
            imported, definition, root, standard_source_rig
        )
        if definition.get("root_motion", "replace") in {"replace", "ignore"}:
            strip_root_motion(action)
        action["wws_character_override_for"] = generic_clip
        overrides[generic_clip] = action
    return overrides


def import_paired_animation_performance(definition, package_root, target_rigs):
    """Import and retarget two synchronized Actions from one approved source.

    The function deliberately keeps the two Actions on their original shared
    timeline.  Spacing and contact adaptation happen only after import.  It is
    Blender-only and accepts a plain dictionary so the module stays portable.
    """
    import bpy

    root = Path(package_root).resolve()
    path = _resolve(root, definition["path"])
    if not path.exists():
        raise FileNotFoundError(f"Paired animation source not found: {path}")
    declared_format = definition.get("format")
    if declared_format and path.suffix.lower().lstrip(".") != declared_format:
        raise ValueError(
            f"Paired source format {declared_format} does not match {path.suffix}"
        )
    provenance = definition.get("provenance", {})
    if not provenance.get("commercial_use_allowed", False):
        raise ValueError("Paired source lacks documented commercial-use permission")
    bindings = {item["actor_id"]: item for item in definition["actors"]}
    if set(bindings) != {"fighter_a", "fighter_b"}:
        raise ValueError("Paired source requires fighter_a and fighter_b bindings")
    imported_objects = []
    loaded_actions = {}
    if path.suffix.lower() == ".blend":
        action_names = [item["action_name"] for item in bindings.values()]
        armature_names = [item["source_armature"] for item in bindings.values()]
        with bpy.data.libraries.load(str(path), link=False) as (source, target):
            missing_actions = set(action_names) - set(source.actions)
            missing_objects = set(armature_names) - set(source.objects)
            if missing_actions or missing_objects:
                raise ValueError(
                    "Paired source missing data: actions=" + ",".join(sorted(missing_actions))
                    + " armatures=" + ",".join(sorted(missing_objects))
                )
            target.actions = action_names
            target.objects = armature_names
        loaded_actions = {action.name: action for action in target.actions if action}
        imported_objects = [obj for obj in target.objects if obj]
        for obj in imported_objects:
            _link_object(bpy, bpy.context.collection, obj)
    else:
        actions_before = set(bpy.data.actions)
        imported_objects = _import_exchange_objects(bpy, path)
        for action in bpy.data.actions:
            if action not in actions_before:
                loaded_actions[action.name] = action
        for obj in imported_objects:
            if obj.type == "ARMATURE" and obj.animation_data and obj.animation_data.action:
                loaded_actions[obj.animation_data.action.name] = obj.animation_data.action
    resolved = {}
    for actor_id, binding in bindings.items():
        source_rig = next((obj for obj in imported_objects if obj.name == binding["source_armature"]), None)
        action = loaded_actions.get(binding["action_name"])
        if source_rig is None or action is None:
            raise ValueError(f"Paired binding unresolved for {actor_id}")
        resolved[actor_id] = (source_rig, action)
    action_ranges = {
        actor_id: tuple(round(float(value), 3) for value in action.frame_range)
        for actor_id, (_, action) in resolved.items()
    }
    if len(set(action_ranges.values())) != 1:
        raise ValueError(f"Paired Actions do not share one timeline: {action_ranges}")
    declared_range = (float(definition["start_frame"]), float(definition["end_frame"]))
    if next(iter(action_ranges.values())) != declared_range:
        raise ValueError(
            f"Paired Action range {next(iter(action_ranges.values()))} does not match declared {declared_range}"
        )
    results = {}
    for actor_id, binding in bindings.items():
        source_rig, action = resolved[actor_id]
        item = {
            "clip_id": definition["performance_id"] + "." + actor_id,
            "action": "paired_exchange",
            "root_motion": definition.get("root_motion", "extract"),
            "rig_adapter": binding["rig_adapter"],
        }
        derived = _retarget_imported_action(
            {"action": action.copy(), "source_rig": source_rig}, item, root, target_rigs[actor_id]
        )
        if item["root_motion"] in {"replace", "ignore", "extract"}:
            strip_root_motion(derived)
        derived["wws_paired_performance"] = definition["performance_id"]
        derived["wws_paired_actor"] = actor_id
        derived["wws_quality_status"] = definition.get("quality_status", "unreviewed")
        results[actor_id] = derived
    return results
