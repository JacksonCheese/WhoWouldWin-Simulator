"""Tightly scoped body/deformation correction derived from the skin feasibility scene."""
from pathlib import Path
from datetime import datetime, timezone
import bpy, hashlib, json, shutil
from mathutils import Euler, Quaternion, Vector

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'outputs/combat_motion_lab_production_skin_feasibility'
OUT=ROOT/'outputs/combat_motion_lab_production_skin_correction'
EXPECTED='4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def signature(action):
 payload=[]
 for c in sorted(action.fcurves,key=lambda x:(x.data_path,x.array_index)):
  payload.append((c.data_path,c.array_index,[(round(k.co.x,7),round(k.co.y,9),k.interpolation) for k in c.keyframe_points]))
 return hashlib.sha256(json.dumps(payload,separators=(',',':')).encode()).hexdigest()

def insert_curve(action,path,index,keys,constant=()):
 c=action.fcurves.find(path,index=index) or action.fcurves.new(path,index=index)
 for f,v in keys:
  old=next((k for k in c.keyframe_points if abs(k.co.x-f)<.001),None)
  if old: c.keyframe_points.remove(old,fast=True)
  k=c.keyframe_points.insert(f,v,options={'FAST'});k.interpolation='CONSTANT' if f in constant else 'BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
 c.update()

def pose(action,source,bone,keys,constant=()):
 path=f'pose.bones["{bone}"].rotation_quaternion'
 qs=[]
 for f,e in keys:
  q=Quaternion([source.fcurves.find(path,index=i).evaluate(f) for i in range(4)]).normalized()
  qs.append((f,(q@Euler(e,'XYZ').to_quaternion()).normalized()))
 for i in range(4):insert_curve(action,path,i,[(f,q[i]) for f,q in qs],constant)

def add_skin_offset_action(rig_name,name,bone,keys):
 rig=bpy.data.objects[rig_name]
 action=bpy.data.actions.get(name) or bpy.data.actions.new(name)
 path=f'pose.bones["{bone}"].location'
 base=rig.pose.bones[bone].location.copy()
 for i in range(3):insert_curve(action,path,i,[(f,base[i]+delta[i]) for f,delta in keys],constant=(82,83,84))
 track=rig.animation_data.nla_tracks.get(name) or rig.animation_data.nla_tracks.new();track.name=name
 if not track.strips:
  strip=track.strips.new(name,1,action);strip.frame_start=1;strip.frame_end=108;strip.action_frame_start=1;strip.action_frame_end=108
  if action.slots: strip.action_slot=action.slots[0]
 return action

assert sha(SOURCE/'source/events.json')==EXPECTED
bpy.ops.wm.open_mainfile(filepath=str(SOURCE/'scene.blend'))
for d in ('review','source','renders/preview','renders/quality-preview','renders/contact-closeup'):(OUT/d).mkdir(parents=True,exist_ok=True)
shutil.copy2(SOURCE/'source/events.json',OUT/'source/events.json')
shutil.copy2(SOURCE/'review/build-provenance.json',OUT/'source/parent-build-provenance.json')
roots={n:signature(bpy.data.actions[n]) for n in ('HA_ROOT_fighter_a','HA_ROOT_fighter_b')}
body_n=bpy.data.actions['HA_BODY_NARUTO']; body_o=bpy.data.actions['HA_BODY_OMNI']
src_n=body_n.copy();src_o=body_o.copy();src_n.name='CORRECTION_SOURCE_N';src_o.name='CORRECTION_SOURCE_O'
Z=(0,0,0)
# Naruto 68-80: leg-driven low entry; root and tangent target are untouched.
pose(body_n,src_n,'pelvis',[(68,Z),(71,(.015,-.035,.015)),(75,(.025,-.055,.025)),(79,(.015,-.035,.018)),(80,Z)])
pose(body_n,src_n,'thigh.L',[(68,Z),(71,(.10,0,-.025)),(74,(.17,0,-.04)),(77,(.07,0,-.02)),(80,Z)])
pose(body_n,src_n,'shin.L',[(68,Z),(71,(-.13,0,0)),(74,(-.23,0,0)),(77,(-.08,0,0)),(80,Z)])
pose(body_n,src_n,'foot.L',[(68,Z),(71,(.08,0,0)),(74,(.18,0,0)),(77,(.05,0,0)),(80,Z)])
pose(body_n,src_n,'thigh.R',[(68,Z),(72,(-.04,0,.025)),(76,(.08,0,.04)),(79,(.03,0,.015)),(82,Z)])
pose(body_n,src_n,'clavicle.R',[(68,Z),(74,(0,-.025,.045)),(78,(0,-.045,.075)),(81,(0,-.035,.06)),(82,(0,-.03,.05)),(84,(0,-.03,.05)),(86,Z)],constant=(82,83,84))
pose(body_n,src_n,'upper_arm.R',[(68,Z),(74,(.025,-.02,.025)),(78,(.055,-.04,.04)),(81,(.075,-.05,.05)),(82,(.085,-.055,.055)),(84,(.085,-.055,.055)),(86,Z)],constant=(82,83,84))
pose(body_n,src_n,'forearm.R',[(68,Z),(74,(.02,.025,-.02)),(78,(.055,.04,-.035)),(81,(.08,.055,-.045)),(82,(.095,.06,-.05)),(84,(.095,.06,-.05)),(86,Z)],constant=(82,83,84))
pose(body_n,src_n,'hand.R',[(68,Z),(75,(.025,.045,-.035)),(78,(.055,.075,-.055)),(81,(.07,.095,-.07)),(82,(.075,.105,-.075)),(84,(.075,.105,-.075)),(86,Z)],constant=(82,83,84))
# Production-skin pelvis offsets lower the COM while existing authored foot IK carries the plants.
add_skin_offset_action('fighter_b_ProductionRig','SKINCORR_NARUTO_BODY','Hips',[(1,Z),(67,Z),(70,(0,0,-.035)),(74,(0,0,-.075)),(80,(0,0,-.055)),(82,(0,0,-.04)),(84,(0,0,-.04)),(86,Z),(108,Z)])
# Omni 82-98: pelvis first, chest one frame later, asymmetric limb lag; root Action unchanged.
pose(body_o,src_o,'pelvis',[(82,Z),(84,Z),(85,(.035,.02,-.035)),(86,(.07,.035,-.055)),(88,(.09,.045,-.065)),(92,(.045,.025,-.035)),(95,(-.025,-.015,.02)),(98,Z)],constant=(82,83,84))
pose(body_o,src_o,'chest',[(82,Z),(84,Z),(85,Z),(86,(.025,.01,-.02)),(87,(.065,.025,-.045)),(89,(.10,.04,-.065)),(92,(.055,.02,-.04)),(96,(-.025,-.01,.015)),(98,Z)],constant=(82,83,84))
pose(body_o,src_o,'clavicle.L',[(82,Z),(84,Z),(86,(.015,.02,.025)),(89,(.045,.055,.07)),(92,(.025,.035,.045)),(96,Z),(98,Z)],constant=(82,83,84))
pose(body_o,src_o,'upper_arm.L',[(82,Z),(84,Z),(86,(.035,.015,.025)),(89,(.11,.045,.08)),(92,(.16,.055,.11)),(96,(.035,.01,.025)),(98,Z)],constant=(82,83,84))
pose(body_o,src_o,'upper_arm.R',[(82,Z),(84,Z),(87,(-.025,-.015,-.02)),(90,(-.10,-.04,-.07)),(93,(-.14,-.05,-.09)),(96,(-.025,0,-.015)),(98,Z)],constant=(82,83,84))
pose(body_o,src_o,'forearm.R',[(82,Z),(84,Z),(88,(-.035,.03,-.025)),(92,(-.10,.06,-.055)),(95,(-.025,.015,-.015)),(98,Z)],constant=(82,83,84))
add_skin_offset_action('fighter_a_ProductionRig','SKINCORR_OMNI_BODY','Hips',[(1,Z),(81,Z),(82,(0,0,-.015)),(84,(0,0,-.015)),(86,(0,0,-.045)),(89,(0,0,-.085)),(92,(0,0,-.105)),(95,(0,0,-.10)),(98,(0,0,-.075)),(100,Z),(108,Z)])
# Explicit left-foot catch measured from the inherited recoil pose.  These are
# authored knots, not a runtime ground/collision solve.
left=bpy.data.objects['RR_a_L_FOOT']; la=left.animation_data.action
catch=[(90,(-.5973,-.0957,.19)),(92,(-.8727,-.0623,.14)),(95,(-1.0083,.0703,.13)),(98,(-1.131,.1743,.13)),(100,(-1.1161,.1009,.18))]
for i in range(3):insert_curve(la,'location',i,[(f,p[i]) for f,p in catch])
quats=[(90,(.899348,-.171203,-.196719,-.350948)),(92,(.905054,-.127105,-.172809,-.367233)),(95,(.872844,-.099616,-.179223,-.442832)),(98,(.828544,-.12736,-.100031,-.535992)),(100,(.830082,-.13288,-.098105,-.532618))]
for i in range(4):insert_curve(la,'rotation_quaternion',i,[(f,q[i]) for f,q in quats])
controls=bpy.data.actions['RR_CONTROLS_a']
for path in ('pose.bones["LowerLeg_L"].constraints["RR authored support L"].influence','pose.bones["Foot_L"].constraints["RR authored sole L"].influence'):
 insert_curve(controls,path,0,[(85,0),(89,0),(90,.35),(92,1),(98,1),(100,0),(108,0)])
# Recoil camera: preserve medium contact, widen progressively and reacquire both performers.
cam=bpy.data.objects['SKINTEST_CAM_Recoil'];cam.data.lens=42
for f,loc,target,lens in [(85,(6.1,-9.8,3.45),(.15,.48,1.55),48),(92,(5.8,-10.2,3.65),(-.05,.32,1.45),43),(98,(5.4,-10.8,3.8),(-.18,.20,1.38),38)]:
 cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=lens
 cam.keyframe_insert('location',frame=f);cam.keyframe_insert('rotation_euler',frame=f);cam.data.keyframe_insert('lens',frame=f)
for c in cam.animation_data.action.fcurves:
 for k in c.keyframe_points:k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
# Ensure immutable root curves and event/timeline invariants.
assert roots=={n:signature(bpy.data.actions[n]) for n in roots}
for a in (src_n,src_o):bpy.data.actions.remove(a)
scene=bpy.context.scene;scene.frame_start=1;scene.frame_end=108;scene.render.fps=30
scene['wws_skin_correction_parent_sha256']=sha(SOURCE/'scene.blend');scene['wws_canonical_events_sha256']=EXPECTED
scene['wws_root_actions_unchanged']=True;scene['wws_contact_hold']='82-84';scene['wws_scope']='targeted production-skin correction'
scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'scene.blend'))
report={'schema_version':1,'generated_utc':datetime.now(timezone.utc).isoformat(),'source_scene':str(SOURCE/'scene.blend'),'source_scene_sha256':sha(SOURCE/'scene.blend'),'derived_scene':str(OUT/'scene.blend'),'derived_scene_sha256':sha(OUT/'scene.blend'),'canonical_events_sha256':sha(OUT/'source/events.json'),'timeline':[1,108],'contact_hold':[82,84],'root_action_signatures_before_after':{n:{'before':v,'after':signature(bpy.data.actions[n]),'identical':True} for n,v in roots.items()},'body_root_separation_preserved':True,'root_trajectories_edited':False,'collision_solver_used':False,'mixamo_or_mocap_used':False,'edits':['Naruto body/leg/arm frames 68-86','Omni-Man compression and lag frames 82-98','production-rig Hips skin offsets','authored Omni-Man left-foot catch frames 90-100','recoil camera frames 85-98']}
(OUT/'review/build-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
print('SKIN_CORRECTION_BUILT',report['derived_scene_sha256'])
