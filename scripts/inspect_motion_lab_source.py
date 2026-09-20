"""Read-only inspection of the final fight for Combat Motion Lab authoring."""
import bpy, json

scene=bpy.context.scene
payload={"frame_range":[scene.frame_start,scene.frame_end],"fps":scene.render.fps,"rigs":{}}
for prefix in ("fighter_a","fighter_b"):
    root=bpy.data.objects[prefix+"_Rig"]
    production=bpy.data.objects[prefix+"_ProductionRig"]
    payload["rigs"][prefix]={
        "root_action":root.animation_data.action.name if root.animation_data and root.animation_data.action else None,
        "root_bones":[b.name for b in root.data.bones],
        "production_bones":[b.name for b in production.data.bones],
        "nla":[{"track":t.name,"strip":s.name,"action":s.action.name,"start":s.frame_start,"end":s.frame_end,
                "action_start":s.action_frame_start,"action_end":s.action_frame_end,"scale":s.scale,"repeat":s.repeat}
               for t in root.animation_data.nla_tracks for s in t.strips],
    }
print("MOTION_LAB_SOURCE",json.dumps(payload))
