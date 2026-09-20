"""Render one source shot from the first TikTok production slice scene."""
import argparse
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/first_tiktok_production_slice"
CAMERAS = {"01_establishment": "TIKTOK_CAM_Establishment", "02_approach": "TIKTOK_CAM_Approach", "03_hero_exchange": "TIKTOK_CAM_HeroExchange", "04_aftermath": "TIKTOK_CAM_Aftermath"}
p = argparse.ArgumentParser()
p.add_argument("--shot", choices=CAMERAS, required=True)
p.add_argument("--start", type=int, required=True)
p.add_argument("--end", type=int, required=True)
p.add_argument("--tier", choices=("clean", "preview", "quality"), required=True)
a = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
s = bpy.context.scene
s.camera = bpy.data.objects[CAMERAS[a.shot]]
for marker in s.timeline_markers:
    marker.camera = s.camera
s.frame_start, s.frame_end, s.render.fps = a.start, a.end, 30
s.render.image_settings.file_format = "PNG"
s.render.resolution_percentage = 100
s.render.use_file_extension = True
if a.tier in ("clean", "preview"):
    s.render.engine = "BLENDER_WORKBENCH"
    s.display.shading.light = "STUDIO"
    s.display.shading.studio_light = "rim.sl"
    s.display.shading.color_type = "MATERIAL"
    s.display.shading.show_shadows = True
    s.display.shading.show_cavity = True
    s.render.resolution_x, s.render.resolution_y = 360, 640
    s.render.use_motion_blur = False
else:
    s.render.engine = "BLENDER_EEVEE_NEXT"
    s.render.resolution_x, s.render.resolution_y = 720, 1280
    # One sample keeps this review render practical; the final target remains a
    # quality-preview gate rather than a publication master.
    s.eevee.taa_render_samples = 1
    s.render.use_motion_blur = True
    s.render.motion_blur_shutter = .24
folder = OUT / "renders" / ("quality-frames" if a.tier == "quality" else "clean-frames") / a.shot
folder.mkdir(parents=True, exist_ok=True)
s.render.filepath = str(folder) + "/"
bpy.ops.render.render(animation=True)
print("FIRST_TIKTOK_SLICE_RENDERED", a.tier, a.shot, a.start, a.end)
