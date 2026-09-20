"""Build the single-shot aftermath revision of the locked TikTok slice."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import bpy

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/first_tiktok_production_slice"
OUT = ROOT / "outputs/first_tiktok_production_slice_v2"
EXPECTED = "4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861"
PROTECTED = ("HA_ROOT_fighter_a", "HA_ROOT_fighter_b", "HA_BODY_OMNI", "HA_BODY_NARUTO")
START, END = 99, 158


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def action_signature(action) -> str:
    payload = [
        (curve.data_path, curve.array_index,
         [(round(key.co.x, 6), round(key.co.y, 8), key.interpolation)
          for key in curve.keyframe_points])
        for curve in sorted(action.fcurves, key=lambda item: (item.data_path, item.array_index))
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def insert_curve(action, path: str, index: int, keys: list[tuple[int, float]]) -> None:
    curve = action.fcurves.find(path, index=index) or action.fcurves.new(path, index=index)
    for frame, value in keys:
        point = curve.keyframe_points.insert(frame, value, options={"FAST"})
        point.interpolation = "BEZIER"
        point.handle_left_type = point.handle_right_type = "AUTO_CLAMPED"
    curve.update()


def add_rotation(action, bone: str, poses: list[tuple[int, tuple[float, float, float]]]) -> None:
    path = f'pose.bones["{bone}"].rotation_euler'
    for axis in range(3):
        insert_curve(action, path, axis, [(frame, rotation[axis]) for frame, rotation in poses])


def build_aftermath_action() -> tuple[str, str]:
    """Author a restrained, additive whole-body settle after the approved recoil."""
    rig = bpy.data.objects["fighter_a_ProductionRig"]
    action = bpy.data.actions.new("TIKTOK_V2_OMNI_AFTERMATH_BODY")
    action["wws_source"] = "shot-specific hand-authored aftermath reaction"
    action["wws_scope"] = "frames 99-158; approved recovery tail then additive body settle; no new root translation"

    zero = (0.0, 0.0, 0.0)
    # A compressed recoil resolves pelvis-first, with delayed ribcage and
    # asymmetric arm drag. Values are small additive rotations in radians.
    add_rotation(action, "Hips", [(108, zero), (114, (.070, -.018, .025)),
                                   (124, (.035, -.010, .018)), (140, (-.020, .008, -.010)),
                                   (150, (.008, 0, .004)), (158, zero)])
    add_rotation(action, "SpineLower", [(108, zero), (116, zero), (122, (.055, -.012, .018)),
                                         (132, (.028, -.008, .010)), (146, (-.018, .006, -.008)),
                                         (152, (.006, 0, .003)), (158, zero)])
    add_rotation(action, "SpineUpper", [(108, zero), (118, zero), (126, (.072, -.018, .026)),
                                         (136, (.032, -.010, .012)), (150, (-.022, .008, -.010)),
                                         (154, (.006, 0, .003)), (158, zero)])
    add_rotation(action, "Head", [(108, zero), (120, (-.025, .012, -.020)),
                                   (132, (.035, -.010, .022)), (148, (-.012, .005, -.008)),
                                   (158, zero)])
    add_rotation(action, "Shoulder_L", [(108, zero), (118, (.018, .015, .035)),
                                         (128, (.042, .030, .060)), (144, (.012, .010, .025)),
                                         (152, (-.008, 0, -.008)), (158, zero)])
    add_rotation(action, "UpperArm_L", [(108, zero), (120, (.065, .025, .075)),
                                         (132, (.125, .045, .115)), (146, (.040, .015, .045)),
                                         (152, (-.015, 0, -.010)), (158, zero)])
    add_rotation(action, "LowerArm_L", [(108, zero), (122, (-.030, .025, -.020)),
                                         (136, (-.085, .055, -.045)), (150, (-.025, .018, -.012)),
                                         (158, zero)])
    add_rotation(action, "Hand_L", [(108, zero), (124, (.015, .030, -.045)),
                                     (140, (.030, .050, -.075)), (154, (.010, .015, -.020)),
                                     (158, zero)])
    add_rotation(action, "Shoulder_R", [(108, zero), (116, (-.012, -.010, -.025)),
                                         (124, (-.030, -.020, -.050)), (138, (-.010, -.008, -.022)),
                                         (150, (.006, 0, .008)), (158, zero)])
    add_rotation(action, "UpperArm_R", [(108, zero), (118, (-.050, -.020, -.055)),
                                         (128, (-.105, -.035, -.095)), (142, (-.035, -.012, -.035)),
                                         (152, (.012, 0, .010)), (158, zero)])
    add_rotation(action, "LowerArm_R", [(108, zero), (120, (.025, -.018, .015)),
                                         (132, (.070, -.040, .035)), (148, (.020, -.010, .010)),
                                         (158, zero)])
    # Legs trail the torso in controlled flight, then return to a readable,
    # balanced hover. No contact solver or world-space root motion is used.
    add_rotation(action, "UpperLeg_L", [(108, zero), (120, (-.030, .012, -.012)),
                                         (134, (-.060, .020, -.020)), (150, (-.018, .006, -.006)),
                                         (158, zero)])
    add_rotation(action, "LowerLeg_L", [(108, zero), (122, (.025, 0, 0)),
                                         (138, (.055, 0, 0)), (150, (.015, 0, 0)), (158, zero)])
    add_rotation(action, "UpperLeg_R", [(108, zero), (118, (.022, -.010, .010)),
                                         (130, (.050, -.018, .018)), (146, (.015, -.006, .006)),
                                         (158, zero)])
    add_rotation(action, "LowerLeg_R", [(108, zero), (120, (-.018, 0, 0)),
                                         (134, (-.040, 0, 0)), (148, (-.012, 0, 0)), (158, zero)])

    rig.animation_data_create()
    track = rig.animation_data.nla_tracks.new()
    track.name = "TIKTOK_V2_AUTHORED_AFTERMATH"
    strip = track.strips.new(action.name, START, action)
    strip.frame_start, strip.frame_end = START, END
    strip.action_frame_start, strip.action_frame_end = START, END
    strip.blend_type = "ADD"
    strip.extrapolation = "NOTHING"
    if action.slots:
        strip.action_slot = action.slots[0]
    return action.name, action_signature(action)


def extend_cape() -> tuple[str, str]:
    cape = bpy.data.objects["OmniMan_Cape"]
    source = cape.animation_data.action
    action = source.copy()
    action.name = "TIKTOK_V2_OMNI_CAPE_AFTERMATH"
    cape.animation_data.action = action
    poses = (
        (108, (0.0, -.04, 0.0), (1.0, 1.0, 1.0)),
        (116, (.035, .10, .10), (1.0, .92, 1.06)),
        (128, (.070, .24, .16), (1.0, .86, 1.10)),
        (142, (.030, .08, .06), (1.0, .94, 1.05)),
        (150, (-.012, -.07, -.025), (1.0, 1.02, .99)),
        (158, (0.0, -.03, 0.0), (1.0, 1.0, 1.0)),
    )
    for frame, rotation, scale in poses:
        cape.rotation_euler = rotation
        cape.scale = scale
        cape.keyframe_insert("rotation_euler", frame=frame)
        cape.keyframe_insert("scale", frame=frame)
    for curve in action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = "BEZIER"
            key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"
    action["wws_source"] = "authored secondary cape follow-through for aftermath shot"
    return action.name, action_signature(action)


def main() -> None:
    if sha(SOURCE / "source/events.json") != EXPECTED:
        raise RuntimeError("Canonical event log does not match the approved baseline")
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE / "scene.blend"))
    for folder in ("source", "review", "renders/clean-frames/04_aftermath",
                   "renders/quality-frames/04_aftermath", "renders/clean",
                   "renders/quality-preview"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / "source/events.json", OUT / "source/events.json")
    shutil.copy2(SOURCE / "shot_manifest.json", OUT / "source/locked-parent-shot-manifest.json")
    shutil.copy2(SOURCE / "review/provenance-report.json", OUT / "source/locked-parent-provenance.json")

    before = {name: action_signature(bpy.data.actions[name]) for name in PROTECTED}
    aftermath_action, aftermath_signature = build_aftermath_action()
    cape_action, cape_signature = extend_cape()
    after = {name: action_signature(bpy.data.actions[name]) for name in PROTECTED}
    if before != after:
        raise RuntimeError("Protected body/root Actions changed during aftermath authoring")

    scene = bpy.context.scene
    scene.frame_start, scene.frame_end, scene.render.fps = 1, END, 30
    scene.camera = bpy.data.objects["TIKTOK_CAM_Aftermath"]
    scene["wws_canonical_events_sha256"] = EXPECTED
    scene["wws_tiktok_v2_parent_sha256"] = sha(SOURCE / "scene.blend")
    scene["wws_approved_hero_exchange_unchanged"] = True
    scene["wws_body_root_actions_separate"] = True
    scene["wws_contact_hold"] = "82-84"
    scene["wws_new_authored_shots"] = 1
    scene["wws_aftermath_root_motion"] = "none; controlled hover with additive body settle"
    scene.frame_set(108)
    bpy.context.view_layer.update()
    scene_path = OUT / "scene.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))

    parent = json.loads((SOURCE / "shot_manifest.json").read_text())
    shots = json.loads(json.dumps(parent["shots"]))
    shots[3] = {
        "shot_id": "04_aftermath_reaction",
        "source_frames": [99, 158],
        "duration_seconds": 2.0,
        "camera": "TIKTOK_CAM_Aftermath",
        "source": "approved recoil endpoint plus shot-specific authored additive recovery",
        "characters": ["naruto", "omniman"],
        "vfx": ["Rasengan dissipated"],
        "status": "PROVISIONAL",
        "limitations": ["controlled flight recovery; simplified cape and hand controls"],
        "new_animation_action": aftermath_action,
        "root_motion": "none",
    }
    manifest = {
        "schema_version": 2,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "aspect_ratio": "9:16",
        "fps": 30,
        "target_duration_seconds": 8.5,
        "canonical_events_sha256": EXPECTED,
        "parent_scene": str(SOURCE / "scene.blend"),
        "parent_scene_sha256": sha(SOURCE / "scene.blend"),
        "parent_shot_manifest_sha256": sha(SOURCE / "shot_manifest.json"),
        "scene": str(scene_path),
        "scene_sha256": sha(scene_path),
        "protected_action_signatures": before,
        "protected_actions_unchanged": before == after,
        "contact_hold_frames": [82, 84],
        "new_authored_shot_count": 1,
        "new_actions": {
            aftermath_action: aftermath_signature,
            cape_action: cape_signature,
        },
        "shots": shots,
        "locked": False,
        "whole_project_production_ready": False,
    }
    (OUT / "shot_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (OUT / "review/build-provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("FIRST_TIKTOK_SLICE_V2_BUILT", manifest["scene_sha256"])


if __name__ == "__main__":
    main()
