"""Minimal Blender renderer smoke test used by the V2 certification workflow."""

from pathlib import Path

import bpy


OUTPUT = Path("/tmp/wws_blender_runtime_smoke")
OUTPUT.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
bpy.ops.object.camera_add(location=(4, -4, 3))
camera = bpy.context.object
bpy.context.scene.camera = camera
camera.rotation_euler = (1.1, 0, 0.78)
bpy.ops.object.light_add(type="AREA", location=(2, -2, 4))
bpy.context.object.data.energy = 900

scene = bpy.context.scene
scene.render.resolution_x = 64
scene.render.resolution_y = 64
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"

for engine, name in (("BLENDER_WORKBENCH", "workbench"), ("BLENDER_EEVEE_NEXT", "eevee")):
    scene.render.engine = engine
    scene.render.filepath = str(OUTPUT / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"WWS_RENDER_OK {engine} {scene.render.filepath}")
