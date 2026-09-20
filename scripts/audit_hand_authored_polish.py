"""Read-only saved-scene regression and per-frame motion audit."""
from pathlib import Path
import json, hashlib, importlib.util, sys, csv
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/combat_motion_lab_hand_authored_polish'
SOURCE=ROOT/'outputs/combat_motion_lab_hand_authored_hero_exchange'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('ha_audit_validator',ROOT/'scripts/validate_hand_authored_exchange.py')
v=importlib.util.module_from_spec(spec);sys.modules[spec.name]=v;spec.loader.exec_module(v)
mathlib=v.load_collision_module()

def snapshot(path):
 bpy.ops.wm.open_mainfile(filepath=str(path))
 result=[]
 for f in range(1,109):
  bpy.context.scene.frame_set(f);bpy.context.view_layer.update()
  row={'frame':f,'actors':{}}
  for tag in ('a','b'):
   source=bpy.data.objects['fighter_'+tag+'_Rig'];r=bpy.data.objects['fighter_'+tag+'_ProductionRig']
   row['actors'][tag]={'root':list(source.location),'yaw':source.rotation_euler.z,
      'bones':{b.name:[x for vector in (r.matrix_world@b.matrix) for x in vector] for b in r.pose.bones},
      'feet':{s:list(r.matrix_world@r.pose.bones['Foot_'+s].head) for s in ('L','R')}}
  result.append(row)
 return result
before=snapshot(SOURCE/'scene.blend')
after=snapshot(OUT/'scene.blend')
root_error=max(abs(x-y) for b,a in zip(before,after) for tag in ('a','b') for x,y in zip(b['actors'][tag]['root']+[b['actors'][tag]['yaw']],a['actors'][tag]['root']+[a['actors'][tag]['yaw']]))
recovery_error=max(abs(x-y) for b,a in zip(before[98:],after[98:]) for tag in ('a','b') for bone in b['actors'][tag]['bones'] for x,y in zip(b['actors'][tag]['bones'][bone],a['actors'][tag]['bones'][bone]))
hold_error=max(abs(x-y) for a in after[82:84] for tag in ('a','b') for bone in a['actors'][tag]['bones'] for x,y in zip(after[81]['actors'][tag]['bones'][bone],a['actors'][tag]['bones'][bone]))
rows=[]
for f,record in enumerate(after,1):
 bpy.context.scene.frame_set(f);bpy.context.view_layer.update()
 r={t:bpy.data.objects['fighter_'+t+'_ProductionRig'] for t in ('a','b')}
 row={'frame':f,'time_seconds':(f-1)/30}
 for tag in ('a','b'):
  prev=after[max(0,f-2)]['actors'][tag];now=record['actors'][tag]
  row[tag+'_root_step']=(Vector(now['root'])-Vector(prev['root'])).length
  row[tag+'_yaw_step']=now['yaw']-prev['yaw']
  for side in ('L','R'):
   row[tag+'_'+side+'_ankle_z']=now['feet'][side][2]
   row[tag+'_'+side+'_foot_step']=(Vector(now['feet'][side])-Vector(prev['feet'][side])).length
 row['parry_surface_gap']=v.pair_gap(mathlib,r['b'],'naruto','hand.L',r['a'],'omniman','forearm.L')
 row['rasengan_hand_chest_gap']=v.pair_gap(mathlib,r['b'],'naruto','hand.R',r['a'],'omniman','chest')
 marker=bpy.data.objects['HA_RasenganContactMarker']
 center=marker.matrix_world.translation
 chest=mathlib.capsule_for(r['a'],'omniman','chest')
 delta=chest.b-chest.a
 nearest=chest.a+delta*max(0,min(1,(center-chest.a).dot(delta)/delta.length_squared))
 row['rasengan_marker_chest_gap']=(center-nearest).length-chest.radius-.15
 rows.append(row)
assert root_error==0
assert recovery_error<1e-5
upper_hold_error=max(abs(x-y) for a in after[82:84] for tag in ('a','b') for bone in a['actors'][tag]['bones'] if not any(n in bone for n in ('Leg','Foot')) for x,y in zip(after[81]['actors'][tag]['bones'][bone],a['actors'][tag]['bones'][bone]))
assert upper_hold_error<1e-5
baseline_hold_error=max(abs(x-y) for a in before[82:84] for tag in ('a','b') for bone in a['actors'][tag]['bones'] for x,y in zip(before[81]['actors'][tag]['bones'][bone],a['actors'][tag]['bones'][bone]))
assert hold_error <= baseline_hold_error + 1e-5

report={'scene_sha256':sha(OUT/'scene.blend'),'source_scene_sha256':sha(SOURCE/'scene.blend'),
 'events_unchanged':sha(OUT/'source/events.json')==sha(SOURCE/'source/events.json'),
 'canonical_events_sha256':sha(SOURCE/'source/events.json'),'all_108_root_samples_max_error':root_error,
 'evaluated_recovery_99_108_max_matrix_error':recovery_error,'evaluated_hold_82_84_max_matrix_error':hold_error,'baseline_hold_max_matrix_error':baseline_hold_error,'upper_body_hold_max_matrix_error':upper_hold_error,
 'collision_solver_used':False,'foot_measurement_limit':'Bone-head positions are not sole-contact or support-force measurements. Short pin windows do not certify the angle-change transition.',
 'naruto_angle_change_root_displacement_44_52':(Vector(after[51]['actors']['b']['root'])-Vector(after[43]['actors']['b']['root'])).length,
 'naruto_angle_change_unwrapped_yaw_44_52':after[51]['actors']['b']['yaw']-after[43]['actors']['b']['yaw'],
 'omni_root_jump_89_90':rows[89]['a_root_step'],
 'rasengan_hold_marker_surface_gaps':[rows[f-1]['rasengan_marker_chest_gap'] for f in (82,83,84)],
 'rig_bones':{t:list(r[t].pose.bones.keys()) for t in ('a','b')},
 'limitations':'Capsules and a sphere-marker measure clearance only; no mesh-intersection or continuous-playback artistic certification is implied.'}
(OUT/'review/saved-scene-regression.json').write_text(json.dumps(report,indent=2))
(OUT/'review/full-frame-motion.json').write_text(json.dumps(rows,indent=2))
with (OUT/'review/full-frame-motion.csv').open('w') as h:
 w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
v.OUTPUT=OUT;v.main()
print('SAVED_SCENE_AUDIT',json.dumps({k:x for k,x in report.items() if k!='rig_bones'}))
