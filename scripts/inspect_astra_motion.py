import bpy, json
s=bpy.context.scene
out={}
for slot in ('fighter_a','fighter_b'):
 r=bpy.data.objects[slot+'_Rig']; out[slot]={}
 out[slot]['constraints']={b.name:[{'name':c.name,'type':c.type,'influence':c.influence,'target':getattr(getattr(c,'target',None),'name',None),'chain':getattr(c,'chain_count',None)} for c in b.constraints] for b in r.pose.bones if b.constraints}
 out[slot]['rest']={b.name:{'head':list(b.head_local),'tail':list(b.tail_local),'matrix':list(map(list,b.matrix_local))} for b in r.data.bones}
 out[slot]['samples']=[]
 for f in (1,42,48,56,65,78,106,138,152,196,256,286,294,303,312,316,332,350,362,365,368,371,397,418,448,476,526):
  s.frame_set(f);bpy.context.view_layer.update()
  out[slot]['samples'].append({'frame':f,'loc':list(r.location),'rot':list(r.rotation_euler),'bones':{b.name:{'rot':list(b.rotation_euler),'loc':list(b.location),'head':list(r.matrix_world@b.head),'tail':list(r.matrix_world@b.tail)} for b in r.pose.bones}})
open('/tmp/astra-motion-data.json','w').write(json.dumps(out,indent=2))
