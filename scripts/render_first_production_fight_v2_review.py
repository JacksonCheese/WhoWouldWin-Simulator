"""Render deterministic spatial-integrity review stills from the V2 scene."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/first_production_fight_v2"


def main() -> None:
    report = json.loads((OUTPUT / "review/collision_report.json").read_text(encoding="utf-8"))
    frames = sorted(set(report["worst_frames"] + [289, 296, 303, 316, 332, 336, 357, 360, 362, 365, 368, 371, 375, 379]))
    proxy_mode = "--proxies" in sys.argv
    folder = OUTPUT / "review" / ("collision_frames" if proxy_mode else "motion_frames")
    folder.mkdir(parents=True, exist_ok=True)
    proxies = bpy.data.collections.get("WWS_COLLISION_PROXIES")
    if proxies:
        proxies.hide_render = not proxy_mode
        proxies.hide_viewport = not proxy_mode
    for obj in bpy.data.objects:
        if any(token in obj.name for token in ("Dust", "ImpactArc", "Shockwave", "RoadCrack", "Crater", "WallDebris")):
            obj.hide_render = True
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "rim.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.render.resolution_x = 360
    scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.camera = bpy.data.objects["V2_RasenganContactReview"]
    for frame in frames:
        scene.frame_set(frame)
        scene.render.filepath = str(folder / f"frame_{frame:04d}.png")
        bpy.ops.render.render(write_still=True)
    print(json.dumps({"frames": frames, "proxy_mode": proxy_mode, "folder": str(folder)}, indent=2))


if __name__ == "__main__":
    main()
