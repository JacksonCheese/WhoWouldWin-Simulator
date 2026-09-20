"""Build a limited production-skin feasibility scene from the approved root revision.

This script does not edit the paired body or root Actions.  It exposes the existing
Naruto/Omni-Man CharacterPackage assets already carried by the baseline scene and
adds only presentation: hand presets, restrained Rasengan geometry, simple lights,
a minimal stage, and three vertical review cameras.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/combat_motion_lab_hand_authored_root_revision"
OUTPUT = ROOT / "outputs/combat_motion_lab_production_skin_feasibility"
SOURCE_SCENE = SOURCE / "scene.blend"
SCENE_PATH = OUTPUT / "scene.blend"
EXPECTED_EVENTS = "4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861"
PACKAGE_ROOT = ROOT / "outputs/first_production_fight_v2/characters"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base_humanoid = load_module(
    "wws_skin_base_humanoid",
    ROOT / "src/whowouldwin/cinematic/blender_backend/base_humanoid.py",
)


def material(name: str, color, *, roughness=0.5, metallic=0.0, emission=None, strength=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        (bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")).default_value = (*emission, 1.0)
        if bsdf.inputs.get("Emission Strength"):
            bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def look_at(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def create_camera(name: str, location, target, lens: float):
    data = bpy.data.cameras.new(name + "_Data")
    data.lens = lens
    data.sensor_fit = "VERTICAL"
    data.dof.use_dof = False
    camera = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = location
    look_at(camera, target)
    return camera


def cube(name, location, scale, mat, bevel=0.04):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new("Skin-test bevel", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    return obj


def show_character_package_objects():
    wanted = {
        "Naruto_Body", "Naruto_ForeheadProtectorBand", "Naruto_ForeheadPlate",
        "OmniMan_Body", "OmniMan_HairCap", "OmniMan_Cape",
    }
    wanted.update({f"Naruto_HairSpike_{i:02d}" for i in range(13)})
    wanted.update({f"Naruto_Cheek_{side}_{row}" for side in (-1, 1) for row in range(3)})
    wanted.update({f"OmniMan_Mustache_{i}" for i in range(2)})
    for fighter in ("naruto", "omniman"):
        for side in ("L", "R"):
            wanted.add(f"{fighter}_{side}_Palm")
            wanted.add(f"{fighter}_{side}_Thumb")
            wanted.update({f"{fighter}_{side}_Finger_{i}" for i in range(4)})

    for collection in bpy.data.collections:
        collection.hide_render = False
        collection.hide_viewport = False
    def enable_layer_collection(layer_collection):
        layer_collection.exclude = False
        layer_collection.hide_viewport = False
        for child in layer_collection.children:
            enable_layer_collection(child)
    enable_layer_collection(bpy.context.view_layer.layer_collection)
    for obj in bpy.data.objects:
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            obj.hide_render = obj.name not in wanted
            obj.hide_viewport = obj.name not in wanted

    missing = sorted(name for name in wanted if bpy.data.objects.get(name) is None)
    if missing:
        raise RuntimeError(f"CharacterPackage scene objects missing: {missing}")
    for name in wanted:
        obj = bpy.data.objects[name]
        if obj.animation_data and obj.animation_data.action:
            action = obj.animation_data.action
            for curve in list(action.fcurves):
                if curve.data_path in {"hide_render", "hide_viewport"}:
                    action.fcurves.remove(curve)
        obj.hide_render = False
        obj.hide_viewport = False
        obj.hide_set(False)
    return sorted(wanted)


def set_hand_presets():
    controls = {}
    for fighter in ("naruto", "omniman"):
        for side in ("L", "R"):
            prefix = f"{fighter}_{side}"
            controls[prefix] = base_humanoid.HandControls(
                root=bpy.data.objects[prefix + "_HandControl"],
                palm=bpy.data.objects[prefix + "_Palm"],
                fingers=[bpy.data.objects[prefix + f"_Finger_{i}"] for i in range(4)],
                thumb=bpy.data.objects[prefix + "_Thumb"],
            )
    for name in ("omniman_L", "omniman_R"):
        for frame in (1, 108):
            base_humanoid.set_hand_pose(controls[name], "CLOSED_FIST", frame)
    for frame, pose in ((1, "RELAXED"), (65, "RELAXED"), (74, "CUPPED"), (84, "CUPPED"), (90, "OPEN_PALM"), (108, "RELAXED")):
        base_humanoid.set_hand_pose(controls["naruto_R"], pose, frame)
    for frame, pose in ((1, "OPEN_PALM"), (39, "OPEN_PALM"), (68, "RELAXED"), (108, "RELAXED")):
        base_humanoid.set_hand_pose(controls["naruto_L"], pose, frame)
    return sorted(controls)


def simplify_cape():
    cape = bpy.data.objects["OmniMan_Cape"]
    if cape.animation_data:
        cape.animation_data_clear()
    cape.rotation_mode = "XYZ"
    for frame, rotation, scale in (
        (1, (0.0, -0.08, 0.0), (1.0, 1.0, 1.0)),
        (22, (0.02, -0.18, 0.06), (1.0, 0.94, 1.03)),
        (68, (0.0, -0.05, -0.05), (1.0, 1.0, 1.0)),
        (84, (0.0, -0.12, -0.08), (1.0, 0.96, 1.02)),
        (90, (0.08, 0.34, 0.17), (1.0, 0.86, 1.11)),
        (98, (0.04, 0.15, 0.06), (1.0, 0.92, 1.06)),
        (108, (0.0, -0.04, 0.0), (1.0, 1.0, 1.0)),
    ):
        cape.rotation_euler = rotation
        cape.scale = scale
        cape.keyframe_insert("rotation_euler", frame=frame)
        cape.keyframe_insert("scale", frame=frame)
    for curve in cape.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = "BEZIER"
            key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"


def build_stage():
    floor_mat = material("SKINTEST_Floor", (0.035, 0.045, 0.065), roughness=0.78)
    wall_mat = material("SKINTEST_Backdrop", (0.075, 0.095, 0.14), roughness=0.7)
    trim_mat = material("SKINTEST_Trim", (0.18, 0.23, 0.31), roughness=0.5, metallic=0.1)
    floor = cube("SKINTEST_Ground", (0, 0, -0.075), (6.5, 5.0, 0.075), floor_mat, 0.03)
    back = cube("SKINTEST_BackWall", (0, 3.8, 2.1), (6.5, 0.08, 2.1), wall_mat, 0.04)
    trim = cube("SKINTEST_HorizonTrim", (0, 3.69, 0.5), (6.5, 0.035, 0.05), trim_mat, 0.015)
    for obj in (floor, back, trim):
        obj["wws_minimal_environment"] = True
    return [floor.name, back.name, trim.name]


def build_rasengan():
    blue = material("SKINTEST_RasenganCore", (0.015, 0.22, 0.72), roughness=0.18, emission=(0.03, 0.38, 1.0), strength=3.0)
    pale = material("SKINTEST_RasenganSwirl", (0.18, 0.62, 1.0), roughness=0.12, emission=(0.12, 0.52, 1.0), strength=1.7)
    carrier = bpy.data.objects.get("ML_Naruto_hand.R_carrier")
    if not carrier:
        raise RuntimeError("Rasengan hand carrier is absent")
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=0.14)
    core = bpy.context.object
    core.name = "SKINTEST_RasenganCore"
    core.data.materials.append(blue)
    core.parent = carrier
    core.location = (0.0, 0.0, 0.0)
    for axis in range(3):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.17 + 0.014 * axis, minor_radius=0.012, major_segments=32, minor_segments=8)
        ring = bpy.context.object
        ring.name = f"SKINTEST_RasenganRing_{axis}"
        ring.data.materials.append(pale)
        ring.parent = carrier
        ring.location = (0.0, 0.0, 0.0)
        ring.rotation_euler = ((axis == 1) * math.pi / 2, (axis == 2) * math.pi / 2, axis * math.pi / 5)
        for frame, angle in ((68, 0.0), (84, (axis + 1) * math.tau * 1.4), (98, (axis + 1) * math.tau * 2.1)):
            ring.rotation_euler[2] = angle
            ring.keyframe_insert("rotation_euler", frame=frame)
    light_data = bpy.data.lights.new("SKINTEST_RasenganLight_Data", "POINT")
    light_data.color = (0.05, 0.35, 1.0)
    light_data.energy = 42
    light_data.shadow_soft_size = 0.6
    light = bpy.data.objects.new("SKINTEST_RasenganLight", light_data)
    bpy.context.scene.collection.objects.link(light)
    light.parent = carrier
    for obj in [core, *[bpy.data.objects[f"SKINTEST_RasenganRing_{i}"] for i in range(3)]]:
        for frame, scale in ((1, 0.001), (67, 0.001), (72, 0.7), (80, 1.0), (84, 1.0), (90, 0.72), (98, 0.001), (108, 0.001)):
            obj.scale = (scale, scale, scale)
            obj.keyframe_insert("scale", frame=frame)
    return [core.name, *[f"SKINTEST_RasenganRing_{i}" for i in range(3)], light.name]


def build_lighting():
    world = bpy.context.scene.world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.012, 0.02, 0.045, 1.0)
    background.inputs["Strength"].default_value = 0.18
    lights = []
    for name, light_type, location, energy, color, size in (
        ("SKINTEST_Key", "AREA", (-4.0, -4.5, 6.5), 820, (1.0, 0.62, 0.40), 5.0),
        ("SKINTEST_Fill", "AREA", (4.5, -2.5, 4.2), 520, (0.16, 0.35, 1.0), 4.0),
        ("SKINTEST_Rim", "AREA", (1.0, 4.0, 5.5), 950, (0.42, 0.62, 1.0), 3.5),
    ):
        data = bpy.data.lights.new(name + "_Data", light_type)
        data.energy = energy
        data.color = color
        data.shape = "DISK"
        data.size = size
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = location
        look_at(obj, (0.0, 0.3, 1.4))
        lights.append(obj.name)
    return lights


def build_cameras():
    cameras = {
        "shot1": create_camera("SKINTEST_CAM_AttackSlip", (-1.1, -9.5, 3.0), (-0.25, -0.3, 1.34), 48),
        "shot2": create_camera("SKINTEST_CAM_RasenganEntry", (6.6, -7.2, 3.4), (0.48, 0.62, 1.72), 58),
        "shot3": create_camera("SKINTEST_CAM_Recoil", (5.5, -8.5, 3.2), (0.15, 0.48, 1.72), 54),
        "contact": create_camera("SKINTEST_CAM_ContactCloseup", (4.5, -6.1, 2.8), (0.45, 0.58, 1.68), 72),
    }
    target = Vector((0.45, 0.58, 1.76))
    recoil = cameras["shot3"]
    for frame, location, point in (
        (85, (5.5, -8.5, 3.2), target),
        (92, (5.0, -8.65, 3.35), (-0.05, 0.36, 1.55)),
        (98, (4.55, -8.75, 3.4), (-0.25, 0.32, 1.5)),
    ):
        recoil.location = location
        look_at(recoil, point)
        recoil.keyframe_insert("location", frame=frame)
        recoil.keyframe_insert("rotation_euler", frame=frame)
    return {key: obj.name for key, obj in cameras.items()}


def configure_scene(cameras):
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 108
    scene.render.fps = 30
    scene.render.resolution_x = 720
    scene.render.resolution_y = 1280
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 8
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.28
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.camera = bpy.data.objects[cameras["shot1"]]
    for marker in scene.timeline_markers:
        marker.camera = None
    for frame, name, camera in (
        (1, "SKINTEST_01_ATTACK_SLIP", cameras["shot1"]),
        (68, "SKINTEST_02_RASENGAN_ENTRY", cameras["shot2"]),
        (85, "SKINTEST_03_RECOIL", cameras["shot3"]),
    ):
        marker = scene.timeline_markers.new(name, frame=frame)
        marker.camera = bpy.data.objects[camera]


def main():
    if sha256(SOURCE / "source/events.json") != EXPECTED_EVENTS:
        raise RuntimeError("Canonical event log changed before skin feasibility build")
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE_SCENE))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for folder in ("review", "renders/preview", "renders/quality-preview", "renders/contact-closeup", "source"):
        (OUTPUT / folder).mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / "source/events.json", OUTPUT / "source/events.json")
    shutil.copy2(SOURCE / "review/action-provenance.json", OUTPUT / "source/root-revision-action-provenance.json")
    visible = show_character_package_objects()
    hand_controls = set_hand_presets()
    simplify_cape()
    stage = build_stage()
    rasengan = build_rasengan()
    lights = build_lighting()
    cameras = build_cameras()
    configure_scene(cameras)

    package_files = {}
    package_manifests = {}
    for character in ("naruto", "omniman"):
        package = PACKAGE_ROOT / character
        files = [package / "manifest.json", package / "rig_adapter.json", package / "model" / f"{character}_stylized.blend"]
        package_files[character] = {str(path.relative_to(ROOT)): sha256(path) for path in files}
        package_manifests[character] = json.loads((package / "manifest.json").read_text())

    scene = bpy.context.scene
    scene["wws_skin_test_source_scene_sha256"] = sha256(SOURCE_SCENE)
    scene["wws_canonical_events_sha256"] = EXPECTED_EVENTS
    scene["wws_body_actions_unchanged"] = True
    scene["wws_root_actions_unchanged"] = True
    scene["wws_feasibility_only"] = True
    scene.frame_set(1)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(SCENE_PATH))

    report = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_scene": str(SOURCE_SCENE),
        "source_scene_sha256": sha256(SOURCE_SCENE),
        "derived_scene": str(SCENE_PATH),
        "derived_scene_sha256": sha256(SCENE_PATH),
        "canonical_events_sha256": sha256(OUTPUT / "source/events.json"),
        "canonical_expected": EXPECTED_EVENTS,
        "timeline": [1, 108],
        "fps": 30,
        "body_actions": ["HA_BODY_OMNI", "HA_BODY_NARUTO"],
        "root_actions": ["HA_ROOT_fighter_a", "HA_ROOT_fighter_b"],
        "body_and_root_actions_edited": False,
        "package_files": package_files,
        "package_manifest_versions": {key: value["package_version"] for key, value in package_manifests.items()},
        "visible_package_objects": visible,
        "hand_control_presets": hand_controls,
        "presentation_objects": {"stage": stage, "rasengan": rasengan, "lights": lights, "cameras": cameras},
        "selected_source_ranges": {"shot1": [1, 22], "shot2": [68, 84], "shot3": [85, 98]},
        "full_fight_started": False,
        "production_approval_claimed": False,
        "builder_sha256": sha256(Path(__file__)),
    }
    (OUTPUT / "review/build-provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print("PRODUCTION_SKIN_FEASIBILITY_BUILT", report["derived_scene_sha256"])


if __name__ == "__main__":
    main()
