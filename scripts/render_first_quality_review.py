"""Render a few Eevee look-development frames without the full quality pass."""

from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/first_production_fight/review/quality-frames"
OUT.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.render.resolution_x = 360
scene.render.resolution_y = 640
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
for frame in (1, 70, 110, 200, 365, 380, 420, 465, 520):
    scene.frame_set(frame)
    bound = [marker for marker in scene.timeline_markers if marker.frame <= frame and marker.camera]
    if bound:
        scene.camera = max(bound, key=lambda marker: marker.frame).camera
    scene.render.filepath = str(OUT / f"frame-{frame:03d}.png")
    bpy.ops.render.render(write_still=True)
print(f"Rendered Eevee review frames to {OUT}")
