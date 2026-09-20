"""Render one normal-speed review angle from the saved hero exchange."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(bpy.data.filepath).resolve().parent
VIEWS = ("preview", "side", "three-quarter", "front-diagonal", "top")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arguments():
    tail = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--view", choices=VIEWS, required=True)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=120)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(tail)


def set_visibility(top=False):
    allowed = {"WWS_MOTION_DEBUG_BODY", "WWS_MOTION_MINIMAL_ENV", "HERO_REVIEW_CAMERAS", "HERO_CONTACT_CONTROLS", "HERO_FOOT_PINS"}
    for collection in bpy.context.scene.collection.children:
        collection.hide_render = collection.name not in allowed
    for name in ("HERO_CONTACT_CONTROLS", "HERO_FOOT_PINS"):
        collection = bpy.data.collections.get(name)
        if collection:
            collection.hide_render = True
    overlays = bpy.data.collections.get("WWS_MOTION_OVERLAYS")
    if overlays:
        overlays.hide_render = True
    bpy.context.view_layer.update()


def main():
    args = arguments()
    scene = bpy.context.scene
    label = "three-quarter" if args.view == "preview" else args.view
    camera = bpy.data.objects["HERO_CAM_" + label]
    scene.camera = camera
    for marker in scene.timeline_markers:
        marker.camera = camera
    set_visibility(top=args.view == "top")
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "rim.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.render.resolution_x = 360
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.render.image_settings.file_format = "PNG"
    folder = OUTPUT / "renders" / args.view / "frames"
    folder.mkdir(parents=True, exist_ok=True)
    provenance = {
        "scene_sha256": digest(Path(bpy.data.filepath)),
        "renderer_sha256": digest(Path(__file__)),
        "view": args.view,
        "camera": camera.name,
        "resolution": [360, 640],
        "fps": 30,
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    record = folder / "render-provenance.json"
    record.write_text(json.dumps(provenance, indent=2))
    pending = [frame for frame in range(args.start, args.end + 1) if args.force or not (folder / f"{frame:04d}.png").exists()]
    if pending:
        scene.frame_start = pending[0]
        scene.frame_end = pending[-1]
        scene.render.filepath = str(folder) + "/"
        bpy.ops.render.render(animation=True)
    print("HERO_RENDER_COMPLETE", args.view, args.start, args.end)


if __name__ == "__main__":
    main()
