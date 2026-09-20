"""Build the first character-directed WWS cinematic fight.

This script intentionally starts from the validated V4 rig/retarget scene. It keeps
the standard source rigs, continuous skinned bodies, root-motion separation and IK
controls, then replaces the graybox presentation with character packages, authored
character Actions, a staged city block, destruction layers, Rasengan presentation,
and a new 18-second cinematic edit.

Run with Blender 4.5+:

    blender --background outputs/blender_combat_v4_humanoid/scene.blend \
      --python-exit-code 1 --python scripts/blender_first_production_fight.py -- \
      --build
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/first_production_fight"
SOURCE_EVENTS = ROOT / "outputs/blender_combat_v5_assets/source/events.json"
SCENE = bpy.context.scene
FPS = 30
END = 540

runtime_path = ROOT / "src/whowouldwin/cinematic/blender_backend/runtime.py"
runtime_spec = importlib.util.spec_from_file_location("wws_blender_runtime", runtime_path)
rt = importlib.util.module_from_spec(runtime_spec)
assert runtime_spec and runtime_spec.loader
runtime_spec.loader.exec_module(rt)

rt.bpy = bpy
rt.Vector = Vector


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mat(name, color, *, roughness=0.48, metallic=0.0, emission=None, alpha=1.0):
    old = bpy.data.materials.get(name)
    if old:
        return old
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, alpha)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, alpha)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        color_input = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        strength = bsdf.inputs.get("Emission Strength")
        if color_input:
            color_input.default_value = (*emission, 1)
        if strength:
            strength.default_value = 8.0
    if alpha < 1:
        bsdf.inputs["Alpha"].default_value = alpha
        material.surface_render_method = "DITHERED"
    return material


def cube(name, loc, scale, material, bevel=0.05):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("Stylized bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    obj.data.materials.append(material)
    return obj


def sphere(name, loc, scale, material, subdivisions=2):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    return obj


def cylinder(name, loc, radius, depth, material, vertices=16):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def cone(name, loc, radius, depth, material, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=radius, radius2=0.025, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def hide_at(obj, frame, hidden):
    obj.hide_render = hidden
    obj.hide_viewport = hidden
    obj.keyframe_insert("hide_render", frame=frame)
    obj.keyframe_insert("hide_viewport", frame=frame)


def scale_key(obj, frame, scale, interpolation="BEZIER"):
    obj.scale = scale
    obj.keyframe_insert("scale", frame=frame)
    action = obj.animation_data.action if obj.animation_data else None
    if action:
        rt.set_key_interpolation(action, frame, interpolation)


def loc_key(obj, frame, loc, interpolation="BEZIER"):
    obj.location = loc
    obj.keyframe_insert("location", frame=frame)
    action = obj.animation_data.action if obj.animation_data else None
    if action:
        rt.set_key_interpolation(action, frame, interpolation)


def rot_key(obj, frame, rot, interpolation="BEZIER"):
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = rot
    obj.keyframe_insert("rotation_euler", frame=frame)
    action = obj.animation_data.action if obj.animation_data else None
    if action:
        rt.set_key_interpolation(action, frame, interpolation)


def parent_bone(obj, rig, bone_name):
    world = obj.matrix_world.copy()
    obj.parent = rig
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_world = world
    obj["wws_attachment_bone"] = bone_name


def clear_presentation():
    keep = {
        "fighter_a_Rig", "fighter_b_Rig",
        "fighter_a_ProductionRig", "fighter_b_ProductionRig",
        "fighter_a_ProductionBody", "fighter_b_ProductionBody",
        "fighter_a_IK_hand.R", "fighter_b_IK_hand.R",
        "fighter_a_IK_foot.L", "fighter_a_IK_foot.R",
        "fighter_b_IK_foot.L", "fighter_b_IK_foot.R",
    }
    for obj in list(bpy.data.objects):
        if obj.name not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    for name in ("fighter_a_SkinnedBody", "fighter_b_SkinnedBody"):
        obj = bpy.data.objects.get(name)
        if obj:
            obj.hide_render = obj.hide_viewport = True
    for marker in list(SCENE.timeline_markers):
        SCENE.timeline_markers.remove(marker)
    for rig_name in ("fighter_a_Rig", "fighter_b_Rig"):
        rig = bpy.data.objects[rig_name]
        if rig.animation_data:
            for track in list(rig.animation_data.nla_tracks):
                rig.animation_data.nla_tracks.remove(track)
            rig.animation_data.action = bpy.data.actions.new(rig_name + "_FirstProductionRoot")
        else:
            rig.animation_data_create()
            rig.animation_data.action = bpy.data.actions.new(rig_name + "_FirstProductionRoot")
        rig.location = (0, 0, 0)
        rig.rotation_euler = (0, 0, 0)
        rig.scale = (1, 1, 1)
        for bone in rig.pose.bones:
            bone.rotation_mode = "XYZ"
            bone.rotation_euler = (0, 0, 0)
            for constraint in bone.constraints:
                if constraint.type == "IK":
                    constraint.influence = 0
    for rig_name in ("fighter_a_ProductionRig", "fighter_b_ProductionRig"):
        rig = bpy.data.objects[rig_name]
        rig.hide_render = rig.hide_viewport = False
    bpy.data.objects["fighter_a_ProductionBody"].hide_render = False
    bpy.data.objects["fighter_a_ProductionBody"].hide_viewport = False
    bpy.data.objects["fighter_b_ProductionBody"].hide_render = False
    bpy.data.objects["fighter_b_ProductionBody"].hide_viewport = False


def assign_character_materials():
    skin = mat("CHAR_Skin", (0.72, 0.43, 0.28), roughness=0.62)
    naruto_orange = mat("Naruto_Orange", (0.95, 0.22, 0.025), roughness=0.5)
    naruto_black = mat("Naruto_Black", (0.015, 0.022, 0.035), roughness=0.58)
    omni_red = mat("Omni_Red", (0.55, 0.015, 0.025), roughness=0.38)
    omni_white = mat("Omni_White", (0.82, 0.85, 0.86), roughness=0.42)
    boot = mat("Boot_Dark", (0.035, 0.035, 0.045), roughness=0.6)
    for body_name, palette in (
        ("fighter_b_ProductionBody", (skin, naruto_orange, naruto_black, boot)),
        ("fighter_a_ProductionBody", (skin, omni_red, omni_white, boot)),
    ):
        body = bpy.data.objects[body_name]
        body.name = "Naruto_Body" if body_name.startswith("fighter_b") else "OmniMan_Body"
        body.data.materials.clear()
        for material in palette:
            body.data.materials.append(material)
        groups = body.vertex_groups
        for poly in body.data.polygons:
            scores = {}
            for vi in poly.vertices:
                for item in body.data.vertices[vi].groups:
                    scores[groups[item.group].name] = scores.get(groups[item.group].name, 0.0) + item.weight
            primary = max(scores, key=scores.get) if scores else ""
            if any(token in primary for token in ("Head", "Neck", "Hand")):
                poly.material_index = 0
            elif any(token in primary for token in ("Foot", "LowerLeg")):
                poly.material_index = 3
            elif body.name.startswith("Naruto"):
                poly.material_index = 2 if any(token in primary for token in ("Arm", "Shoulder", "SpineUpper")) else 1
            else:
                poly.material_index = 1 if any(token in primary for token in ("Arm", "Shoulder", "LowerLeg", "Foot")) else 2
        if body.name.startswith("Omni"):
            body.scale.y = 1.13
            body.scale.x = 1.07
    return {
        "skin": skin, "naruto_orange": naruto_orange, "naruto_black": naruto_black,
        "omni_red": omni_red, "omni_white": omni_white, "boot": boot,
    }


def create_character_features(mats):
    naruto_rig = bpy.data.objects["fighter_b_ProductionRig"]
    omni_rig = bpy.data.objects["fighter_a_ProductionRig"]
    blond = mat("Naruto_Hair", (1.0, 0.68, 0.025), roughness=0.42)
    band = mat("Naruto_Headband", (0.018, 0.055, 0.12), roughness=0.5)
    metal = mat("Headband_Metal", (0.55, 0.62, 0.7), roughness=0.25, metallic=0.75)
    dark = mat("Omni_Hair", (0.018, 0.012, 0.015), roughness=0.7)
    cape_mat = mat("Omni_Cape", (0.65, 0.01, 0.02), roughness=0.52)

    features = {"naruto": [], "omniman": []}
    # Naruto's radial spikes give a readable silhouette even in profile.
    center = Vector((0, 0, 2.69))
    for index in range(13):
        angle = 2 * math.pi * index / 13
        radial = Vector((0.07 * math.cos(angle), 0.27 * math.sin(angle), 0.11))
        spike = cone(
            f"Naruto_HairSpike_{index:02d}", center + radial,
            0.095, 0.48, blond,
            rotation=(0.5 * math.sin(angle), 0.5 * math.cos(angle), angle),
        )
        parent_bone(spike, naruto_rig, "Head")
        features["naruto"].append(spike)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.285, minor_radius=0.042, major_segments=24, minor_segments=8, location=(0, 0, 2.56))
    headband = bpy.context.object
    headband.name = "Naruto_ForeheadProtectorBand"
    headband.data.materials.append(band)
    parent_bone(headband, naruto_rig, "Head")
    features["naruto"].append(headband)
    plate = cube("Naruto_ForeheadPlate", (0.278, 0, 2.58), (0.035, 0.17, 0.075), metal, 0.025)
    parent_bone(plate, naruto_rig, "Head")
    features["naruto"].append(plate)
    # Simple cheek marks improve close-read without pursuing likeness.
    for side in (-1, 1):
        for row in range(3):
            mark = cube(f"Naruto_Cheek_{side}_{row}", (0.278, side * (0.105 + row * 0.028), 2.44 - row * 0.025), (0.014, 0.025, 0.008), dark, 0)
            rot_key(mark, 1, (0, 0.28 * side, 0))
            parent_bone(mark, naruto_rig, "Head")
            features["naruto"].append(mark)

    hair_cap = sphere("OmniMan_HairCap", (0, 0, 2.67), (0.245, 0.285, 0.17), dark, 2)
    parent_bone(hair_cap, omni_rig, "Head")
    features["omniman"].append(hair_cap)
    for index, y in enumerate((-0.075, 0.075)):
        mustache = cube(f"OmniMan_Mustache_{index}", (0.285, y, 2.43), (0.025, 0.085, 0.025), dark, 0.025)
        rot_key(mustache, 1, (0.12, 0, -0.22 if y < 0 else 0.22))
        parent_bone(mustache, omni_rig, "Head")
        features["omniman"].append(mustache)
    cape = cube("OmniMan_Cape", (-0.16, 0, 1.63), (0.035, 0.48, 0.76), cape_mat, 0.06)
    parent_bone(cape, omni_rig, "SpineUpper")
    features["omniman"].append(cape)
    cape.rotation_mode = "XYZ"
    for frame, rot, scale in (
        (1, (0, -0.08, 0), (1, 1, 1)),
        (48, (0, -0.18, 0), (1, 1, 1)),
        (66, (0, 0.72, 0), (1, 0.82, 1.22)),
        (115, (0, -0.5, 0.12), (1, 1, 1.05)),
        (285, (0, 0.25, 0), (1, 1, 1)),
        (370, (0, -0.55, -0.18), (1, 0.9, 1.1)),
        (420, (0, 0.7, 0.3), (1, 0.8, 1.25)),
        (490, (0, -0.35, 0), (1, 1, 1.05)),
        (540, (0, -0.08, 0), (1, 1, 1)),
    ):
        cape.rotation_euler = rot
        cape.scale = scale
        cape.keyframe_insert("rotation_euler", frame=frame)
        cape.keyframe_insert("scale", frame=frame)
    return features


def create_city():
    asphalt = mat("City_Asphalt", (0.055, 0.065, 0.078), roughness=0.84)
    concrete = mat("City_Concrete", (0.31, 0.33, 0.36), roughness=0.72)
    curb = mat("City_Curb", (0.52, 0.54, 0.55), roughness=0.68)
    lane = mat("City_Lane", (0.92, 0.72, 0.12), roughness=0.66)
    glass = mat("City_Glass", (0.045, 0.16, 0.23), roughness=0.18, metallic=0.15)
    brick = mat("City_Brick", (0.32, 0.075, 0.055), roughness=0.77)
    stone = mat("City_Stone", (0.16, 0.2, 0.25), roughness=0.69)
    neon = mat("City_Neon", (0.04, 0.45, 0.75), roughness=0.3, emission=(0.04, 0.45, 0.75))
    metal = mat("City_Metal", (0.08, 0.1, 0.13), roughness=0.38, metallic=0.65)
    car_a = mat("Car_Blue", (0.025, 0.16, 0.32), roughness=0.34, metallic=0.5)
    car_b = mat("Car_Yellow", (0.8, 0.36, 0.025), roughness=0.38, metallic=0.35)
    red = mat("Utility_Red", (0.65, 0.025, 0.02), roughness=0.52)
    dark = mat("City_Dark", (0.025, 0.03, 0.04), roughness=0.7)
    dust_mat = mat("Dust", (0.44, 0.37, 0.28), roughness=1.0, alpha=0.38)
    debris_mat = mat("Broken_Concrete", (0.25, 0.24, 0.23), roughness=0.9)

    collection = bpy.data.collections.new("WWS_CITY_STREET")
    SCENE.collection.children.link(collection)
    created = []
    road = cube("City_Road", (0, 0, -0.18), (32, 5.3, 0.18), asphalt, 0.08)
    created.append(road)
    for side in (-1, 1):
        created.append(cube(f"Sidewalk_{side}", (0, side * 6.15, 0.02), (32, 0.85, 0.2), concrete, 0.08))
        created.append(cube(f"Curb_{side}", (0, side * 5.38, 0.10), (32, 0.08, 0.28), curb, 0.025))
    for x in range(-28, 31, 6):
        created.append(cube(f"LaneMark_{x}", (x, 0, 0.015), (1.8, 0.07, 0.025), lane, 0.01))
    # Modular facades, with alley gaps and taller background volumes.
    facade_specs = [(-25, 7.4, 6, 5.5, brick), (-13, 7.4, 5, 4.5, stone), (-1, 7.4, 5, 6.5, brick), (12, 7.4, 6, 5, stone), (25, 7.4, 5, 7, brick)]
    facade_specs += [(x, -7.4, w, h, stone if i % 2 else brick) for i, (x, w, h) in enumerate([(-25, 6, 6), (-12, 5, 7), (0, 5, 4.5), (12, 5, 6), (25, 6, 5.5)])]
    for idx, (x, y, width, height, material) in enumerate(facade_specs):
        building = cube(f"Facade_{idx:02d}", (x, y, height / 2), (width, 1.15, height / 2), material, 0.12)
        created.append(building)
        toward_road = y - math.copysign(1.18, y)
        # Storefront opening, door, awning and repeated windows.
        created.append(cube(f"StoreGlass_{idx}", (x, toward_road, 1.35), (width * 0.55, 0.035, 1.05), glass, 0.02))
        created.append(cube(f"Door_{idx}", (x - width * 0.68, toward_road - math.copysign(0.01, y), 1.15), (0.48, 0.05, 1.15), dark, 0.02))
        created.append(cube(f"Awning_{idx}", (x, toward_road - math.copysign(0.16, y), 2.55), (width * 0.72, 0.4, 0.13), neon if idx % 3 == 0 else lane, 0.04))
        for floor in range(2, int(height // 1.4) + 1):
            for offset in (-0.55, 0, 0.55):
                created.append(cube(f"Window_{idx}_{floor}_{offset}", (x + offset * width, toward_road, floor * 1.28), (0.52, 0.035, 0.43), glass, 0.015))
    for idx, (x, y, sx, sy, h) in enumerate(((-22, 12, 5, 4, 13), (-6, 13, 4, 4, 17), (11, 12, 5, 4, 14), (25, -13, 6, 4, 16), (5, -13, 4, 4, 12), (-18, -14, 5, 4, 15))):
        created.append(cube(f"BackgroundTower_{idx}", (x, y, h / 2), (sx, sy, h / 2), stone if idx % 2 else brick, 0.12))
    # Street furniture and hero-readable vehicles.
    for idx, (x, side) in enumerate(((-20, -1), (-2, 1), (16, -1), (27, 1))):
        pole = cylinder(f"StreetlightPole_{idx}", (x, side * 5.75, 2.2), 0.065, 4.4, metal, 12)
        arm = cube(f"StreetlightArm_{idx}", (x, side * 5.35, 4.25), (0.055, 0.4, 0.055), metal, 0.02)
        lamp = cube(f"StreetlightLamp_{idx}", (x, side * 4.95, 4.15), (0.24, 0.15, 0.09), neon, 0.03)
        created += [pole, arm, lamp]
    for idx, (x, y, color) in enumerate(((-18, -3.9, car_a), (5, 4.05, car_b), (22, -3.9, car_a))):
        car = cube(f"ParkedCar_{idx}", (x, y, 0.58), (1.8, 0.82, 0.48), color, 0.18)
        cabin = cube(f"ParkedCarCabin_{idx}", (x + 0.1, y, 1.15), (0.92, 0.72, 0.42), glass, 0.12)
        created += [car, cabin]
        for dx in (-1.15, 1.15):
            for dy in (-0.72, 0.72):
                wheel = cylinder(f"CarWheel_{idx}_{dx}_{dy}", (x + dx, y + dy, 0.35), 0.28, 0.18, dark, 16)
                wheel.rotation_euler[0] = math.pi / 2
                created.append(wheel)
    hydrant = cylinder("FireHydrant", (-7, -5.8, 0.42), 0.18, 0.7, red, 12)
    created.append(hydrant)
    for idx, x in enumerate((-11, 10)):
        bin_obj = cube(f"TrashContainer_{idx}", (x, 5.8, 0.55), (0.48, 0.36, 0.55), dark, 0.08)
        created.append(bin_obj)
    # Traffic signal at the far intersection.
    created.append(cylinder("TrafficPole", (29, -5.7, 2.5), 0.09, 5, metal, 12))
    signal = cube("TrafficSignal", (29, -5.65, 4.7), (0.25, 0.22, 0.58), dark, 0.04)
    created.append(signal)
    for i, color in enumerate(((0.7, 0.02, 0.01), (0.85, 0.45, 0.01), (0.01, 0.55, 0.08))):
        light_mat = mat(f"Signal_{i}", color, emission=color)
        created.append(sphere(f"SignalLight_{i}", (28.76, -5.65, 5.05 - i * 0.32), (0.055, 0.12, 0.1), light_mat, 1))

    # Crash wall and staged destruction at Omni-Man's overshoot location.
    crash_wall = cube("CrashWall_Intact", (-10.5, 6.24, 1.9), (2.6, 0.12, 1.9), brick, 0.04)
    created.append(crash_wall)
    hide_at(crash_wall, 1, False)
    hide_at(crash_wall, 109, False)
    hide_at(crash_wall, 110, True)
    broken = cube("CrashWall_BrokenState", (-10.5, 6.25, 1.9), (2.6, 0.10, 1.9), debris_mat, 0.02)
    created.append(broken)
    hide_at(broken, 1, True)
    hide_at(broken, 109, True)
    hide_at(broken, 110, False)
    # An irregular dark breach makes the swap visually legible.
    breach = sphere("CrashWall_Breach", (-10.5, 6.02, 1.75), (1.25, 0.08, 1.05), dark, 2)
    created.append(breach)
    hide_at(breach, 1, True)
    hide_at(breach, 110, False)
    debris = []
    for idx in range(18):
        dx = ((idx * 37) % 17 - 8) * 0.12
        dz = 0.5 + ((idx * 19) % 12) * 0.16
        chunk = cube(f"WallDebris_{idx:02d}", (-10.5 + dx, 5.9, dz), (0.11 + (idx % 3) * 0.04, 0.08, 0.09 + (idx % 4) * 0.03), debris_mat, 0.02)
        hide_at(chunk, 1, True)
        hide_at(chunk, 108, True)
        hide_at(chunk, 110, False)
        loc_key(chunk, 110, chunk.location)
        loc_key(chunk, 126, (chunk.location.x + dx * 1.4, 3.7 - (idx % 4) * 0.25, max(0.12, dz * 0.25)))
        rot_key(chunk, 110, (0, 0, 0))
        rot_key(chunk, 126, (idx * 0.7, idx * 0.45, idx * 0.32))
        debris.append(chunk)
    dust = []
    for idx in range(8):
        cloud = sphere(f"CrashDust_{idx}", (-10.5 + (idx - 4) * 0.3, 5.8, 0.5 + (idx % 3) * 0.45), (0.2, 0.2, 0.2), dust_mat, 1)
        scale_key(cloud, 1, (0, 0, 0), "CONSTANT")
        scale_key(cloud, 109, (0, 0, 0), "CONSTANT")
        scale_key(cloud, 118, (1.2, 1.0, 1.1))
        scale_key(cloud, 145, (2.1, 1.5, 1.7))
        hide_at(cloud, 146, True)
        dust.append(cloud)

    # Rasengan collateral layer: road cracks, crater, windows and displaced vehicle.
    crater = cylinder("Rasengan_RoadCrater", (0.6, 0.9, 0.01), 1.45, 0.035, dark, 24)
    scale_key(crater, 1, (0, 0, 0), "CONSTANT")
    scale_key(crater, 372, (0, 0, 0), "CONSTANT")
    scale_key(crater, 379, (1, 1, 1))
    created.append(crater)
    for idx in range(8):
        angle = idx * math.pi / 4
        crack = cube(f"RoadCrack_{idx}", (0.6 + math.cos(angle), 0.9 + math.sin(angle), 0.025), (1.3, 0.025, 0.018), dark, 0)
        crack.rotation_euler[2] = angle
        scale_key(crack, 1, (0, 0, 0), "CONSTANT")
        scale_key(crack, 374, (0, 0, 0), "CONSTANT")
        scale_key(crack, 382, (1, 1, 1))
        created.append(crack)
    damaged_car = bpy.data.objects.get("ParkedCar_1")
    if damaged_car:
        loc_key(damaged_car, 365, damaged_car.location)
        loc_key(damaged_car, 387, (damaged_car.location.x + 0.8, damaged_car.location.y + 0.65, 0.72))
        rot_key(damaged_car, 365, (0, 0, 0))
        rot_key(damaged_car, 387, (0.12, -0.1, 0.32))
    # Organize procedurally-created objects under the city collection.
    for obj in created + debris + dust:
        for col in list(obj.users_collection):
            col.objects.unlink(obj)
        collection.objects.link(obj)
    return {"collection": collection, "materials": {"dust": dust_mat, "debris": debris_mat}, "crash_debris": debris}


def make_action(rig, name, frames, *, phases=None):
    root_action = rig.animation_data.action
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    action["wws_authored_character_clip"] = True
    if phases:
        action["wws_phases"] = json.dumps(phases)
    rig.animation_data.action = action
    rt.reset_pose(rig)
    for frame, rotations in frames:
        rt.key_pose(rig, frame, rotations)
    for curve in action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = "BEZIER"
            key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"
    rig.animation_data.action = root_action
    rt.reset_pose(rig)
    return action


def merged(*poses):
    result = dict(rt.POSES["combat_stance"])
    for pose in poses:
        result.update(pose)
    return result


def build_character_actions():
    omni = bpy.data.objects["fighter_a_Rig"]
    naruto = bpy.data.objects["fighter_b_Rig"]
    ninja_stance = {
        "pelvis": (0, 0.28, 0.05), "spine": (0, 0.42, -0.08), "chest": (0, -0.18, 0.12),
        "upper_arm.L": (-1.05, 0.08, -0.78), "forearm.L": (-0.95, 0.1, 0.12),
        "upper_arm.R": (-0.42, -0.1, 0.78), "forearm.R": (-1.18, 0.05, -0.15),
        "thigh.L": (0.48, 0.05, 0.03), "thigh.R": (-0.35, -0.04, -0.05),
        "shin.L": (-0.42, 0, 0), "shin.R": (0.35, 0, 0),
    }
    ninja_dash = merged({
        "pelvis": (0, -0.55, -0.08), "spine": (0, 1.18, 0.08), "chest": (0, 0.52, -0.15),
        "head": (0, -0.35, 0), "upper_arm.L": (-1.45, 0, -0.85), "upper_arm.R": (0.95, 0, 0.9),
        "thigh.L": (0.82, 0, 0), "thigh.R": (-0.78, 0, 0), "shin.L": (-0.65, 0, 0),
    })
    body_dodge = merged({
        "pelvis": (0, -0.42, -0.75), "spine": (0, -0.76, -1.02), "chest": (0, -0.28, -0.62),
        "head": (0, 0.22, 0.38), "upper_arm.L": (0.5, 0, -0.55), "upper_arm.R": (-1.2, 0, 0.45),
        "thigh.L": (0.9, 0, 0), "thigh.R": (-0.68, 0, 0), "shin.L": (-0.72, 0, 0),
    })
    charge = merged({
        "pelvis": (0, 0.3, -0.18), "spine": (0, 0.4, 0.22), "chest": (0, -0.25, 0.35),
        "head": (0, 0.18, -0.2), "upper_arm.L": (-0.82, 0.05, -0.55), "forearm.L": (-1.22, 0, 0.15),
        "upper_arm.R": (-1.35, 0.05, 0.35), "forearm.R": (-1.45, 0, -0.2),
        "thigh.L": (0.55, 0, 0), "thigh.R": (-0.45, 0, 0), "shin.L": (-0.52, 0, 0),
    })
    rasengan_contact = merged({
        "pelvis": (0, 0.38, -0.52), "spine": (0, 0.55, -0.68), "chest": (0, 0.32, -0.62),
        "head": (0, -0.16, 0.22), "clavicle.R": (0, 0, -0.38),
        "upper_arm.R": (0.05, 0, -1.44), "forearm.R": (0.12, 0, 0),
        "upper_arm.L": (-1.2, 0, -0.75), "forearm.L": (-0.65, 0, 0),
        "thigh.L": (-0.48, 0, 0), "thigh.R": (0.62, 0, 0),
    })
    flight = merged({
        "spine": (0, 1.32, 0), "chest": (0, 0.38, 0), "head": (0, -0.38, 0),
        "upper_arm.L": (-0.3, 0, -0.4), "upper_arm.R": (-0.3, 0, 0.4),
        "forearm.L": (-0.18, 0, 0), "forearm.R": (-0.18, 0, 0),
        "thigh.L": (-0.12, 0, 0), "thigh.R": (0.12, 0, 0),
    })
    super_punch_ant = merged({
        "pelvis": (0, -0.22, 0.48), "spine": (0, -0.38, 0.7), "chest": (0, -0.18, 0.62),
        "upper_arm.R": (-1.72, 0, 0.98), "forearm.R": (-1.1, 0, 0),
        "upper_arm.L": (-0.55, 0, -0.42), "forearm.L": (-0.75, 0, 0),
    })
    super_punch_contact = merged({
        "pelvis": (0, 0.32, -0.55), "spine": (0, 0.48, -0.74), "chest": (0, 0.25, -0.68),
        "clavicle.R": (0, 0, -0.36), "upper_arm.R": (0.15, 0, -1.48), "forearm.R": (0.04, 0, 0),
        "upper_arm.L": (-0.85, 0, -0.45), "forearm.L": (-0.7, 0, 0),
    })
    block = merged({
        "spine": (0, -0.18, 0.15), "chest": (0, -0.12, 0.25),
        "upper_arm.L": (-1.1, 0, -0.88), "forearm.L": (-1.25, 0, 0.1),
        "upper_arm.R": (-1.05, 0, 0.86), "forearm.R": (-1.22, 0, -0.1),
    })
    omni_hit = merged({
        "pelvis": (0, -0.72, 0.75), "spine": (0, -1.12, 1.0), "chest": (0, -0.65, 0.85),
        "head": (0, 0.62, -0.48), "upper_arm.L": (1.25, 0, 0.85), "upper_arm.R": (-1.3, 0, -1.0),
        "forearm.L": (-0.48, 0, 0.2), "forearm.R": (-0.62, 0, -0.15),
        "thigh.L": (0.72, 0, 0), "thigh.R": (-0.58, 0, 0),
    })
    actions = {
        "naruto": {
            "ninja_stance": make_action(naruto, "WWS_CHAR_naruto_ninja_stance", [(1, ninja_stance), (20, merged({"spine": (0, 0.34, -0.04)})), (40, ninja_stance)]),
            "body_dodge": make_action(naruto, "WWS_CHAR_naruto_body_dodge", [(1, ninja_stance), (5, merged({"pelvis": (0, -0.3, -0.35)})), (9, body_dodge), (14, body_dodge), (21, ninja_stance)], phases=(5, 9, 14, 21)),
            "substitution_evade": make_action(naruto, "WWS_CHAR_naruto_substitution_evade", [(1, ninja_stance), (4, body_dodge), (7, merged(rt.POSES["air_dodge"])), (12, ninja_stance)], phases=(3, 6, 8, 12)),
            "ninja_dash": make_action(naruto, "WWS_CHAR_naruto_ninja_dash", [(1, ninja_stance), (4, ninja_dash), (13, ninja_dash), (18, rasengan_contact), (24, ninja_stance)], phases=(4, 10, 18, 24)),
            "rasengan_charge": make_action(naruto, "WWS_CHAR_naruto_rasengan_charge", [(1, ninja_stance), (7, charge), (18, charge), (28, merged({**charge, "chest": (0, -0.35, 0.45)})), (36, charge)], phases=(7, 18, 28, 36)),
            "rasengan_attack": make_action(naruto, "WWS_CHAR_naruto_rasengan_attack", [(1, charge), (5, ninja_dash), (10, rasengan_contact), (13, rasengan_contact), (19, merged(rt.POSES["punch_followthrough"])), (26, ninja_stance)], phases=(5, 10, 15, 26)),
            "melee_redirect": make_action(naruto, "WWS_CHAR_naruto_melee_redirect", [(1, ninja_stance), (4, body_dodge), (8, merged(rt.POSES["punch_contact"])), (12, block), (16, charge)], phases=(4, 8, 12, 16)),
        },
        "omniman": {
            "flight_blitz": make_action(omni, "WWS_CHAR_omniman_flight_blitz", [(1, merged(rt.POSES["combat_stance"])), (5, super_punch_ant), (8, flight), (18, flight), (23, super_punch_contact), (27, flight)], phases=(5, 12, 23, 27)),
            "flight_brake": make_action(omni, "WWS_CHAR_omniman_flight_brake", [(1, flight), (6, merged(rt.POSES["dash_stop"])), (13, merged(rt.POSES["wall_impact"])), (20, merged(rt.POSES["recovery"]))], phases=(6, 10, 14, 20)),
            "airborne_turn": make_action(omni, "WWS_CHAR_omniman_airborne_turn", [(1, flight), (6, merged({**flight, "chest": (0, 0.3, 0.75)})), (12, super_punch_ant), (18, merged(rt.POSES["combat_stance"]))]),
            "super_punch": make_action(omni, "WWS_CHAR_omniman_super_punch", [(1, merged(rt.POSES["combat_stance"])), (7, super_punch_ant), (11, super_punch_contact), (14, merged(rt.POSES["punch_followthrough"])), (20, block)], phases=(7, 11, 14, 20)),
            "impact_launch": make_action(omni, "WWS_CHAR_omniman_impact_launch", [(1, block), (4, omni_hit), (7, omni_hit), (13, merged(rt.POSES["launch"])), (20, merged(rt.POSES["airborne_knockback"])), (28, merged(rt.POSES["air_dodge"]))], phases=(3, 4, 10, 28)),
            "midair_recovery": make_action(omni, "WWS_CHAR_omniman_midair_recovery", [(1, merged(rt.POSES["airborne_knockback"])), (7, merged({**rt.POSES["air_dodge"], "chest": (0, 0.1, -0.65)})), (14, flight), (21, merged(rt.POSES["combat_stance"]))], phases=(6, 12, 17, 21)),
            "power_block": make_action(omni, "WWS_CHAR_omniman_power_block", [(1, merged(rt.POSES["combat_stance"])), (4, block), (12, block), (17, super_punch_ant)]),
        },
    }
    return actions


def add_strip(rig, action, start, end, *, blend=2, repeat=1.0):
    track = rig.animation_data.nla_tracks.new()
    track.name = f"CHAR_{action.name}_{start:03d}"
    strip = track.strips.new(track.name, start, action)
    strip.action_frame_start, strip.action_frame_end = action.frame_range
    strip.frame_start, strip.frame_end = start, end
    strip.blend_type = "REPLACE"
    strip.extrapolation = "NOTHING"
    strip.blend_in = blend
    strip.blend_out = blend
    strip.repeat = repeat
    return strip


def key_root(rig, frame, loc, yaw, *, tilt=0, roll=0, interpolation="BEZIER", scale=(1, 1, 1)):
    rig.location = loc
    rig.rotation_mode = "XYZ"
    rig.rotation_euler = (roll, tilt, yaw)
    rig.scale = scale
    rig.keyframe_insert("location", frame=frame)
    rig.keyframe_insert("rotation_euler", frame=frame)
    rig.keyframe_insert("scale", frame=frame)
    action = rig.animation_data.action
    rt.set_key_interpolation(action, frame, interpolation)


def setup_choreography(actions):
    omni = bpy.data.objects["fighter_a_Rig"]
    naruto = bpy.data.objects["fighter_b_Rig"]
    face = math.atan2(2.7, -13.0)
    # Character clips remain the primary body-motion source.
    add_strip(omni, actions["omniman"]["power_block"], 1, 45, blend=4)
    add_strip(omni, actions["omniman"]["flight_blitz"], 42, 105, blend=3)
    add_strip(omni, actions["omniman"]["flight_brake"], 101, 145, blend=2)
    add_strip(omni, actions["omniman"]["airborne_turn"], 145, 220, blend=4)
    add_strip(omni, actions["omniman"]["super_punch"], 268, 314, blend=2)
    add_strip(omni, actions["omniman"]["power_block"], 311, 359, blend=2)
    add_strip(omni, actions["omniman"]["impact_launch"], 357, 438, blend=1)
    add_strip(omni, actions["omniman"]["midair_recovery"], 430, 502, blend=3)
    add_strip(omni, actions["omniman"]["power_block"], 495, 540, blend=5)

    add_strip(naruto, actions["naruto"]["ninja_stance"], 1, 58, blend=3)
    add_strip(naruto, actions["naruto"]["body_dodge"], 55, 95, blend=2)
    add_strip(naruto, actions["naruto"]["substitution_evade"], 88, 136, blend=2)
    add_strip(naruto, actions["naruto"]["ninja_dash"], 132, 175, blend=3)
    add_strip(naruto, actions["naruto"]["rasengan_charge"], 168, 238, blend=4)
    add_strip(naruto, actions["naruto"]["ninja_dash"], 228, 284, blend=2)
    add_strip(naruto, actions["naruto"]["melee_redirect"], 278, 352, blend=1)
    add_strip(naruto, actions["naruto"]["rasengan_attack"], 342, 398, blend=1)
    add_strip(naruto, actions["naruto"]["ninja_stance"], 390, 540, blend=5, repeat=3.0)

    # Root motion is authored separately: bursts have nonlinear spacing and aerial banking.
    for frame, loc, yaw, tilt, roll, interp in (
        (1, (7.5, -0.5, 0), face, 0, 0, "BEZIER"),
        (42, (7.5, -0.5, 0), face, 0, 0, "BEZIER"),
        (50, (7.1, -0.4, 0.15), face, -0.15, 0, "BEZIER"),
        (56, (5.5, -0.05, 0.45), face, -0.38, 0.08, "BEZIER"),
        (61, (1.8, 0.7, 0.75), face, -0.58, 0.12, "LINEAR"),
        (65, (-3.4, 1.75, 0.7), face, -0.62, 0.15, "LINEAR"),
        (70, (-7.7, 3.5, 0.65), face, -0.45, 0.18, "LINEAR"),
        (78, (-10.0, 5.55, 0.5), face, -0.15, 0.25, "BEZIER"),
        (105, (-10.5, 5.85, 0.1), face, 0.45, -0.1, "BEZIER"),
        (118, (-10.35, 5.6, 0.12), face, 0.15, -0.28, "BEZIER"),
        (145, (-9.6, 4.9, 0.15), -0.15, 0, 0, "BEZIER"),
        (205, (-7.4, 3.1, 0.15), -0.15, 0, 0, "BEZIER"),
        (250, (-5.0, 1.7, 0.08), math.pi + 0.08, 0, 0, "BEZIER"),
        (278, (-2.7, 0.75, 0.05), math.pi + 0.02, 0, 0, "BEZIER"),
        (304, (-1.9, 0.55, 0.05), math.pi, 0, 0, "BEZIER"),
        (330, (-1.0, 0.45, 0.05), math.pi, 0, 0, "BEZIER"),
        (357, (0.32, 0.72, 0.05), math.pi, 0, 0, "BEZIER"),
        (368, (0.55, 0.78, 0.05), math.pi, 0, 0, "CONSTANT"),
        (371, (0.55, 0.78, 0.05), math.pi, 0, 0, "CONSTANT"),
        (380, (2.1, 0.9, 1.5), math.pi + 0.35, -0.18, 0.35, "BEZIER"),
        (397, (7.2, 1.2, 4.8), math.pi + 1.15, -0.35, 0.62, "LINEAR"),
        (418, (13.5, 1.7, 6.6), math.pi + 2.0, -0.15, 1.0, "BEZIER"),
        (440, (17.6, 2.0, 5.1), 0.1, -0.3, -0.45, "BEZIER"),
        (462, (19.0, 1.5, 3.4), math.pi + 0.1, -0.05, 0.12, "BEZIER"),
        (488, (16.2, 1.0, 3.0), math.pi + 0.08, 0, 0, "BEZIER"),
        (540, (13.2, 0.8, 2.8), math.pi + 0.05, 0, 0, "BEZIER"),
    ):
        key_root(omni, frame, loc, yaw, tilt=tilt, roll=roll, interpolation=interp)
    for frame, loc, yaw, tilt, roll, interp in (
        (1, (-5.8, 2.2, 0), 0.02, 0, 0, "BEZIER"),
        (55, (-5.8, 2.2, 0), 0.02, 0, 0, "BEZIER"),
        (63, (-5.7, 2.0, 0), 0.02, 0, 0, "BEZIER"),
        (69, (-5.15, 0.2, 0.2), 0.25, 0, -0.38, "BEZIER"),
        (78, (-4.8, -1.55, 0.08), 0.55, 0, -0.18, "BEZIER"),
        (98, (-4.3, -1.8, 0), 1.1, 0, 0, "BEZIER"),
        (132, (-4.3, -1.8, 0), 1.1, 0, 0, "BEZIER"),
        (146, (-2.4, -3.4, 0.35), 1.35, -0.1, 0.15, "BEZIER"),
        (162, (-0.8, -3.5, 0), 1.72, 0, 0, "BEZIER"),
        (228, (-0.8, -3.5, 0), 1.72, 0, 0, "BEZIER"),
        (246, (-1.1, -2.6, 0), 1.65, 0, 0, "BEZIER"),
        (272, (-1.6, -0.3, 0.08), 1.2, -0.12, 0, "BEZIER"),
        (289, (-2.25, 0.25, 0), 0.1, 0, -0.12, "BEZIER"),
        (302, (-2.25, -0.7, 0), 0.12, 0, -0.35, "BEZIER"),
        (318, (-1.7, -0.2, 0), 0.05, 0, 0.2, "BEZIER"),
        (332, (-0.6, -0.65, 0), 0.55, 0, -0.25, "BEZIER"),
        (347, (-0.55, 0.05, 0), 0.08, 0, 0, "BEZIER"),
        (365, (-0.35, 0.45, 0), 0.03, 0, 0, "BEZIER"),
        (368, (-0.35, 0.45, 0), 0.03, 0, 0, "CONSTANT"),
        (371, (-0.35, 0.45, 0), 0.03, 0, 0, "CONSTANT"),
        (386, (0.35, 0.48, 0), 0.02, 0, 0, "BEZIER"),
        (420, (0.1, 0.35, 0), 0.0, 0, 0, "BEZIER"),
        (500, (0.1, 0.35, 0), 0.0, 0, 0, "BEZIER"),
        (540, (1.3, 0.15, 0.15), 0.0, -0.12, 0, "BEZIER"),
    ):
        key_root(naruto, frame, loc, yaw, tilt=tilt, roll=roll, interpolation=interp)

    # Contact adaptation keeps the Rasengan hand on the target through the 3-frame hold.
    control = bpy.data.objects["fighter_b_IK_hand.R"]
    constraint = next(c for c in naruto.pose.bones["forearm.R"].constraints if c.type == "IK")
    for frame, influence, loc in (
        (1, 0.0, (-5, 0, 1.5)),
        (170, 0.0, (-0.4, -3.6, 1.35)),
        (184, 0.82, (-0.35, -3.3, 1.48)),
        (225, 0.82, (-0.3, -3.25, 1.52)),
        (238, 0.0, (-0.2, -2.8, 1.5)),
        (342, 0.0, (-0.2, 0.2, 1.6)),
        (358, 0.85, (0.48, 0.72, 1.55)),
        (365, 1.0, (0.52, 0.77, 1.58)),
        (371, 1.0, (0.52, 0.77, 1.58)),
        (379, 0.0, (0.8, 0.8, 1.5)),
    ):
        loc_key(control, frame, loc, "BEZIER")
        constraint.influence = influence
        constraint.keyframe_insert("influence", frame=frame)
    return omni, naruto


def create_rasengan(naruto_rig, ik_control):
    blue = mat("Rasengan_Core", (0.02, 0.48, 1.0), roughness=0.15, emission=(0.02, 0.55, 1.0))
    cyan = mat("Rasengan_Swirl", (0.15, 0.85, 1.0), roughness=0.12, emission=(0.1, 0.75, 1.0), alpha=0.75)
    white = mat("Rasengan_HotCore", (0.75, 0.96, 1.0), roughness=0.08, emission=(0.6, 0.95, 1.0))
    root = bpy.data.objects.new("Rasengan_Control", None)
    bpy.context.collection.objects.link(root)
    constraint = root.constraints.new("COPY_LOCATION")
    constraint.target = ik_control
    core = sphere("Rasengan_Core", (0, 0, 0), (0.28, 0.28, 0.28), blue, 3)
    core.parent = root
    hot = sphere("Rasengan_HotCore", (0, 0, 0), (0.12, 0.12, 0.12), white, 2)
    hot.parent = root
    rings = []
    for idx, rotation in enumerate(((0, 0, 0), (math.pi / 2, 0, 0), (0, math.pi / 2, 0), (0.65, 0.5, 0.2))):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.34 + idx * 0.035, minor_radius=0.026, major_segments=28, minor_segments=7)
        ring = bpy.context.object
        ring.name = f"Rasengan_Swirl_{idx}"
        ring.data.materials.append(cyan)
        ring.parent = root
        ring.rotation_euler = rotation
        for frame, spin in ((170, 0), (230, 6 + idx), (342, 12 + idx * 2), (365, 18 + idx * 3), (371, 20 + idx * 3), (392, 25 + idx * 4)):
            ring.rotation_euler[2] = rotation[2] + spin
            ring.rotation_euler[0] = rotation[0] + spin * (0.18 + idx * 0.03)
            ring.keyframe_insert("rotation_euler", frame=frame)
        rings.append(ring)
    light_data = bpy.data.lights.new("Rasengan_Light", type="POINT")
    light_data.color = (0.05, 0.45, 1.0)
    light_data.energy = 0
    light_data.shadow_soft_size = 1.2
    light = bpy.data.objects.new("Rasengan_Light", light_data)
    bpy.context.collection.objects.link(light)
    light.parent = root
    for frame, scale, energy in ((1, (0, 0, 0), 0), (178, (0, 0, 0), 0), (192, (0.45, 0.45, 0.45), 250), (220, (1, 1, 1), 700), (342, (1.05, 1.05, 1.05), 900), (365, (0.72, 0.72, 0.72), 1300), (371, (0.72, 0.72, 0.72), 1300), (378, (1.45, 1.45, 1.45), 1600), (392, (0, 0, 0), 0)):
        scale_key(root, frame, scale, "BEZIER")
        light.data.energy = energy
        light.data.keyframe_insert("energy", frame=frame)
    # Energy trail is a tapered path aligned with Naruto's final approach.
    trail = cube("Rasengan_EnergyTrail", (-0.4, 0.2, 1.55), (0.9, 0.025, 0.025), cyan, 0.025)
    scale_key(trail, 1, (0, 0, 0), "CONSTANT")
    scale_key(trail, 343, (0, 0, 0), "CONSTANT")
    scale_key(trail, 360, (1, 1, 1))
    scale_key(trail, 363, (0, 0, 0))
    scale_key(trail, 378, (0, 0, 0))
    scale_key(trail, 390, (0, 0, 0))
    # Shockwave starts after readable contact, not over it.
    bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.035, major_segments=40, minor_segments=8, location=(0.55, 0.77, 1.55), rotation=(math.pi / 2, 0, 0))
    shock = bpy.context.object
    shock.name = "Rasengan_ImpactShockwave"
    shock.data.materials.append(cyan)
    scale_key(shock, 1, (0, 0, 0), "CONSTANT")
    scale_key(shock, 371, (0, 0, 0), "CONSTANT")
    scale_key(shock, 378, (2.2, 2.2, 2.2))
    scale_key(shock, 390, (5.5, 5.5, 5.5))
    hide_at(shock, 396, True)
    return {"root": root, "core": core, "rings": rings, "shockwave": shock, "trail": trail}


def create_takeoff_and_impact_vfx(city):
    dust_mat = city["materials"]["dust"]
    blue = bpy.data.materials["Rasengan_Swirl"]
    for group, frame, origin, count in (("Takeoff", 48, (7.2, -0.5, 0.25), 8), ("Impact", 373, (0.6, 0.8, 0.35), 12)):
        for idx in range(count):
            angle = 2 * math.pi * idx / count
            cloud = sphere(f"{group}_Dust_{idx}", origin, (0.1, 0.1, 0.1), dust_mat, 1)
            scale_key(cloud, 1, (0, 0, 0), "CONSTANT")
            scale_key(cloud, frame - 1, (0, 0, 0), "CONSTANT")
            loc_key(cloud, frame, origin)
            loc_key(cloud, frame + 16, (origin[0] + math.cos(angle) * (1.5 if group == "Takeoff" else 2.8), origin[1] + math.sin(angle) * (1.2 if group == "Takeoff" else 2.4), origin[2] + 0.4 + (idx % 3) * 0.25))
            scale_key(cloud, frame + 6, (0.8, 0.8, 0.8))
            scale_key(cloud, frame + 22, (1.6, 1.6, 1.6))
            hide_at(cloud, frame + 24, True)
    # Thin impact arcs reinforce direction without obscuring bodies.
    for idx in range(5):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.55 + idx * 0.12, minor_radius=0.018, major_segments=32, minor_segments=6, location=(0.55, 0.77, 1.58), rotation=(math.pi / 2, 0.3 * idx, 0))
        arc = bpy.context.object
        arc.name = f"ImpactArc_{idx}"
        arc.data.materials.append(blue)
        scale_key(arc, 1, (0, 0, 0), "CONSTANT")
        scale_key(arc, 371, (0, 0, 0), "CONSTANT")
        scale_key(arc, 378 + idx, (1.5, 1.5, 1.5))
        hide_at(arc, 390 + idx, True)


def camera(name, location, lens, target_location):
    data = bpy.data.cameras.new(name + "Data")
    data.lens = lens
    data.sensor_width = 32
    cam = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(cam)
    cam.location = location
    target = bpy.data.objects.new(name + "_Target", None)
    bpy.context.collection.objects.link(target)
    target.location = target_location
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    return cam, target


def camera_key(cam, target, frame, cam_loc, target_loc, lens=None, interpolation="BEZIER"):
    loc_key(cam, frame, cam_loc, interpolation)
    loc_key(target, frame, target_loc, interpolation)
    if lens is not None:
        cam.data.lens = lens
        cam.data.keyframe_insert("lens", frame=frame)


def add_camera_cut(cam, frame, label):
    marker = SCENE.timeline_markers.new(label, frame=frame)
    marker.camera = cam


def create_cameras():
    shots = []
    cam, target = camera("SHOT01_LowFaceoff", (-10.4, 4.65, 1.35), 40, (6.2, -0.25, 1.48))
    camera_key(cam, target, 1, (-10.4, 4.65, 1.35), (6.2, -0.25, 1.48), 40)
    camera_key(cam, target, 41, (-9.6, 4.3, 1.26), (6.8, -0.35, 1.52), 46)
    shots.append((1, cam, "01 FACE OFF"))
    cam, target = camera("SHOT02_FlightBlitz", (10.0, -4.75, 1.65), 29, (5.8, 0.0, 1.45))
    camera_key(cam, target, 42, (10.0, -4.75, 1.65), (5.8, 0.0, 1.45), 29)
    camera_key(cam, target, 60, (3.8, -4.7, 1.95), (1.4, 0.8, 1.65), 34, "LINEAR")
    camera_key(cam, target, 70, (-4.0, -4.65, 1.95), (-6.2, 2.2, 1.55), 38, "LINEAR")
    shots.append((42, cam, "02 FLIGHT BLITZ"))
    cam, target = camera("SHOT03_NarrowDodge", (-2.0, -4.75, 1.75), 35, (-5.4, 1.25, 1.4))
    camera_key(cam, target, 62, (-2.0, -4.75, 1.75), (-5.4, 1.25, 1.4), 35)
    camera_key(cam, target, 86, (-6.2, -4.7, 1.55), (-7.4, 3.5, 1.5), 38)
    shots.append((62, cam, "03 NARROW DODGE"))
    cam, target = camera("SHOT04_WallCrash", (-15.0, -0.4, 2.2), 37, (-10.4, 5.7, 1.6))
    camera_key(cam, target, 88, (-15.0, -0.4, 2.2), (-10.4, 5.7, 1.6), 37)
    camera_key(cam, target, 128, (-13.5, 0.8, 1.7), (-10.4, 5.8, 1.45), 46)
    shots.append((88, cam, "04 STOREFRONT CRASH"))
    cam, target = camera("SHOT05_WhipReveal", (-7.0, -4.75, 2.25), 31, (-4.0, 0.0, 1.45))
    camera_key(cam, target, 132, (-7.0, -4.75, 2.25), (-5.8, 1.9, 1.45), 31)
    camera_key(cam, target, 148, (-5.0, -4.7, 1.95), (-2.3, -3.2, 1.4), 38, "LINEAR")
    camera_key(cam, target, 165, (-3.8, -4.65, 1.8), (-0.8, -3.5, 1.4), 44, "LINEAR")
    shots.append((132, cam, "05 WHIP REVEAL"))
    cam, target = camera("SHOT06_RasenganCharge", (-2.0, -4.95, 1.8), 46, (-0.45, -3.3, 1.5))
    camera_key(cam, target, 170, (-2.15, -4.95, 1.8), (-0.45, -3.3, 1.52), 46)
    camera_key(cam, target, 228, (-1.8, -4.75, 1.72), (-0.35, -3.25, 1.5), 52)
    shots.append((170, cam, "06 RASENGAN CHARGE"))
    cam, target = camera("SHOT07_Pursuit", (-3.2, -5.4, 2.5), 44, (-2.0, -0.6, 1.6))
    camera_key(cam, target, 229, (-1.4, -5.8, 2.2), (-1.0, -2.5, 1.45), 44)
    camera_key(cam, target, 278, (-3.2, -4.4, 1.65), (-2.6, 0.6, 1.5), 58, "LINEAR")
    shots.append((229, cam, "07 PURSUIT"))
    cam, target = camera("SHOT08_CloseExchange", (-2.0, -5.3, 1.75), 50, (-1.7, 0.35, 1.5))
    camera_key(cam, target, 279, (-2.4, -5.3, 1.7), (-2.0, 0.25, 1.5), 50)
    camera_key(cam, target, 330, (0.2, -4.5, 1.55), (-1.1, 0.2, 1.45), 56, "LINEAR")
    shots.append((279, cam, "08 CLOSE EXCHANGE"))
    cam, target = camera("SHOT09_RasenganHero", (-0.2, -5.4, 1.9), 56, (0.1, 0.58, 1.55))
    camera_key(cam, target, 342, (-0.6, -5.2, 1.9), (0.0, 0.55, 1.55), 52)
    camera_key(cam, target, 365, (-0.15, -4.8, 1.72), (0.18, 0.62, 1.55), 62)
    # Three-frame contact hold, then a small directional kick.
    camera_key(cam, target, 371, (-0.15, -4.8, 1.72), (0.18, 0.62, 1.55), 62, "CONSTANT")
    camera_key(cam, target, 381, (-0.55, -4.3, 1.92), (1.1, 0.8, 1.8), 54)
    shots.append((342, cam, "09 RASENGAN IMPACT"))
    cam, target = camera("SHOT10_LaunchTrack", (1.5, -4.7, 3.0), 34, (4.0, 1.0, 3.3))
    camera_key(cam, target, 382, (1.5, -4.7, 3.0), (3.0, 1.0, 3.2), 34)
    camera_key(cam, target, 418, (10.0, -4.6, 5.2), (13.5, 1.7, 8.0), 36, "LINEAR")
    camera_key(cam, target, 438, (14.0, -4.5, 5.3), (17.2, 1.8, 6.6), 40, "LINEAR")
    shots.append((382, cam, "10 ROTATIONAL LAUNCH"))
    cam, target = camera("SHOT11_FlightRecovery", (21.0, -4.65, 5.7), 40, (18.0, 1.5, 6.5))
    camera_key(cam, target, 439, (21.0, -4.65, 5.7), (18.2, 1.8, 6.5), 40)
    camera_key(cam, target, 470, (19.2, -4.6, 4.8), (18.2, 1.5, 5.1), 42)
    camera_key(cam, target, 500, (17.0, -4.55, 4.2), (15.0, 0.9, 4.4), 44)
    shots.append((439, cam, "11 FLIGHT RECOVERY"))
    cam, target = camera("SHOT12_AftermathTease", (-1.4, -1.8, 1.25), 36, (10.5, 0.8, 3.4))
    camera_key(cam, target, 501, (-1.4, -1.8, 1.25), (10.5, 0.8, 3.4), 36)
    camera_key(cam, target, 540, (-0.7, -1.45, 1.4), (9.5, 0.6, 3.25), 40)
    shots.append((501, cam, "12 NEXT EXCHANGE"))
    for frame, cam, label in shots:
        add_camera_cut(cam, frame, label)
    SCENE.camera = shots[0][1]
    return shots


def setup_lighting():
    SCENE.world.color = (0.018, 0.028, 0.055)
    world = SCENE.world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.025, 0.055, 0.12, 1)
    bg.inputs["Strength"].default_value = 0.28
    sun_data = bpy.data.lights.new("City_KeySun", type="SUN")
    sun_data.energy = 2.1
    sun_data.color = (1.0, 0.58, 0.34)
    sun = bpy.data.objects.new("City_KeySun", sun_data)
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(28), math.radians(-18), math.radians(-42))
    fill_data = bpy.data.lights.new("City_BlueFill", type="AREA")
    fill_data.energy = 850
    fill_data.color = (0.08, 0.26, 0.8)
    fill_data.shape = "DISK"
    fill_data.size = 8
    fill = bpy.data.objects.new("City_BlueFill", fill_data)
    bpy.context.collection.objects.link(fill)
    fill.location = (-4, -5, 8)
    fill.rotation_euler = (0.35, 0, 0.2)
    rim_data = bpy.data.lights.new("Hero_Rim", type="AREA")
    rim_data.energy = 1100
    rim_data.color = (1.0, 0.18, 0.06)
    rim_data.size = 6
    rim = bpy.data.objects.new("Hero_Rim", rim_data)
    bpy.context.collection.objects.link(rim)
    rim.location = (4, 4, 6)
    rim.rotation_euler = (-0.5, 0, 2.5)


def write_character_package(character_id, display_name, source_body, source_rig, features, actions, ability, vfx):
    package = OUTPUT / "characters" / character_id
    for sub in ("model", "materials", "animations", "abilities", "vfx", "audio", "metadata"):
        (package / sub).mkdir(parents=True, exist_ok=True)
    model_path = package / "model" / f"{character_id}_stylized.blend"
    animation_path = package / "animations" / f"{character_id}_actions.blend"
    # Libraries are independent, derived package assets; the live scene keeps its own copies.
    blocks = {source_rig, source_rig.data, source_body, source_body.data}
    blocks.update(features)
    for obj in features:
        if getattr(obj, "data", None):
            blocks.add(obj.data)
        for material in getattr(obj.data, "materials", ()) if getattr(obj, "data", None) else ():
            blocks.add(material)
    for material in source_body.data.materials:
        blocks.add(material)
    bpy.data.libraries.write(str(model_path), blocks, fake_user=True, compress=True)
    action_blocks = set(actions.values())
    bpy.data.libraries.write(str(animation_path), action_blocks, fake_user=True, compress=True)
    mapping = json.loads(source_rig["wws_standard_to_target"])
    adapter = {
        "schema_version": 1,
        "adapter_id": f"{character_id}.stylized.v1",
        "standard_to_target": mapping,
        "optional_bones": {}, "finger_chains": {}, "corrective_shape_keys": [],
        "source_rest_pose": "SOURCE", "target_rest_pose": "A_POSE",
        "rotation_offsets_degrees": {}, "root_object": None,
    }
    (package / "rig_adapter.json").write_text(json.dumps(adapter, indent=2), encoding="utf-8")
    mesh_names = [source_body.name]
    accessory_names = [obj.name for obj in features]
    clips = []
    for semantic, action in actions.items():
        clips.append({
            "clip_id": f"{character_id}.{semantic}", "action": semantic,
            "path": f"animations/{character_id}_actions.blend", "action_name": action.name,
            "root_motion": "replace", "mirror_supported": semantic not in {"rasengan_charge", "rasengan_attack"},
            "loop": semantic.endswith("stance"), "tags": ["character_specific", "authored_action"],
        })
    manifest = {
        "schema_version": 1, "character_id": character_id, "display_name": display_name,
        "package_version": "1.0.0-previs", "development_fixture": True,
        "allow_external_assets": False, "model_path": f"model/{character_id}_stylized.blend",
        "armature": source_rig.name, "mesh_objects": mesh_names,
        "accessory_objects": accessory_names, "scale": 1.0,
        "forward_axis": "-Y", "up_axis": "Z", "rest_pose": "A_POSE",
        "rig_adapter": "rig_adapter.json", "default_materials": [],
        "combat_style": ["agile_ninja", "chakra"] if character_id == "naruto" else ["aerial_powerhouse", "close_range_pressure"],
        "generic_animation_compatibility": ["dash", "heavy_cross", "hook", "kick", "dodge", "hit_heavy", "launch", "airborne_tumble", "hard_landing", "skid", "recovery"],
        "animation_clips": clips,
        "custom_animation_overrides": {semantic: f"{character_id}.{semantic}" for semantic in actions},
        "ability_definitions": [f"abilities/{ability['ability_id']}.json"],
        "vfx_definitions": ["vfx/vfx.json"],
        "attachment_points": [
            {"attachment_id": "right_hand", "bone_role": "hand.R", "offset": {"location": [0, 0, 0], "rotation_degrees": [0, 0, 0]}},
            {"attachment_id": "chest", "bone_role": "chest", "offset": {"location": [0.18, 0, 0], "rotation_degrees": [0, 0, 0]}},
        ],
        "metadata": {"visual_quality": "stylized_character_previs", "canonical_likeness": False, "simulation_authority": "external_event_log"},
    }
    (package / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (package / "abilities" / f"{ability['ability_id']}.json").write_text(json.dumps(ability, indent=2), encoding="utf-8")
    (package / "vfx" / "vfx.json").write_text(json.dumps(vfx, indent=2), encoding="utf-8")
    (package / "audio" / "hooks.json").write_text(json.dumps({"hooks": ability["sound_hooks"], "assets": [], "implemented": False}, indent=2), encoding="utf-8")
    (package / "materials" / "palette.json").write_text(json.dumps({"embedded_in_model": True, "style": "clean_stylized_toon_influence"}, indent=2), encoding="utf-8")
    (package / "metadata" / "README.md").write_text(
        f"# {display_name} stylized development package\n\nRecognizable combat-previs fixture. Not a likeness-accurate or publication-final asset.\n",
        encoding="utf-8",
    )
    return manifest


def write_metadata(actions, packages):
    (OUTPUT / "source").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_EVENTS, OUTPUT / "source/events.json")
    provenance = {
        "schema_version": 1, "source_event_log": "source/events.json",
        "source_sha256": sha256(SOURCE_EVENTS), "seed": 69,
        "canonical_outcome": {"winner": "naruto", "condition": "ko", "duration": 22.55, "finisher": "energy_orb"},
        "cinematic_excerpt": {"duration_seconds": 18.0, "does_not_move_ko_earlier": True},
        "beats": [
            {"shot": 1, "event_ids": ["event-000001"], "portrayal": "street faceoff"},
            {"shot": 2, "event_ids": ["event-000121", "event-000123"], "portrayal": "Omni-Man flight charge"},
            {"shot": 3, "event_ids": ["event-000055", "event-000158"], "portrayal": "Naruto narrow dodge"},
            {"shot": 4, "event_ids": ["event-000067"], "portrayal": "miss continuation and staged wall destruction"},
            {"shot": 5, "event_ids": ["event-000167"], "portrayal": "Naruto reposition and chakra activation"},
            {"shot": 6, "event_ids": ["event-000218"], "portrayal": "charged_vortex as Rasengan formation"},
            {"shot": 7, "event_ids": ["event-000203"], "portrayal": "pursuit and failed grapple"},
            {"shot": 8, "event_ids": ["event-000256", "event-000244", "event-000284"], "portrayal": "heavy strike miss, melee hit, evade"},
            {"shot": 9, "event_ids": ["event-000221", "event-000223"], "portrayal": "charged_vortex Rasengan hit and knockback"},
            {"shot": 10, "event_ids": ["event-000223"], "portrayal": "directional launch"},
            {"shot": 11, "event_ids": ["event-000237", "event-000239"], "portrayal": "Omni-Man flight recovery/power continuity"},
            {"shot": 12, "event_ids": ["event-000289"], "portrayal": "next-exchange tease; no early outcome claim"},
        ],
    }
    (OUTPUT / "source/provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    sound = {
        "fps": FPS,
        "hooks": [
            {"frame": 48, "hook": "flight_takeoff_whoosh", "character": "omniman"},
            {"frame": 69, "hook": "near_miss_whoosh", "character": "omniman"},
            {"frame": 110, "hook": "concrete_break", "character": "omniman"},
            {"frame": 190, "hook": "energy_charge", "character": "naruto"},
            {"frame": 289, "hook": "super_punch_whoosh", "character": "omniman"},
            {"frame": 365, "hook": "rasengan_contact", "character": "naruto"},
            {"frame": 374, "hook": "impact_explosion", "character": "naruto"},
            {"frame": 381, "hook": "debris", "character": None},
        ],
    }
    (OUTPUT / "review/sound-hooks.json").write_text(json.dumps(sound, indent=2), encoding="utf-8")
    plan = {
        "duration_seconds": 18.0, "fps": FPS, "aspect_ratio": "9:16",
        "characters": packages,
        "custom_actions": {who: sorted(clips) for who, clips in actions.items()},
        "source_provenance": "source/provenance.json",
        "environment": "environment/city-street.json",
    }
    (OUTPUT / "review/production-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "milestone": "first_production_fight",
        "matchup": ["naruto", "omniman"],
        "simulation_seed": 69,
        "source_event_log": "source/events.json",
        "source_event_sha256": sha256(SOURCE_EVENTS),
        "canonical_outcome": {"winner": "naruto", "condition": "ko", "finisher": "energy_orb"},
        "cinematic_excerpt_seconds": 18.0,
        "scene": "scene.blend",
        "character_packages": {
            "naruto": "characters/naruto/manifest.json",
            "omniman": "characters/omniman/manifest.json",
        },
        "environment": "environment/city-street.json",
        "preview": "renders/preview/fight.mp4",
        "quality_preview": "renders/quality-preview/fight.mp4",
        "review": "production_review.md",
        "external_paid_services_used": False,
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def render_video(path, width, height, quality=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    SCENE.render.resolution_x = width
    SCENE.render.resolution_y = height
    SCENE.render.resolution_percentage = 100
    SCENE.render.fps = FPS
    SCENE.frame_start = 1
    SCENE.frame_end = END
    if quality:
        # A high-resolution viewport render is the intentional quality-preview gate.
        # Full Eevee lighting remains available for selected look-dev frames, while
        # 540-frame animation review stays fast enough for repeated direction passes.
        SCENE.render.engine = "BLENDER_WORKBENCH"
        SCENE.display.shading.light = "STUDIO"
        SCENE.display.shading.studio_light = "rim.sl"
        SCENE.display.shading.color_type = "MATERIAL"
        SCENE.display.shading.show_shadows = True
        SCENE.display.shading.show_cavity = True
        SCENE.display.shading.cavity_type = "WORLD"
        SCENE.render.image_settings.file_format = "FFMPEG"
        SCENE.render.ffmpeg.format = "MPEG4"
        SCENE.render.ffmpeg.codec = "H264"
        SCENE.render.ffmpeg.constant_rate_factor = "MEDIUM"
        SCENE.render.film_transparent = False
    else:
        SCENE.render.engine = "BLENDER_WORKBENCH"
        SCENE.display.shading.light = "STUDIO"
        SCENE.display.shading.studio_light = "rim.sl"
        SCENE.display.shading.color_type = "MATERIAL"
        SCENE.display.shading.show_shadows = True
        SCENE.display.shading.show_cavity = True
        SCENE.display.shading.cavity_type = "WORLD"
        SCENE.render.image_settings.file_format = "FFMPEG"
        SCENE.render.ffmpeg.format = "MPEG4"
        SCENE.render.ffmpeg.codec = "H264"
        SCENE.render.ffmpeg.constant_rate_factor = "MEDIUM"
    SCENE.render.filepath = str(path)
    bpy.ops.render.render(animation=True)


def main():
    render_preview = "--render-preview" in sys.argv
    render_quality = "--render-quality" in sys.argv
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "review").mkdir(parents=True, exist_ok=True)
    (OUTPUT / "environment").mkdir(parents=True, exist_ok=True)
    clear_presentation()
    mats = assign_character_materials()
    features = create_character_features(mats)
    city = create_city()
    actions = build_character_actions()
    omni, naruto = setup_choreography(actions)
    rasengan = create_rasengan(naruto, bpy.data.objects["fighter_b_IK_hand.R"])
    create_takeoff_and_impact_vfx(city)
    create_cameras()
    setup_lighting()

    naruto_ability = {
        "ability_id": "charged_vortex", "animation": "rasengan_attack",
        "startup_vfx": ["rasengan_form"], "active_vfx": ["rasengan_swirl", "chakra_trail"],
        "impact_vfx": ["rasengan_compression", "rasengan_shockwave", "environment_reaction"],
        "projectile_object": None, "attachment_points": ["right_hand"],
        "camera_preference": ["medium_charge", "close_contact", "directional_launch"],
        "environmental_presentation": ["road_cracks", "window_reaction", "debris"],
        "sound_hooks": ["energy_charge", "rasengan_contact", "impact_explosion", "debris"],
        "authority": "presentation", "simulator_decides_outcome": True,
    }
    omni_ability = {
        "ability_id": "charge", "animation": "flight_blitz",
        "startup_vfx": ["takeoff_dust"], "active_vfx": ["speed_wake"],
        "impact_vfx": ["concrete_break", "dust_cloud"], "projectile_object": None,
        "attachment_points": ["chest", "right_hand"],
        "camera_preference": ["low_angle", "high_speed_follow", "impact_wide"],
        "environmental_presentation": ["wall_break", "debris", "broken_windows"],
        "sound_hooks": ["flight_takeoff_whoosh", "near_miss_whoosh", "concrete_break"],
        "authority": "presentation", "simulator_decides_outcome": True,
    }
    packages = {
        "naruto": write_character_package("naruto", "Naruto", bpy.data.objects["Naruto_Body"], bpy.data.objects["fighter_b_ProductionRig"], features["naruto"], actions["naruto"], naruto_ability, [
            {"vfx_id": "rasengan_form", "attachment_point": "right_hand", "duration_seconds": 2.0, "parameters": {"color": "blue", "layers": 4, "rotating": True}},
            {"vfx_id": "rasengan_swirl", "attachment_point": "right_hand", "duration_seconds": 2.0, "parameters": {"rings": 4, "rotating": True}},
            {"vfx_id": "chakra_trail", "attachment_point": "right_hand", "duration_seconds": 0.8, "parameters": {"directional": True, "restrained": True}},
            {"vfx_id": "rasengan_compression", "attachment_point": "right_hand", "duration_seconds": 0.2, "parameters": {"scale": 0.72}},
            {"vfx_id": "rasengan_shockwave", "duration_seconds": 0.5, "parameters": {"expanding": True, "contact_visible_first": True}},
            {"vfx_id": "environment_reaction", "duration_seconds": 0.8, "parameters": {"road_cracks": True, "debris": True}},
        ]),
        "omniman": write_character_package("omniman", "Omni-Man", bpy.data.objects["OmniMan_Body"], bpy.data.objects["fighter_a_ProductionRig"], features["omniman"], actions["omniman"], omni_ability, [
            {"vfx_id": "takeoff_dust", "duration_seconds": 0.7, "parameters": {"directional": True}},
            {"vfx_id": "speed_wake", "duration_seconds": 1.0, "parameters": {"subtle": True}},
            {"vfx_id": "concrete_break", "duration_seconds": 0.8, "parameters": {"staged_destruction": True}},
            {"vfx_id": "dust_cloud", "duration_seconds": 1.2, "parameters": {"restrained": True}},
        ]),
    }
    env = {
        "schema_version": 1, "environment_id": "stylized_city_street_v1", "length_m": 64,
        "road": True, "sidewalks": True, "modular_facades": 10, "background_towers": 6,
        "vehicles": 3, "streetlights": 4,
        "destruction_layers": ["wall_breach", "broken_concrete", "debris", "dust", "road_crater", "road_cracks", "vehicle_displacement"],
        "authority": "presentation_only",
    }
    (OUTPUT / "environment/city-street.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
    write_metadata(actions, packages)
    SCENE["wws_milestone"] = "first_production_fight"
    SCENE["wws_character_packages"] = json.dumps({key: f"characters/{key}/manifest.json" for key in packages}, sort_keys=True)
    SCENE["wws_source_event_sha256"] = sha256(SOURCE_EVENTS)
    SCENE["wws_source_outcome_digest"] = "fb3a7975683c9fc6dfafb0ce8ba71e241866a749be826caff70c2058794b3265"
    SCENE["wws_simulation_seed"] = 69
    SCENE["wws_canonical_winner"] = "naruto"
    SCENE["wws_cinematic_excerpt_not_final_outcome"] = True
    SCENE.frame_start = 1
    SCENE.frame_end = END
    SCENE.render.resolution_x = 360
    SCENE.render.resolution_y = 640
    SCENE.render.resolution_percentage = 100
    SCENE.render.fps = FPS
    SCENE.frame_set(1)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "scene.blend"))
    if render_preview:
        render_video(OUTPUT / "renders/preview/fight.mp4", 360, 640, quality=False)
    if render_quality:
        render_video(OUTPUT / "renders/quality-preview/fight.mp4", 720, 1280, quality=True)
    SCENE.render.resolution_x = 360
    SCENE.render.resolution_y = 640
    SCENE.render.filepath = str(OUTPUT / "renders/preview/fight.mp4")
    SCENE.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "scene.blend"))
    print(json.dumps({"output": str(OUTPUT), "frames": END, "duration": END / FPS, "preview": render_preview, "quality": render_quality, "source_sha256": sha256(SOURCE_EVENTS)}, indent=2))


if __name__ == "__main__":
    main()
