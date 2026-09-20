"""Render the one new aftermath shot from the TikTok slice V2 scene."""
import argparse
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/first_tiktok_production_slice_v2"

parser = argparse.ArgumentParser()
parser.add_argument("--tier", choices=("clean", "quality"), required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])

scene = bpy.context.scene
scene.camera = bpy.data.objects["TIKTOK_CAM_Aftermath"]
for marker in scene.timeline_markers:
    marker.camera = scene.camera
scene.frame_start, scene.frame_end, scene.render.fps = 99, 158, 30
scene.render.image_settings.file_format = "PNG"
scene.render.resolution_percentage = 100
scene.render.use_file_extension = True
if args.tier == "clean":
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "rim.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.render.resolution_x, scene.render.resolution_y = 360, 640
    scene.render.use_motion_blur = False
    folder = OUT / "renders/clean-frames/04_aftermath"
else:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x, scene.render.resolution_y = 720, 1280
    scene.eevee.taa_render_samples = 1
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = .24
    folder = OUT / "renders/quality-frames/04_aftermath"
folder.mkdir(parents=True, exist_ok=True)
scene.render.filepath = str(folder) + "/"
bpy.ops.render.render(animation=True)
print("FIRST_TIKTOK_SLICE_V2_RENDERED", args.tier)
