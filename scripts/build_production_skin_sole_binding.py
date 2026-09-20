"""Correct only Omni-Man's planted production-foot binding in frames 90-98."""
from pathlib import Path
from datetime import datetime,timezone
import bpy,hashlib,json,shutil
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'outputs/combat_motion_lab_production_skin_correction';OUT=ROOT/'outputs/combat_motion_lab_production_skin_sole_binding';EXPECTED='4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sig(a):
 p=[(c.data_path,c.array_index,[(round(k.co.x,7),round(k.co.y,9),k.interpolation) for k in c.keyframe_points]) for c in sorted(a.fcurves,key=lambda x:(x.data_path,x.array_index))]
 return hashlib.sha256(json.dumps(p,separators=(',',':')).encode()).hexdigest()
assert sha(SOURCE/'source/events.json')==EXPECTED
bpy.ops.wm.open_mainfile(filepath=str(SOURCE/'scene.blend'))
for d in ('review','source','renders/preview','renders/quality-preview','renders/foot-closeup'):(OUT/d).mkdir(parents=True,exist_ok=True)
shutil.copy2(SOURCE/'source/events.json',OUT/'source/events.json');shutil.copy2(SOURCE/'review/provenance-report.json',OUT/'source/parent-provenance.json')
protected=('HA_ROOT_fighter_a','HA_ROOT_fighter_b','HA_BODY_OMNI','HA_BODY_NARUTO');before={n:sig(bpy.data.actions[n]) for n in protected}
rig=bpy.data.objects['fighter_a_ProductionRig'];action=bpy.data.actions.new('SKINBIND_OMNI_PLANTED_SOLE')
path='pose.bones["Foot_L"].location';offsets=[(1,0.0),(89,0.0),(90,-.153),(91,-.173),(92,-.181),(93,-.169),(94,-.139),(95,-.122),(96,-.118),(97,-.109),(98,-.104),(99,-.060),(100,-.025),(102,0.0),(108,0.0)]
for i in range(3):
 c=action.fcurves.new(path,index=i)
 for f,z in offsets:
  k=c.keyframe_points.insert(f,z if i==2 else 0.0);k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
right_offsets=[(1,0.0),(92,0.0),(93,-.075),(94,-.151),(95,-.139),(96,-.139),(97,-.075),(98,0.0),(108,0.0)]
right_path='pose.bones["Foot_R"].location'
for i in range(3):
 c=action.fcurves.new(right_path,index=i)
 for f,z in right_offsets:
  k=c.keyframe_points.insert(f,z if i==2 else 0.0);k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
track=rig.animation_data.nla_tracks.new();track.name='SKINBIND_OMNI_PLANTED_SOLE';strip=track.strips.new(action.name,1,action);strip.frame_start=1;strip.frame_end=108;strip.action_frame_start=1;strip.action_frame_end=108
if action.slots:strip.action_slot=action.slots[0]
after={n:sig(bpy.data.actions[n]) for n in protected};assert before==after
# Dedicated technical foot camera; production cameras remain untouched.
data=bpy.data.cameras.new('SKINBIND_CAM_Foot_Data');data.lens=62;data.sensor_fit='VERTICAL';cam=bpy.data.objects.new('SKINBIND_CAM_Foot',data);scene=bpy.context.scene;scene.collection.objects.link(cam)
for f,loc,target in [(90,(3.6,-6.0,.82),(-.55,-.12,.20)),(94,(3.3,-6.1,.76),(-.86,.00,.18)),(98,(3.0,-6.2,.74),(-1.02,.08,.18))]:
 cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.keyframe_insert('location',frame=f);cam.keyframe_insert('rotation_euler',frame=f)
for c in cam.animation_data.action.fcurves:
 for k in c.keyframe_points:k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
scene['wws_sole_binding_parent_sha256']=sha(SOURCE/'scene.blend');scene['wws_sole_binding_scope']='Omni-Man production Foot_L local binding only';scene['wws_canonical_events_sha256']=EXPECTED;scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'scene.blend'))
report={'schema_version':1,'generated_utc':datetime.now(timezone.utc).isoformat(),'source_scene':str(SOURCE/'scene.blend'),'source_scene_sha256':sha(SOURCE/'scene.blend'),'derived_scene':str(OUT/'scene.blend'),'derived_scene_sha256':sha(OUT/'scene.blend'),'canonical_events_sha256':sha(OUT/'source/events.json'),'timeline':[1,108],'contact_hold':[82,84],'protected_action_signatures':{n:{'before':before[n],'after':after[n],'identical':True} for n in protected},'new_action':action.name,'bones':['fighter_a_ProductionRig/Foot_L','fighter_a_ProductionRig/Foot_R'],'property':'location.z','authored_offsets':{'Foot_L':offsets,'Foot_R':right_offsets},'root_or_body_actions_edited':False,'naruto_edited':False,'collision_driven_motion':False}
(OUT/'review/build-provenance.json').write_text(json.dumps(report,indent=2)+'\n');print('SOLE_BINDING_BUILT',report['derived_scene_sha256'])
