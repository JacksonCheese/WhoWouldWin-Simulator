"""Shot-specific authored root/support revision of the existing 108-frame Actions.
No collision-driven motion, clip replacement, mocap or runtime pose generation.
"""
from pathlib import Path
import json,hashlib,shutil,math
import bpy
from mathutils import Vector,Quaternion,Euler,Matrix
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'outputs/combat_motion_lab_hand_authored_polish'
OUT=ROOT/'outputs/combat_motion_lab_hand_authored_root_revision'
EXPECTED='4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(SOURCE/'source/events.json')==EXPECTED
bpy.ops.wm.open_mainfile(filepath=str(SOURCE/'scene.blend'))
for folder in ('review','source'): (OUT/folder).mkdir(parents=True,exist_ok=True)
for p in (SOURCE/'source').glob('*'):
 if p.is_file(): shutil.copy2(p,OUT/'source'/p.name)
shutil.copy2(SOURCE/'review/action-provenance.json',OUT/'source/previous-polish-provenance.json')
scene=bpy.context.scene
original={a.name:a.copy() for a in list(bpy.data.actions) if a.name.startswith(('HA_BODY_','HA_ROOT_'))}
log=[]
baseline_feet={}
for f in (1,7,8,36,40,43,79,81,82,84,98,104):
 scene.frame_set(f);bpy.context.view_layer.update()
 for tag in ('a','b'):
  r=bpy.data.objects['fighter_'+tag+'_ProductionRig']
  for side in ('L','R'):
   b=r.pose.bones['Foot_'+side]
   baseline_feet[tag,side,f]=(tuple(r.matrix_world@b.head),(r.matrix_world@b.matrix).to_quaternion().copy())


def replace_segment(action,path,index,keys):
 """Replace a bounded F-curve segment; preserve outside Bezier handles."""
 c=action.fcurves.find(path,index=index)
 if c is None: c=action.fcurves.new(path,index=index)
 lo,hi=keys[0][0],keys[-1][0]
 outside=[(k.co.x,k.co.y,tuple(k.handle_left),tuple(k.handle_right),k.interpolation) for k in c.keyframe_points if k.co.x<=lo or k.co.x>=hi]
 for index_to_remove in reversed(range(len(c.keyframe_points))):
  k=c.keyframe_points[index_to_remove]
  if lo<=k.co.x<=hi:c.keyframe_points.remove(k,fast=True)
 for f,value in keys:
  k=c.keyframe_points.insert(f,value,options={'FAST'});k.interpolation='CONSTANT' if f==82 else 'BEZIER'
  k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
 c.update()
 # Freeze the retained outside halves, avoiding auto-handle ripple.
 for f,value,left,right,interp in outside:
  k=next((k for k in c.keyframe_points if abs(k.co.x-f)<.001),None)
  if k is None: continue
  if f<lo or f>hi:
   k.handle_left_type=k.handle_right_type='FREE';k.handle_left=left;k.handle_right=right;k.interpolation=interp
  elif f==lo:
   rh=k.handle_right.copy();k.handle_left_type=k.handle_right_type='FREE';k.handle_left=left;k.handle_right=rh
  elif f==hi:
   lh=k.handle_left.copy();k.handle_left_type=k.handle_right_type='FREE';k.handle_left=lh;k.handle_right=right;k.interpolation=interp
 c.update()

def root(tag,keys):
 a=bpy.data.actions['HA_ROOT_fighter_'+tag]
 for i in range(3):replace_segment(a,'location',i,[(f,xyz[i]) for f,xyz,yaw in keys])
 replace_segment(a,'rotation_euler',2,[(f,yaw) for f,xyz,yaw in keys])
 log.append({'root':tag,'keys':keys})

def old_root(tag,f):
 a=original['HA_ROOT_fighter_'+tag]
 return ([a.fcurves.find('location',index=i).evaluate(f) for i in range(3)],a.fcurves.find('rotation_euler',index=2).evaluate(f))

# Naruto: compact passing step, follow-leg recovery, then inward entry.
# +2pi continuation prevents an Euler wrap; rotations after 82 are equivalent.
xyz43,y43=old_root('b',43)
nkeys=[(43,xyz43,y43),(45,(.91,-.90,-.04),2.42),(47,(.98,-.69,-.035),2.62),
 (49,(1.04,-.31,.005),2.88),(52,(1.04,.16,-.055),3.16),
 (56,(1.12,.38,-.075),3.39),(58,(1.18,.51,-.10),3.51),(61,(1.30,.74,-.045),3.62),
 (68,(1.40,1.04,-.10),3.76),(72,(1.35,1.11,-.07),3.83),
 (76,(1.20,1.17,.015),3.90),(79,(1.10,1.19,.045),3.925)]
# Unwrap the retained recovery too; no world-space displacement is introduced.
a=bpy.data.actions['HA_ROOT_fighter_b'];c=a.fcurves.find('rotation_euler',index=2)
for k in c.keyframe_points:
 if k.co.x>=82:
  k.co.y+=2*math.pi;k.handle_left.y+=2*math.pi;k.handle_right.y+=2*math.pi
xyz82,y82=old_root('b',82);nkeys.append((82,xyz82,y82+2*math.pi));root('b',nkeys)
# Partner follows the smaller angle, rather than turning toward the old far arrival.
a=bpy.data.actions['HA_ROOT_fighter_a'];old=original[a.name]
replace_segment(a,'rotation_euler',2,[(43,old_root('a',43)[1]),(47,-.47),(52,.025),(58,.28),(65,.56),(76,.70),(82,old_root('a',82)[1])])
# Contact-response compression precedes the continuous recoil acceleration.
x84,y84=old_root('a',84);x98,y98=old_root('a',98)
root('a',[(84,x84,y84),(85,(-.045,.116,.015),y84),(86,(-.085,.078,-.035),y84+.012),
 (88,(-.26,-.05,.02),y84+.04),(90,(-.51,-.17,.11),y84+.075),
 (92,(-.74,-.24,.13),y84+.065),(95,(-.97,-.215,.065),y84+.025),(98,x98,y98)])

# Existing body Actions receive a few deliberate supporting breakdowns only.
def body(tag,bone,keys):
 name='HA_BODY_'+('OMNI' if tag=='a' else 'NARUTO');a=bpy.data.actions[name];src=original[name]
 path=f'pose.bones["{bone}"].rotation_quaternion'
 values=[]
 for f,delta in keys:
  q=Quaternion([src.fcurves.find(path,index=i).evaluate(f) for i in range(4)]).normalized() @ Euler(delta).to_quaternion()
  values.append((f,q.normalized()))
 for i in range(4):replace_segment(a,path,i,[(f,q[i]) for f,q in values])
 log.append({'body':tag,'bone':bone,'offset_keys':keys})
Z=(0,0,0)
# Keep the idle arm compact instead of allowing a broad counter gesture.
body('b','upper_arm.R',[(30,Z),(33,(.08,.03,-.12)),(36,(.10,.04,-.15)),(39,(.035,.01,-.06)),(43,Z)])
body('b','forearm.R',[(30,Z),(34,(.10,-.06,.06)),(37,(.12,-.04,.08)),(43,Z)])
body('a','hand.L',[(30,Z),(34,(.025,.045,-.025)),(37,(.025,.065,-.045)),(40,Z)])
# Short torso lead and landing compression without folding the ribcage.
body('b','pelvis',[(43,Z),(46,(0,-.015,.03)),(49,(0,-.025,.04)),(52,(0,-.01,.025)),(61,Z)])
body('b','chest',[(43,Z),(45,(0,-.01,.045)),(48,(0,-.02,.05)),(52,(0,-.015,.02)),(61,Z)])
body('b','clavicle.R',[(68,Z),(72,(0,-.025,.035)),(76,(0,-.025,.045)),(80,Z),(82,Z)])
body('b','pelvis',[(68,Z),(71,(0,-.04,.015)),(75,(0,-.025,.02)),(79,(0,-.01,.01)),(82,Z)])
body('b','chest',[(68,Z),(72,(0,-.02,.015)),(77,(0,-.03,.02)),(80,Z),(82,Z)])
# Wave from hips to ribcage to shoulders; do not break the 82–84 contact hold.
body('a','pelvis',[(84,Z),(86,(0,.045,-.025)),(89,(0,.055,-.045)),(92,(0,.015,-.025)),(95,(0,-.03,.015)),(98,Z)])
body('a','chest',[(84,Z),(86,(0,.015,-.01)),(88,(0,.06,-.03)),(91,(0,.075,-.04)),(94,(0,.015,-.01)),(97,(0,-.025,.015)),(98,Z)])
body('a','clavicle.L',[(84,Z),(88,(.015,.03,.035)),(91,(.025,.035,.045)),(95,(0,.01,.01)),(98,Z)])
body('a','upper_arm.L',[(84,Z),(88,(.06,.02,.035)),(91,(.12,.035,.065)),(95,(.035,.01,.02)),(98,Z)])
body('a','upper_arm.R',[(84,Z),(89,(-.04,-.015,-.025)),(92,(-.09,-.025,-.04)),(96,(-.02,0,-.01)),(98,Z)])

# Authored foot targets use existing IK types for support and swing. They do not
# calculate trajectories from collisions. Target keys explicitly define the step.
collection=bpy.data.collections['HA_AUTHORED_CONTROLS']
new_pins=[]
def foot_control(tag,side,points,weights,yaw_keys,phases):
 rig=bpy.data.objects['fighter_'+tag+'_ProductionRig']
 target=bpy.data.objects.new(f'RR_{tag}_{side}_FOOT',None);collection.objects.link(target)
 target.empty_display_type='CUBE';target.empty_display_size=.10;target.rotation_mode='QUATERNION'
 scene.frame_set(points[0][0]);bpy.context.view_layer.update()
 start_rot=(rig.matrix_world@rig.pose.bones['Foot_'+side].matrix).to_quaternion()
 for f,p in points:
  target.location=p;target.keyframe_insert('location',frame=f)
 for f,angle in yaw_keys:
  target.rotation_quaternion=Quaternion((0,0,1),angle)@start_rot;target.keyframe_insert('rotation_quaternion',frame=f)
 for c in target.animation_data.action.fcurves:
  for k in c.keyframe_points:k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
 pole=bpy.data.objects.new(f'RR_{tag}_{side}_KNEE',None);collection.objects.link(pole)
 # A few partner-facing pole positions, deliberately not frame-by-frame solves.
 for f,p in points:
  pole.location=(p[0]+(.70 if tag=='a' else -.75),p[1]+(.40 if tag=='a' else (.12 if side=='L' else -.12)),.85);pole.keyframe_insert('location',frame=f)
 for c in pole.animation_data.action.fcurves:
  for k in c.keyframe_points:k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
 shin=rig.pose.bones['LowerLeg_'+side];foot=rig.pose.bones['Foot_'+side]
 ik=shin.constraints.new('IK');ik.name='RR authored support '+side;ik.target=target;ik.pole_target=pole;ik.chain_count=2;ik.use_stretch=False
 sole=foot.constraints.new('COPY_ROTATION');sole.name='RR authored sole '+side;sole.target=target
 controls=bpy.data.actions.get('RR_CONTROLS_'+tag)
 if not controls:
  controls=bpy.data.actions.new('RR_CONTROLS_'+tag)
  track=rig.animation_data.nla_tracks.new();track.name='RR_AUTHORED_SUPPORT';track.strips.new(controls.name,1,controls)
 rig.animation_data.action=controls
 for c in (ik,sole):
  for f,w in weights:c.influence=w;c.keyframe_insert('influence',frame=f)
 rig.animation_data.action=None
 for c in controls.fcurves:
  for k in c.keyframe_points:k.interpolation='LINEAR'
 new_pins.extend({'fighter':'naruto' if tag=='b' else 'omniman','tag':tag,'side':side,'frames':x,'target':target.name} for x in phases)
 log.append({'foot':tag+side,'points':points,'influence':weights,'yaw':yaw_keys,'support_phases':phases})

foot_control('b','L',[(43,(.80,-1.12,.196)),(46,(.80,-1.12,.196)),(49,(1.16,-.75,.34)),
 (53,(1.32,-.16,.24)),(56,(1.35,.20,.22)),(61,(1.50,.65,.196)),(67,(1.50,.65,.196)),
 (72,(1.48,.73,.31)),(76,(1.24,1.03,.36)),(80,(.98,1.30,.247))],
 [(1,0),(42,0),(44,1),(78,1),(81,0),(108,0)],[(43,0),(46,0),(53,.80),(61,1.05),(67,1.05),(76,1.45),(80,1.58)],[(44,46),(61,67)])
foot_control('b','R',[(43,(1.22,-.90,.24)),(45,(1.22,-.90,.24)),(48,(.96,-.41,.48)),
 (51,(.82,.17,.25)),(52,(.82,.23,.24)),(58,(.82,.23,.24)),(60,(.96,.53,.35)),
 (64,(1.10,.98,.24)),(71,(1.10,.98,.24)),(75,(1.13,1.13,.34)),(79,(1.20,1.40,.29))],
 [(1,0),(42,0),(44,1),(78,1),(81,0),(108,0)],[(43,0),(45,0),(51,.82),(58,.82),(64,1.25),(71,1.25),(79,1.59)],[(44,45),(52,58),(64,71)])
# Recoil plant releases before the main displacement, then the rear foot catches.
# The original contact pin remains authoritative through frame 84.
foot_control('a','R',[(84,(.108,-.221,.266)),(86,(.108,-.221,.266)),(89,(-.22,-.27,.40)),
 (92,(-.68,-.44,.27)),(94,(-.88,-.47,.225)),(96,(-.88,-.47,.225)),(98,(-.75,-.63,.25))],
 [(1,0),(84,0),(85,1),(96,1),(98,0),(108,0)],[(84,0),(86,0),(91,.06),(96,.04),(98,0)],[(85,86),(94,96)])

# A single IK solver per leg is necessary: even zero-weight legacy IK chains
# interfered with authored support targets in this inherited Blender scene.
removed=[]
for tag in ('a','b'):
 rig=bpy.data.objects['fighter_'+tag+'_ProductionRig']
 for bone in rig.pose.bones:
  if not any(part in bone.name for part in ('Leg','Foot')):continue
  for c in list(bone.constraints):
   if (c.type=='IK' or 'sole' in c.name.lower()) and not c.name.startswith('RR'):
    removed.append({'rig':rig.name,'bone':bone.name,'constraint':c.name,'type':c.type})
    bone.constraints.remove(c)
log.append({'derived_scene_only_legacy_leg_constraints_removed':removed})
# Retain the other declared supports using one target per chain. These points
# are sampled from the parent scene only at its existing plant boundaries.
def support_segment(tag,side,start,end,fade_in,fade_out):
 obj=bpy.data.objects[f'RR_{tag}_{side}_FOOT'];pos,q=baseline_feet[tag,side,start]
 for f in (start,end):
  obj.location=pos;obj.keyframe_insert('location',frame=f)
  obj.rotation_quaternion=q;obj.keyframe_insert('rotation_quaternion',frame=f)
 action=bpy.data.actions['RR_CONTROLS_'+tag]
 for c in action.fcurves:
  if f' {side}' in c.data_path:
   for f,w in ((fade_in,0),(start,1),(end,1),(fade_out,0)):
    k=c.keyframe_points.insert(f,w);k.interpolation='LINEAR'
 new_pins.append({'fighter':'naruto' if tag=='b' else 'omniman','tag':tag,'side':side,'frames':[start,end],'target':obj.name})
support_segment('b','L',1,7,0,11)
support_segment('b','L',98,104,96,108)
support_segment('a','R',1,8,0,12)
support_segment('a','R',36,40,34,43)
support_segment('a','R',79,84,77,85)
# Keep the recoil pin active across contact release (support_segment's fade at85
# is replaced by the already-authored compression keys).
for c in bpy.data.actions['RR_CONTROLS_a'].fcurves:
 for f in (85,86):k=c.keyframe_points.insert(f,1);k.interpolation='LINEAR'
support_segment('b','R',81,84,80,88)
# Smoothly blend the new swing into the old contact pin rather than disabling
# the target for one frame at 80.
for c in bpy.data.actions['RR_CONTROLS_b'].fcurves:
 if ' R' in c.data_path:
  for f in (78,79,80):k=c.keyframe_points.insert(f,1);k.interpolation='LINEAR'
foot_control('a','L',[(50,(-.18,.38,.22)),(52,(-.18,.38,.22)),(60,(-.18,.38,.22)),(64,(-.20,.35,.23))],
 [(1,0),(50,0),(52,1),(60,1),(64,0),(108,0)],[(50,0),(52,0),(60,0),(64,.15)],[(52,60)])

# Move the obsolete far-side arrival target out of the new step's way by muting
# only its old support interval; the new explicit target is the arrival source.
a=bpy.data.actions['HA_EVALUATED_CONTROLS_fighter_b']
for c in a.fcurves:
 if '52-58' in c.data_path:
  for k in c.keyframe_points:k.co.y=0;k.handle_left.y=0;k.handle_right.y=0
# Fit each support strip after all influence keys exist. Empty Actions initially
# create one-frame NLA strips, which must not truncate the authored controls.
for tag in ('a','b'):
 rig=bpy.data.objects['fighter_'+tag+'_ProductionRig']
 for track in rig.animation_data.nla_tracks:
  if track.name.startswith('RR_AUTHORED_SUPPORT'):
   for strip in track.strips:
    strip.action_frame_start=1;strip.action_frame_end=108;strip.frame_start=1;strip.frame_end=108
    if strip.action.slots: strip.action_slot=strip.action.slots[0]

# Keep the contact marker and hand targets exactly at their prior hold positions.
# Existing contact IK ramps retain the same combat-event times.
scene['wws_root_revision_parent_sha256']=sha(SOURCE/'scene.blend')
scene['wws_root_revision_method']='Explicit root and foot-support keys; existing paired body Actions; no collision pushes'
for copied in original.values():bpy.data.actions.remove(copied)
scene.frame_start=1;scene.frame_end=108;scene.render.fps=30;scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'scene.blend'))
report={'source_scene':str(SOURCE/'scene.blend'),'source_scene_sha256':sha(SOURCE/'scene.blend'),
 'scene_sha256':sha(OUT/'scene.blend'),'canonical_events_sha256':sha(OUT/'source/events.json'),
 'builder_sha256':sha(__file__),'timeline':[1,108],'fps':30,'contact_hold':[82,84],
 'root_motion_separate':True,'body_actions':['HA_BODY_OMNI','HA_BODY_NARUTO'],
 'root_actions':['HA_ROOT_fighter_a','HA_ROOT_fighter_b'],'collision_solver_used':False,
 'cameras_changed':False,'authored_edits':log,'new_support_intervals':new_pins,
 'note':'A presentation-only authored revision; no production animation approval implied.'}
(OUT/'review/action-provenance.json').write_text(json.dumps(report,indent=2))
print('ROOT_REVISION_SAVED',OUT)
