"""Render one source-frame range from the production-skin feasibility scene."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/combat_motion_lab_production_skin_feasibility"
CAMERAS = {
    "shot1": "SKINTEST_CAM_AttackSlip",
    "shot2": "SKINTEST_CAM_RasenganEntry",
    "shot3": "SKINTEST_CAM_Recoil",
    "contact": "SKINTEST_CAM_ContactCloseup",
}


def args():
    tail = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--shot", choices=CAMERAS, required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--tier", choices=("clean", "quality", "contact"), required=True)
    return parser.parse_args(tail)


def main():
    options = args()
    scene = bpy.context.scene
    scene.camera = bpy.data.objects[CAMERAS[options.shot]]
    for marker in scene.timeline_markers:
        marker.camera = scene.camera
    scene.frame_start = options.start
    scene.frame_end = options.end
    scene.render.fps = 30
    scene.render.image_settings.file_format = "PNG"
    if options.tier == "clean":
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.display.shading.light = "STUDIO"
        scene.display.shading.studio_light = "rim.sl"
        scene.display.shading.color_type = "MATERIAL"
        scene.display.shading.show_shadows = True
        scene.display.shading.show_cavity = True
        scene.render.resolution_x, scene.render.resolution_y = 360, 640
        scene.render.use_motion_blur = False
    else:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.render.resolution_x, scene.render.resolution_y = (720, 1280) if options.tier == "quality" else (360, 640)
        scene.eevee.taa_render_samples = 8
        scene.render.use_motion_blur = options.tier == "quality"
        scene.render.motion_blur_shutter = 0.28
    scene.render.resolution_percentage = 100
    folder = OUTPUT / "renders" / ({"clean": "preview", "quality": "quality-preview", "contact": "contact-closeup"}[options.tier]) / options.shot
    folder.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(folder) + "/"
    bpy.ops.render.render(animation=True)
    print("PRODUCTION_SKIN_RENDER_COMPLETE", options.tier, options.shot, options.start, options.end)


if __name__ == "__main__":
    main()
