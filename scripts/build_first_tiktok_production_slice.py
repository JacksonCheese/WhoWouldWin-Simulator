"""Build an editorial derivative around the approved production-skin hero exchange."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/combat_motion_lab_production_skin_sole_binding"
OUT = ROOT / "outputs/first_tiktok_production_slice"
EXPECTED = "4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861"
PROTECTED = ("HA_ROOT_fighter_a", "HA_ROOT_fighter_b", "HA_BODY_OMNI", "HA_BODY_NARUTO")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def action_signature(action) -> str:
    payload = [(c.data_path, c.array_index, [(round(k.co.x, 6), round(k.co.y, 8), k.interpolation) for k in c.keyframe_points]) for c in sorted(action.fcurves, key=lambda c: (c.data_path, c.array_index))]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def material(name, color, roughness=.6, emission=None, strength=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        (bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")).default_value = (*emission, 1)
        if bsdf.inputs.get("Emission Strength"):
            bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def cube(name, location, scale, mat, bevel=.04):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("TikTok slice bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return obj


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def camera(name, location, target, lens):
    data = bpy.data.cameras.new(name + "_Data")
    data.lens = lens
    data.sensor_fit = "VERTICAL"
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    look_at(obj, target)
    return obj


def build_minimal_street():
    for name in ("SKINTEST_BackWall", "SKINTEST_HorizonTrim"):
        obj = bpy.data.objects.get(name)
        if obj:
            obj.hide_render = True
            obj.hide_viewport = True
    road = material("TIKTOK_Road", (.035, .045, .06), .82)
    curb = material("TIKTOK_Curb", (.22, .24, .27), .72)
    wall = material("TIKTOK_Facade", (.12, .16, .22), .62)
    glass = material("TIKTOK_Window", (.035, .12, .22), .24, (.02, .08, .17), .25)
    stripe = material("TIKTOK_Stripe", (.62, .52, .18), .58)
    objects = [cube("TIKTOK_Road", (0, 0, -.09), (7.5, 7.0, .08), road, .02)]
    for side in (-1, 1):
        objects.append(cube(f"TIKTOK_Sidewalk_{side}", (side * 5.4, 0, .02), (1.4, 7.0, .12), curb))
        objects.append(cube(f"TIKTOK_Facade_{side}", (side * 6.45, 1.8, 2.5), (.65, 5.1, 2.45), wall))
        for row in range(2):
            for col in range(3):
                objects.append(cube(f"TIKTOK_Window_{side}_{row}_{col}", (side * 5.78, -1.8 + col * 2.0, 1.45 + row * 1.75), (.025, .54, .48), glass, .015))
    for y in (-4.2, 0.0, 4.2):
        objects.append(cube(f"TIKTOK_Lane_{y}", (0, y, .005), (.07, .72, .012), stripe, .01))
    for obj in objects:
        obj["wws_minimal_tiktok_environment"] = True
    return [o.name for o in objects]


def build_cameras():
    cams = {
        "establishment": camera("TIKTOK_CAM_Establishment", (-2.0, -12.0, 2.15), (0.0, .05, 1.34), 34),
        "approach": camera("TIKTOK_CAM_Approach", (2.0, -11.2, 2.65), (0.0, .12, 1.46), 40),
        "hero": camera("TIKTOK_CAM_HeroExchange", (5.7, -7.8, 2.85), (.35, .48, 1.55), 55),
        "aftermath": camera("TIKTOK_CAM_Aftermath", (5.0, -9.3, 3.15), (-.25, .25, 1.48), 43),
    }
    hero = cams["hero"]
    for frame, loc, target in ((24, (5.5, -8.2, 2.8), (0, .15, 1.5)), (68, (5.8, -7.8, 2.9), (.35, .48, 1.58)), (84, (5.3, -7.2, 2.75), (.42, .56, 1.63)), (98, (5.1, -8.6, 3.1), (-.15, .28, 1.5))):
        hero.location = loc
        look_at(hero, target)
        hero.keyframe_insert("location", frame=frame)
        hero.keyframe_insert("rotation_euler", frame=frame)
    if hero.animation_data:
        for curve in hero.animation_data.action.fcurves:
            for key in curve.keyframe_points:
                key.interpolation = "BEZIER"
                key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"
    return {k: v.name for k, v in cams.items()}


def main():
    if sha(SOURCE / "source/events.json") != EXPECTED:
        raise RuntimeError("Canonical event log does not match the approved baseline")
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE / "scene.blend"))
    for folder in ("source", "review", "renders/preview", "renders/quality-preview", "renders/final", "renders/clean", "renders/frames"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / "source/events.json", OUT / "source/events.json")
    shutil.copy2(SOURCE / "review/provenance-report.json", OUT / "source/approved-parent-provenance.json")
    before = {name: action_signature(bpy.data.actions[name]) for name in PROTECTED}
    environment = build_minimal_street()
    cameras = build_cameras()
    after = {name: action_signature(bpy.data.actions[name]) for name in PROTECTED}
    if before != after:
        raise RuntimeError("Protected body/root Actions changed during presentation build")
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end, scene.render.fps = 1, 108, 30
    scene.render.resolution_x, scene.render.resolution_y = 720, 1280
    scene.render.resolution_percentage = 100
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.camera = bpy.data.objects[cameras["establishment"]]
    scene["wws_canonical_events_sha256"] = EXPECTED
    scene["wws_tiktok_slice_parent_sha256"] = sha(SOURCE / "scene.blend")
    scene["wws_approved_hero_exchange_unchanged"] = True
    scene["wws_body_root_actions_separate"] = True
    scene["wws_contact_hold"] = "82-84"
    scene.frame_set(1)
    bpy.context.view_layer.update()
    scene_path = OUT / "scene.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))
    shots = [
        {"shot_id": "01_establishment", "source_frames": [1, 1], "duration_seconds": 2.0, "camera": cameras["establishment"], "source": "approved sole-binding scene / held confrontation pose", "characters": ["naruto", "omniman"], "vfx": [], "status": "PROVISIONAL", "limitations": ["held pose; no new body animation"]},
        {"shot_id": "02_approach", "source_frames": [1, 22], "duration_seconds": 1.3, "camera": cameras["approach"], "source": "approved hero exchange attack/slip range", "characters": ["naruto", "omniman"], "vfx": [], "status": "PROVISIONAL", "limitations": ["existing transition only; no new close-contact motion"]},
        {"shot_id": "03_hero_exchange", "source_frames": [24, 98], "duration_seconds": 3.2, "camera": cameras["hero"], "source": "approved production-skin hero exchange and sole correction", "characters": ["naruto", "omniman"], "vfx": ["restrained Rasengan core/rings/light"], "status": "APPROVED_SOURCE", "limitations": ["simplified hands and limited scapular/twist deformation"]},
        {"shot_id": "04_aftermath", "source_frames": [99, 108], "duration_seconds": 2.0, "camera": cameras["aftermath"], "source": "approved recovery tail with editorial end hold", "characters": ["naruto", "omniman"], "vfx": ["Rasengan dissipated"], "status": "PROVISIONAL", "limitations": ["short recovery range; endpoint held editorially"]},
    ]
    manifest = {"schema_version": 1, "generated_utc": datetime.now(timezone.utc).isoformat(), "aspect_ratio": "9:16", "fps": 30, "target_duration_seconds": 8.5, "canonical_events_sha256": EXPECTED, "parent_scene": str(SOURCE / "scene.blend"), "parent_scene_sha256": sha(SOURCE / "scene.blend"), "scene": str(scene_path), "scene_sha256": sha(scene_path), "protected_action_signatures": before, "protected_actions_unchanged": before == after, "contact_hold_frames": [82, 84], "environment_objects": environment, "shots": shots, "whole_project_production_ready": False}
    (OUT / "shot_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (OUT / "review/build-provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("FIRST_TIKTOK_SLICE_BUILT", manifest["scene_sha256"])


if __name__ == "__main__":
    main()
