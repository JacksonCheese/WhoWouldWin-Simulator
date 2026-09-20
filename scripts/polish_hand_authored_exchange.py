"""Apply a small, explicitly authored Graph Editor pass to the saved paired Actions.

This edits existing F-curves; it neither generates a performance nor runs a
clearance solver. Root Actions and the original scene are immutable inputs.
Run with Blender --background --python this_file.py.
"""
from pathlib import Path
import hashlib
import json
import shutil
import bpy
from mathutils import Euler, Quaternion

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'outputs/combat_motion_lab_hand_authored_hero_exchange'
OUT = ROOT / 'outputs/combat_motion_lab_hand_authored_polish'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def curves(action):
    return list(action.fcurves)

def signature(action):
    return [{'path': c.data_path, 'index': c.array_index, 'extrapolation': c.extrapolation,
             'keys': [{'co': list(k.co), 'left': list(k.handle_left), 'right': list(k.handle_right),
                       'types': [k.handle_left_type, k.handle_right_type], 'interpolation': k.interpolation}
                      for k in c.keyframe_points]} for c in curves(action)]

def samples(action):
    return [[c.evaluate(f) for f in range(99, 109)] for c in curves(action)]

bpy.ops.wm.open_mainfile(filepath=str(SOURCE / 'scene.blend'))
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'review').mkdir(exist_ok=True)
(OUT / 'source').mkdir(exist_ok=True)
for p in (SOURCE / 'source').glob('*'):
    if p.is_file():
        shutil.copy2(p, OUT / 'source' / p.name)
shutil.copy2(SOURCE / 'review/action-provenance.json', OUT / 'source/parent-action-provenance.json')
root_actions = [bpy.data.actions['HA_ROOT_fighter_' + t] for t in ('a', 'b')]
root_before = {a.name: signature(a) for a in root_actions}
body = {t: bpy.data.actions[n] for t,n in [('o','HA_BODY_OMNI'),('n','HA_BODY_NARUTO')]}
body_before = {t: signature(a) for t,a in body.items()}
end_before = {t: samples(a) for t,a in body.items()}
original = {t: {(c.data_path,c.array_index): c for c in a.copy().fcurves} for t,a in body.items()}
edit_log = []

def pose(actor, bone, keys, delay=0):
    """Hand-specified local rotational breakdowns, relative to immutable input curves."""
    path = f'pose.bones["{bone}"].rotation_quaternion'
    source = [original[actor][(path,i)] for i in range(4)]
    dest = [body[actor].fcurves.find(path,index=i) for i in range(4)]
    for frame, angles in keys:
        q = Quaternion([c.evaluate(frame-delay if any(angles) or delay else frame) for c in source])
        q.normalize()
        q = q @ Euler(angles,'XYZ').to_quaternion()
        q.normalize()
        for i,c in enumerate(dest):
            k = c.keyframe_points.insert(frame,q[i],options={'FAST'})
            k.interpolation = 'CONSTANT' if frame in (82,83) else 'BEZIER'
            k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
    edit_log.append({'actor': actor, 'bone': bone, 'keys': keys, 'source_phase_delay': delay})

Z=(0,0,0)
# Shoulder initiates; the existing punch IK still owns the miss trajectory.
pose('o','clavicle.R',[(9,Z),(12,(0,-.025,.10)),(14,(0,-.02,.065)),(18,(0,0,-.025)),(22,Z)])
pose('o','upper_arm.R',[(9,Z),(13,(.025,0,.045)),(18,(0,0,-.025)),(22,Z)])
# A trailing knee clears the ground; no root or plant target is moved.
pose('n','thigh.R',[(9,Z),(15,(0,0,.13)),(17,(0,0,.25)),(20,(0,0,.07)),(22,Z)])
pose('n','shin.R',[(9,Z),(15,(0,0,-.19)),(18,(0,0,-.38)),(21,(0,0,-.06)),(22,Z)])
pose('n','foot.R',[(9,Z),(15,(.08,0,0)),(18,(.17,0,0)),(22,Z)])
# Pronation precedes a small parry follow-through. No hand/finger bones are invented.
for actor,sign in [('o',1),('n',-1)]:
    pose(actor,'forearm.L',[(24,Z),(31,(0,.045*sign,0)),(34,(0,.095*sign,0)),(37,(0,.12*sign,.025)),(39,(0,.04*sign,.015)),(43,Z)])
    pose(actor,'hand.L',[(24,Z),(31,(.035,.035*sign,0)),(35,(.075,.09*sign,0)),(38,(.03,.13*sign,-.035)),(43,Z)])
pose('o','clavicle.L',[(24,Z),(33,(0,0,-.035)),(37,(0,0,-.075)),(39,(0,0,-.045)),(43,Z)])
# Passing-leg breakdown, followed by a planted arrival at the existing frame 52 pin.
pose('n','thigh.R',[(44,Z),(47,(0,0,.23)),(49,(0,0,.38)),(51,(0,0,.12)),(52,Z),(55,Z)])
pose('n','shin.R',[(44,Z),(47,(0,0,-.34)),(49,(0,0,-.62)),(51,(0,0,-.17)),(52,Z),(55,Z)])
pose('n','foot.R',[(44,Z),(47,(.16,0,0)),(49,(.24,0,0)),(51,(.04,0,0)),(52,Z),(55,Z)])
pose('n','thigh.L',[(44,Z),(47,(0,0,-.08)),(49,(0,0,-.14)),(52,(0,0,-.045)),(55,Z)])
# Source phase values are sampled once at authored breakdown frames, not runtime-driven.
for bone in ('chest','clavicle.R','upper_arm.R'):
    pose('n',bone,[(68,Z)])
    pose('n',bone,[(71,Z),(75,Z),(78,Z),(79,Z)],delay=1)
    pose('n',bone,[(80,Z)])
for bone in ('thigh.L','shin.L','foot.L'):
    pose('n',bone,[(68,Z)])
    pose('n',bone,[(72,Z),(76,Z),(78,Z)],delay=2)
    pose('n',bone,[(80,Z)])
pose('n','hand.R',[(68,Z),(76,(.025,.04,-.015)),(79,(.035,.06,-.025)),(81,(.015,.04,0)),(82,(.015,.04,0)),(84,(.015,.04,0)),(86,Z)])
# Recoil begins in the body after the hold. Existing root motion is deliberately untouched.
pose('o','upper_arm.L',[(85,Z),(88,(.09,.02,.045)),(90,(.17,.03,.08)),(92,(.09,.025,.055)),(95,(.025,0,.02)),(98,Z)])
pose('o','upper_arm.R',[(85,Z),(88,(-.035,-.02,-.03)),(91,(-.075,-.04,-.055)),(94,(-.025,0,-.015)),(98,Z)])
pose('o','forearm.L',[(85,Z),(89,(.035,.055,-.05)),(92,(.025,.035,-.025)),(98,Z)])
pose('o','shin.L',[(85,Z),(89,(0,0,-.13)),(92,(0,0,-.07)),(98,Z)])
pose('o','pelvis',[(85,Z),(88,(.01,-.01,.02)),(92,(.015,0,-.015)),(95,(-.025,0,.02)),(98,Z)])
pose('o','chest',[(85,Z),(89,(-.025,.015,-.025)),(92,(-.04,.01,-.035)),(96,(.025,0,.02)),(98,Z)])

# Partner-relative target polish: a compact counter arc reaches the guard then
# sweeps out with the parry. These are authored knots, not collision responses.
def target_arc(name, keys):
    obj=bpy.data.objects[name]
    action=obj.animation_data.action
    values={f:[action.fcurves.find('location',index=i).evaluate(f) for i in range(3)] for f,_ in keys}
    for f,delta in keys:
        for i in range(3):
            c=action.fcurves.find('location',index=i)
            k=c.keyframe_points.insert(f,values[f][i]+delta[i])
            k.interpolation='CONSTANT' if f==82 else 'BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
    for c in action.fcurves: c.update()
    edit_log.append({'target':name,'keys':keys})
target_arc('HA_NARUTO_COUNTER_TARGET',[(30,Z),(33,(-.04,.025,.02)),(35,(-.079,.041,.034)),(36,(-.10,.06,.04)),(38,(-.05,.03,.01)),(42,Z)])
target_arc('HA_OMNI_PARRY_TARGET',[(32,Z),(35,Z),(37,(0,.025,.015)),(39,(0,.015,.005)),(43,Z)])
target_arc('HA_RASENGAN_TANGENT_TARGET',[(72,Z),(76,(.025,-.02,.015)),(79,(.015,-.01,.005)),(82,Z),(84,Z)])
# Static review framing: retain axes, pull back so loading feet remain visible.
from mathutils import Vector
for label,scale in [('side',8.4),('top',8.4)]:
    bpy.data.objects['HA_CAM_'+label].data.ortho_scale=scale
front=bpy.data.objects['HA_CAM_front-diagonal']
front.location=(-8,-2,3.2)
front.rotation_euler=(Vector((.05,.1,1.3))-front.location).to_track_quat('-Z','Y').to_euler()
front.data.lens=36
hero=bpy.data.objects['HA_CAM_three-quarter']
hero.location=(8.0,-2.0,3.8)
hero.rotation_euler=(Vector((.05,.1,1.3))-hero.location).to_track_quat('-Z','Y').to_euler()
hero.data.lens=36

# Restore outgoing recovery curves and incoming opening handles exactly. This
# prevents auto-handle recalculation from changing the protected 99–108 interval.
for tag,a in body.items():
    for c in a.fcurves:
        src = original[tag][(c.data_path,c.array_index)]
        for f in (1,8,98,108):
            old = next((k for k in src.keyframe_points if abs(k.co.x-f)<.001),None)
            new = next((k for k in c.keyframe_points if abs(k.co.x-f)<.001),None)
            if old and new:
                if f in (98,108):
                    new.co.y=old.co.y
                    new.handle_left_type='FREE'
                    new.handle_right_type='FREE'; new.handle_right=old.handle_right
                    if f==108:
                        new.handle_left_type='FREE';new.handle_left=old.handle_left
                if f in (1,8):
                    new.handle_left_type='FREE';new.handle_left=old.handle_left
                    if f==1:
                        new.handle_right_type='FREE';new.handle_right=old.handle_right
        c.update()
# Remove the unused immutable Action copies; retain all real body/root Actions.
for name in ('HA_BODY_OMNI.001','HA_BODY_NARUTO.001'):
    if a := bpy.data.actions.get(name): bpy.data.actions.remove(a)
assert root_before == {a.name:signature(a) for a in root_actions}, 'Root Actions changed'
end_error = max(abs(x-y) for t,a in body.items() for bx,ax in zip(end_before[t],samples(a)) for x,y in zip(bx,ax))

for t,a in body.items():
    for c,bx,ax in zip(a.fcurves,end_before[t],samples(a)):
        e=max(abs(x-y) for x,y in zip(bx,ax))
        if e>1e-6:
            print('END_ERROR',t,c.data_path,c.array_index,e)
            print('NEW',[(list(k.co),list(k.handle_left),list(k.handle_right),k.interpolation) for k in c.keyframe_points if k.co.x>=98])
            print('OLD',next(x for x in body_before[t] if x['path']==c.data_path and x['index']==c.array_index)['keys'][-2:])
assert end_error < 1e-6, f'Protected recovery changed: {end_error}'
scene=bpy.context.scene
scene.frame_start=1;scene.frame_end=108;scene.render.fps=30
scene['wws_polish_parent_scene_sha256']=sha(SOURCE/'scene.blend')
scene['wws_polish_method']='Sparse authored breakdowns on existing body Actions; no collision correction or root edits'
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'scene.blend'))
report={'classification':'animation-direction revision; not production certification',
        'source_scene':str(SOURCE/'scene.blend'),'source_scene_sha256':sha(SOURCE/'scene.blend'),
        'scene_sha256':sha(OUT/'scene.blend'),'canonical_events_sha256':sha(OUT/'source/events.json'),
        'parent_events_sha256':sha(SOURCE/'source/events.json'),'source_script_sha256':sha(__file__),
        'root_actions_unchanged':True,'root_action_signatures':root_before,
        'body_action_names':[a.name for a in body.values()], 'timeline':[1,108], 'fps':30,
        'protected_recovery_frames':[99,108],'protected_recovery_max_curve_error':end_error,
        'contact_hold_frames':[82,84], 'collision_solver_used':False,
        'edits':edit_log,'source_animation':'Existing hand-authored paired scene; no Mixamo motion used'}
(OUT/'review/action-provenance.json').write_text(json.dumps(report,indent=2))
print('POLISH_SAVED',OUT/'scene.blend','protected_end_error',end_error)
