import bpy, json
payload={}
for name in ('fighter_a_Rig','fighter_b_Rig'):
    action=bpy.data.objects[name].animation_data.action
    payload[name]={}
    for curve in action.fcurves:
        if curve.data_path in {'location','rotation_euler'}:
            payload[name][curve.data_path+':'+str(curve.array_index)]=[[round(k.co.x,3),round(k.co.y,4),k.interpolation] for k in curve.keyframe_points]
print('MOTION_ROOT_KEYS',json.dumps(payload))
