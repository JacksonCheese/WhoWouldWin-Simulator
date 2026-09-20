"""Render one normal-speed review angle from the hand-authored exchange."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import bpy

OUTPUT = Path(bpy.data.filepath).resolve().parent
VIEWS = ("preview", "side", "three-quarter", "front-diagonal", "top", "contact")


def args():
    tail = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--view", choices=VIEWS, required=True)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=108)
    return parser.parse_args(tail)


def main():
    opt = args()
    scene = bpy.context.scene
    label = "three-quarter" if opt.view == "preview" else opt.view
    scene.camera = bpy.data.objects["HA_CAM_" + label]
    for marker in scene.timeline_markers:
        marker.camera = scene.camera
    allowed = {"WWS_MOTION_DEBUG_BODY", "WWS_MOTION_MINIMAL_ENV", "HA_REVIEW_CAMERAS"}
    for collection in scene.collection.children:
        collection.hide_render = collection.name not in allowed
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "rim.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.render.resolution_x = 360
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.render.image_settings.file_format = "PNG"
    folder = OUTPUT / "renders" / opt.view / "frames"
    folder.mkdir(parents=True, exist_ok=True)
    scene.frame_start = opt.start
    scene.frame_end = opt.end
    scene.render.filepath = str(folder) + "/"
    (folder / "render-settings.json").write_text(json.dumps({
        "view": opt.view, "camera": scene.camera.name, "frames": [opt.start, opt.end],
        "fps": 30, "resolution": [360, 640], "renderer": "BLENDER_WORKBENCH",
    }, indent=2))
    bpy.ops.render.render(animation=True)
    print("HA_RENDER_COMPLETE", opt.view, opt.start, opt.end)


if __name__ == "__main__":
    main()
