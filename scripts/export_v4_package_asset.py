"""Extract one clean model-only package asset from the existing V4 scene."""

from __future__ import annotations

from pathlib import Path
import sys

import bpy


def main() -> None:
    divider = sys.argv.index("--")
    fighter = sys.argv[divider + 1]
    output = Path(sys.argv[divider + 2]).resolve()
    source_rig = bpy.data.objects[f"{fighter}_ProductionRig"]
    source_body = bpy.data.objects[f"{fighter}_ProductionBody"]

    rig = source_rig.copy()
    rig.data = source_rig.data.copy()
    rig.name = "WWS_EvaluationRig"
    rig.animation_data_clear()
    rig.constraints.clear()
    for bone in rig.pose.bones:
        for constraint in list(bone.constraints):
            bone.constraints.remove(constraint)
    bpy.context.collection.objects.link(rig)

    body = source_body.copy()
    body.data = source_body.data.copy()
    body.name = "WWS_EvaluationBody"
    body.animation_data_clear()
    body.parent = rig
    for modifier in body.modifiers:
        if modifier.type == "ARMATURE":
            modifier.object = rig
    body.hide_viewport = False
    body.hide_render = False
    rig.hide_viewport = False
    rig.hide_render = False
    bpy.context.collection.objects.link(body)

    keep = {rig, body}
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    print(f"Extracted {fighter} package asset: {output}")


if __name__ == "__main__":
    main()
