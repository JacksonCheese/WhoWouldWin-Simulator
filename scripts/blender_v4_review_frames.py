"""Render V4 static and cinematic diagnostic frames with presentation VFX hidden."""

from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/blender_combat_v4_humanoid/review/frames"
OUTPUT.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.studio_light = "rim.sl"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"

for obj in bpy.data.objects:
    if not obj.name.startswith("vfx-"):
        continue
    action = obj.animation_data.action if obj.animation_data else None
    if action:
        for curve in action.fcurves:
            if curve.data_path in {"hide_render", "hide_viewport"}:
                curve.mute = True
    obj.hide_render = True

frames = (55, 70, 82, 87, 100, 116, 145, 158, 163, 165, 172, 184, 210, 245, 271, 277, 287, 300, 311, 340)
cinematic = scene.camera
static = bpy.data.objects["V4_StaticMotionReview"]
for label, camera, width, height in (
    ("static", static, 640, 480),
    ("cinematic", cinematic, 360, 640),
):
    scene.camera = camera
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    for frame in frames:
        scene.frame_set(frame)
        scene.render.filepath = str(OUTPUT / f"{label}_{frame:03d}.png")
        bpy.ops.render.render(write_still=True)
