"""Print the Motion Lab source state used for the isolated hero exchange."""

import bpy

scene = bpy.context.scene
print("SCENE", bpy.data.filepath, scene.frame_start, scene.frame_end, scene.render.fps)
for name in ("fighter_a_Rig", "fighter_b_Rig", "fighter_a_ProductionRig", "fighter_b_ProductionRig"):
    obj = bpy.data.objects.get(name)
    print("OBJECT", name, bool(obj), obj.type if obj else None)
    if not obj:
        continue
    ad = obj.animation_data
    print(" ACTION", ad.action.name if ad and ad.action else None)
    if ad:
        print(" NLA", [(track.name, track.mute, [(strip.name, strip.frame_start, strip.frame_end) for strip in track.strips]) for track in ad.nla_tracks])
    if obj.type == "ARMATURE":
        print(" BONES", [bone.name for bone in obj.pose.bones])

for frame in (268, 278, 286, 294, 303, 316, 324, 332, 342, 350, 358, 362, 365, 368, 371, 379, 390):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    out = ["FRAME", frame]
    for prefix in ("fighter_a", "fighter_b"):
        rig = bpy.data.objects[prefix + "_ProductionRig"]
        root = bpy.data.objects[prefix + "_Rig"]
        out.extend((prefix, tuple(round(v, 3) for v in root.location)))
        for bone_name in ("Hips", "SpineUpper", "Hand_R", "Hand_L", "Foot_R", "Foot_L"):
            bone = rig.pose.bones[bone_name]
            p = rig.matrix_world @ bone.head.lerp(bone.tail, 0.65)
            out.append((bone_name, tuple(round(v, 3) for v in p)))
    print(*out)
