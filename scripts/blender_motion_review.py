"""Render selected Workbench frames with presentation VFX hidden.

Run with Blender after a scene path:
blender --background scene.blend --python scripts/blender_motion_review.py -- OUTPUT_DIR
"""

from pathlib import Path
import sys

import bpy


def main() -> None:
    divider = sys.argv.index("--")
    output = Path(sys.argv[divider + 1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for obj in bpy.data.objects:
        if obj.name.startswith("vfx-"):
            obj.hide_render = True

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
    for frame in (72, 87, 116, 145, 158, 162, 166, 172, 190, 220, 277, 280, 285):
        scene.frame_set(frame)
        scene.render.filepath = str(output / f"no_vfx_{frame:03d}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
