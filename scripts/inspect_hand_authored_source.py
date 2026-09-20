"""Print the small subset of Blender state needed for hand-authored blocking."""
from __future__ import annotations

import json
from pathlib import Path

import bpy


def rig_info(name: str) -> dict:
    rig = bpy.data.objects[name]
    bones = {}
    for bone in rig.pose.bones:
        bones[bone.name] = {
            "head": [round(v, 4) for v in bone.head],
            "tail": [round(v, 4) for v in bone.tail],
            "parent": bone.parent.name if bone.parent else None,
            "constraints": [
                {
                    "name": c.name,
                    "type": c.type,
                    "target": getattr(getattr(c, "target", None), "name", None),
                    "subtarget": getattr(c, "subtarget", ""),
                    "influence": round(float(c.influence), 4),
                }
                for c in bone.constraints
            ],
        }
    animation = rig.animation_data
    return {
        "name": name,
        "location": [round(v, 4) for v in rig.location],
        "rotation": [round(v, 4) for v in rig.rotation_euler],
        "parent": rig.parent.name if rig.parent else None,
        "action": animation.action.name if animation and animation.action else None,
        "nla": [
            {
                "name": track.name,
                "mute": track.mute,
                "strips": [s.action.name for s in track.strips],
            }
            for track in (animation.nla_tracks if animation else [])
        ],
        "bones": bones,
    }


payload = {
    "scene": str(Path(bpy.data.filepath)),
    "fps": bpy.context.scene.render.fps,
    "unit_scale": bpy.context.scene.unit_settings.scale_length,
    "rigs": {
        name: rig_info(name)
        for name in (
            "fighter_a_Rig",
            "fighter_b_Rig",
            "fighter_a_ProductionRig",
            "fighter_b_ProductionRig",
        )
    },
}
payload["object_samples"] = {}
for frame in (1, 16, 38, 56, 85, 93, 120):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    payload["object_samples"][str(frame)] = {
        name: {
            "location": [round(v, 4) for v in bpy.data.objects[name].location],
            "world": [round(v, 4) for v in bpy.data.objects[name].matrix_world.translation],
        }
        for name in (
            "fighter_a_Rig",
            "fighter_b_Rig",
            "fighter_a_ProductionRig",
            "fighter_b_ProductionRig",
        )
    }
print("WWS_RIG_INSPECTION=" + json.dumps(payload))
