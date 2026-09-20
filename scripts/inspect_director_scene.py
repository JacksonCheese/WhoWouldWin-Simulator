"""Read-only scene inspection for the directing pass."""
import bpy, json
from pathlib import Path
out = Path(__file__).resolve().parents[1] / 'outputs/first_production_fight_astra_final/review'
out.mkdir(parents=True, exist_ok=True)
data = {'objects': {}, 'frames': {}}
for name in ['fighter_a_Rig','fighter_b_Rig','fighter_a_ProductionRig','OmniMan_Cape','Rasengan_Control']:
    o=bpy.data.objects[name]
    d={'type':o.type,'parent':o.parent.name if o.parent else None,'parent_bone':o.parent_bone,'location':list(o.location),'scale':list(o.scale),'matrix_basis':[list(r) for r in o.matrix_basis]}
    if o.animation_data:
        d['active_action']=o.animation_data.action.name if o.animation_data.action else None
        d['nla']=[{'name':t.name,'mute':t.mute,'strips':[(s.action.name,s.frame_start,s.frame_end,s.influence,s.blend_type) for s in t.strips]} for t in o.animation_data.nla_tracks]
    if o.type=='ARMATURE':
        d['bones']={b.name:{'head':list(b.head_local),'tail':list(b.tail_local),'constraints':[(c.type,getattr(c,'target',None).name if getattr(c,'target',None) else None,getattr(c,'subtarget','')) for c in o.pose.bones[b.name].constraints]} for b in o.data.bones}
    if o.type=='MESH': d['vertices']=[list(v.co) for v in o.data.vertices]
    data['objects'][name]=d
for f in [16,56,76,106,166,196,226,256,286,303,316,342,360,365,368,371,381,406,436,466,526]:
    bpy.context.scene.frame_set(f)
    data['frames'][f]={}
    for prefix in ['fighter_a','fighter_b']:
        o=bpy.data.objects[prefix+'_ProductionRig']
        data['frames'][f][prefix]={b.name:[list(o.matrix_world@b.head),list(o.matrix_world@b.tail)] for b in o.pose.bones if b.name in ['Hips','SpineUpper','Head','UpperArm_R','LowerArm_R','Hand_R','Foot_R','Foot_L']}
data['actions']={a.name:{'fcurves':len(a.fcurves),'frames':list(a.frame_range)} for a in bpy.data.actions}
(out/'source-scene-inspection.json').write_text(json.dumps(data,indent=2))
print('INSPECTION_COMPLETE')
