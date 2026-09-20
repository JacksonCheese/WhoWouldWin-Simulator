"""Render one Combat Motion Lab view from the saved derived scene."""
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
import bpy

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs/combat_motion_lab"


def parse_args():
    tail=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    parser=argparse.ArgumentParser()
    parser.add_argument("--view",choices=["side","three-quarter","front-diagonal","top-debug","cinematic-test"],required=True)
    parser.add_argument("--start",type=int,default=1);parser.add_argument("--end",type=int,default=540)
    parser.add_argument("--visualization",choices=["motion_debug","character_preview","production"],default="motion_debug")
    parser.add_argument("--force",action="store_true")
    return parser.parse_args(tail)


def set_mode(mode, top_debug=False):
    scene=bpy.context.scene
    states=json.loads(scene["wws_motion_lab_original_states"])
    debug=bpy.data.collections["WWS_MOTION_DEBUG_BODY"]
    minimal=bpy.data.collections["WWS_MOTION_MINIMAL_ENV"]
    overlay=bpy.data.collections["WWS_MOTION_OVERLAYS"]
    source_layer=bpy.context.view_layer.layer_collection.children.get("WWS_MOTION_SOURCE_RENDERABLES")
    for name,original_hidden in states.items():
        obj=bpy.data.objects.get(name)
        if obj:obj.hide_render=True
    if mode=="production":
        if source_layer:source_layer.exclude=False
        for collection in scene.collection.children:collection.hide_render=False
        for name,original_hidden in states.items():
            obj=bpy.data.objects.get(name)
            if obj:obj.hide_render=original_hidden
        debug.hide_render=True;minimal.hide_render=True;overlay.hide_render=True
    elif mode=="character_preview":
        if source_layer:source_layer.exclude=False
        for collection in scene.collection.children:collection.hide_render=False
        for name,original_hidden in states.items():
            obj=bpy.data.objects.get(name)
            if obj and name.startswith(("Naruto","OmniMan")):obj.hide_render=original_hidden
        debug.hide_render=True;minimal.hide_render=False;overlay.hide_render=True
    else:
        if source_layer:source_layer.exclude=True
        # Source debris and destruction use animated hide_render keys. Hiding
        # the source collections is the reliable way to keep motion-debug clean.
        allowed={"WWS_MOTION_DEBUG_BODY","WWS_MOTION_MINIMAL_ENV","WWS_MOTION_OVERLAYS","WWS_MOTION_CAMERAS"}
        for collection in scene.collection.children:
            collection.hide_render=collection.name not in allowed
        debug.hide_render=False;minimal.hide_render=False;overlay.hide_render=not top_debug
    bpy.context.view_layer.update()
    scene["wws_visualization_mode"]=mode


def main():
    args=parse_args();scene=bpy.context.scene
    set_mode(args.visualization,args.view=="top-debug")
    if args.view!="cinematic-test":
        static_camera=bpy.data.objects["ML_CAM_"+args.view]
        scene.camera=static_camera
        # Camera markers are a cinematic edit feature; static reviews ignore them.
        # Assigning None lets Blender reactivate the preceding shot camera while
        # stepping frames. Point every marker at the review camera instead.
        for marker in scene.timeline_markers:marker.camera=static_camera
    scene.render.engine="BLENDER_WORKBENCH"
    scene.display.shading.light="STUDIO";scene.display.shading.studio_light="rim.sl"
    scene.display.shading.color_type="MATERIAL";scene.display.shading.show_shadows=True
    scene.display.shading.show_cavity=True;scene.display.shading.cavity_type="WORLD"
    scene.render.resolution_x=360;scene.render.resolution_y=640;scene.render.resolution_percentage=100;scene.render.fps=30
    scene.render.image_settings.file_format="PNG"
    folder=OUT/"renders"/args.view/"frames";folder.mkdir(parents=True,exist_ok=True)
    scene_hash=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()
    provenance={"scene_sha256":scene_hash,"renderer_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "view":args.view,"visualization":args.visualization,"resolution":[360,640],"fps":30,
        "started_utc":datetime.now(timezone.utc).isoformat()}
    record=folder/"render-provenance.json"
    if record.exists() and not args.force:
        previous=json.loads(record.read_text())
        for key in ("scene_sha256","renderer_sha256","view","visualization"):
            if previous.get(key)!=provenance[key]:raise RuntimeError("Render provenance changed: "+key)
    record.write_text(json.dumps(provenance,indent=2))
    pending=[f for f in range(args.start,args.end+1) if args.force or not (folder/f"{f:04d}.png").exists()]
    if pending:
        scene.frame_start=pending[0];scene.frame_end=pending[-1]
        scene.render.filepath=str(folder)+"/"
        bpy.ops.render.render(animation=True)
    print("MOTION_LAB_RENDER_COMPLETE",args.view,args.start,args.end)


if __name__=="__main__":main()
