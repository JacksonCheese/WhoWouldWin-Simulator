"""Render review outputs from the already-certified V2 scene without rebuilding it."""

from __future__ import annotations

from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/first_production_fight_v2"
SCENE = bpy.context.scene


def set_vfx_hidden(hidden):
    states = []
    tokens = ("Dust", "ImpactArc", "Shockwave", "RoadCrack", "Crater", "WallDebris")
    for obj in bpy.data.objects:
        if any(token in obj.name for token in tokens):
            states.append((obj, obj.hide_render))
            obj.hide_render = hidden
    return states


def restore(states):
    for obj, hidden in states:
        obj.hide_render = hidden


def render(path, width, height, start=1, end=540, camera=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    SCENE.frame_start, SCENE.frame_end = start, end
    SCENE.render.resolution_x, SCENE.render.resolution_y = width, height
    SCENE.render.resolution_percentage = 100
    SCENE.render.fps = 30
    SCENE.render.engine = "BLENDER_WORKBENCH"
    SCENE.display.shading.light = "STUDIO"
    SCENE.display.shading.studio_light = "rim.sl"
    SCENE.display.shading.color_type = "MATERIAL"
    SCENE.display.shading.show_shadows = True
    SCENE.display.shading.show_cavity = True
    if camera:
        SCENE.camera = camera
    SCENE.render.image_settings.file_format = "FFMPEG"
    SCENE.render.ffmpeg.format = "MPEG4"
    SCENE.render.ffmpeg.codec = "H264"
    SCENE.render.ffmpeg.constant_rate_factor = "MEDIUM"
    SCENE.render.filepath = str(path)
    bpy.ops.render.render(animation=True)


proxies = bpy.data.collections["WWS_COLLISION_PROXIES"]
if "--clean" in sys.argv:
    proxies.hide_render = True
    state = set_vfx_hidden(True)
    render(OUTPUT / "renders/clean-motion/fight.mp4", 360, 640)
    restore(state)
if "--debug" in sys.argv:
    proxies.hide_render = False
    state = set_vfx_hidden(True)
    render(OUTPUT / "renders/collision-debug/fight.mp4", 360, 640)
    restore(state)
if "--contact" in sys.argv:
    proxies.hide_render = True
    state = set_vfx_hidden(True)
    markers = [(marker.name, marker.frame, marker.camera) for marker in SCENE.timeline_markers]
    for marker in list(SCENE.timeline_markers):
        SCENE.timeline_markers.remove(marker)
    render(OUTPUT / "review/rasengan-contact.mp4", 540, 720, 270, 405, bpy.data.objects["V2_RasenganContactReview"])
    for name, frame, camera in markers:
        marker = SCENE.timeline_markers.new(name, frame=frame)
        marker.camera = camera
    restore(state)

SCENE.frame_start, SCENE.frame_end = 1, 540
SCENE.frame_set(1)
print("Rendered existing certified scene; .blend was not modified or saved.")
