"""Render deterministic review frames for the first production fight."""

from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/first_production_fight/review/frames"
OUT.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.studio_light = "rim.sl"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.render.resolution_x = 360
scene.render.resolution_y = 640
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
for frame in (1, 55, 70, 110, 150, 200, 270, 300, 365, 380, 420, 465, 520):
    scene.frame_set(frame)
    bound = [marker for marker in scene.timeline_markers if marker.frame <= frame and marker.camera]
    if bound:
        scene.camera = max(bound, key=lambda marker: marker.frame).camera
    scene.render.filepath = str(OUT / f"frame-{frame:03d}.png")
    bpy.ops.render.render(write_still=True)
print(f"Rendered {len(list(OUT.glob('*.png')))} review frames to {OUT}")
