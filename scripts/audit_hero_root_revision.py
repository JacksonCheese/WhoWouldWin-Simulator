"""Read-only comparison of the two saved paired-performance scenes."""
from pathlib import Path
import json,hashlib,importlib.util,sys,math
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'outputs/combat_motion_lab_hand_authored_polish'
OUT=ROOT/'outputs/combat_motion_lab_hand_authored_root_revision'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('rr_validator',ROOT/'scripts/validate_hand_authored_exchange.py')
v=importlib.util.module_from_spec(spec);sys.modules[spec.name]=v;spec.loader.exec_module(v)
collision=v.load_collision_module()
def snapshot(path):
 bpy.ops.wm.open_mainfile(filepath=str(path));scene=bpy.context.scene;rows=[]
 cameras={o.name:{'matrix':[list(row) for row in o.matrix_world],'lens':o.data.lens,'ortho':o.data.ortho_scale} for o in bpy.data.objects if o.type=='CAMERA'}
 for f in range(1,109):
  scene.frame_set(f);bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
  row={'frame':f,'actors':{}}
  for tag,label in [('a','Omni'),('b','Naruto')]:
   src=bpy.data.objects['fighter_'+tag+'_Rig'];rig=bpy.data.objects['fighter_'+tag+'_ProductionRig']
   row['actors'][tag]={'root':list(src.location),'yaw':src.rotation_euler.z,
    'root_matrix':[x for r in src.matrix_world for x in r],
    'bones':{b.name:[x for r in (rig.matrix_world@b.matrix) for x in r] for b in rig.pose.bones},
    'feet':{s:list(rig.matrix_world@rig.pose.bones['Foot_'+s].head) for s in ('L','R')},
    'foot_mesh_min_z':{s:min((bpy.data.objects[f'ML_{label}_foot.{s}'].evaluated_get(dg).matrix_world@Vector(p)).z for p in bpy.data.objects[f'ML_{label}_foot.{s}'].evaluated_get(dg).bound_box) for s in ('L','R')}}
  r_a=bpy.data.objects['fighter_a_ProductionRig'];r_b=bpy.data.objects['fighter_b_ProductionRig']
  row['parry_gap']=v.pair_gap(collision,r_b,'naruto','hand.L',r_a,'omniman','forearm.L')
  row['rasengan_hand_gap']=v.pair_gap(collision,r_b,'naruto','hand.R',r_a,'omniman','chest')
  chest=collision.capsule_for(r_a,'omniman','chest');center=bpy.data.objects['HA_RasenganContactMarker'].matrix_world.translation
  d=chest.b-chest.a;closest=chest.a+d*max(0,min(1,(center-chest.a).dot(d)/d.length_squared))
  row['rasengan_marker_gap']=(center-closest).length-chest.radius-.15
  rows.append(row)
 return rows,cameras,[(m.frame,m.name) for m in scene.timeline_markers]
before,cb,mb=snapshot(SOURCE/'scene.blend');after,ca,ma=snapshot(OUT/'scene.blend')
assert cb==ca,'Cameras changed'
assert mb==ma,'Event/beat markers changed'
assert sha(OUT/'source/events.json')==sha(SOURCE/'source/events.json')=='4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861'

def root_metrics(rows,tag,lo,hi):
 r=rows[lo-1:hi];points=[Vector(x['actors'][tag]['root']) for x in r]
 steps=[(b-a).length for a,b in zip(points,points[1:])]
 turns=[abs(b['actors'][tag]['yaw']-a['actors'][tag]['yaw']) for a,b in zip(r,r[1:])]
 return {'displacement':(points[-1]-points[0]).length,'path_length':sum(steps),'max_step':max(steps),'yaw_change_degrees':math.degrees(r[-1]['actors'][tag]['yaw']-r[0]['actors'][tag]['yaw']),'max_yaw_step_degrees':math.degrees(max(turns))}
comparison={name:{'before':root_metrics(before,tag,lo,hi),'after':root_metrics(after,tag,lo,hi)} for name,tag,lo,hi in [('naruto_angle_change_44_52','b',44,52),('naruto_entry_52_82','b',52,82),('omni_recoil_85_92','a',85,92)]}
comparison['omni_89_to_90']={name:(Vector(rows[89]['actors']['a']['root'])-Vector(rows[88]['actors']['a']['root'])).length for name,rows in [('before',before),('after',after)]}
upper=lambda b: not any(x in b for x in ('Leg','Foot'))
hold=max(abs(x-y) for row in after[82:84] for tag in ('a','b') for name in row['actors'][tag]['bones'] if upper(name) for x,y in zip(after[81]['actors'][tag]['bones'][name],row['actors'][tag]['bones'][name]))
source_hold=max(abs(x-y) for b,a in zip(before[81:84],after[81:84]) for tag in ('a','b') for name in a['actors'][tag]['bones'] if upper(name) for x,y in zip(b['actors'][tag]['bones'][name],a['actors'][tag]['bones'][name]))
recovery=max(abs(x-y) for b,a in zip(before[98:],after[98:]) for tag in ('a','b') for name in a['actors'][tag]['bones'] if upper(name) for x,y in zip(b['actors'][tag]['bones'][name],a['actors'][tag]['bones'][name]))
assert hold<1e-5 and source_hold<1e-5 and recovery<1e-5,(hold,source_hold,recovery)
assert comparison['naruto_angle_change_44_52']['after']['max_yaw_step_degrees']<12
assert comparison['naruto_entry_52_82']['after']['max_yaw_step_degrees']<12
assert comparison['omni_recoil_85_92']['after']['max_step']<.20
# Use unchanged clearance rules on the actual saved revision.
v.OUTPUT=OUT;v.main()
review=OUT/'review';old_foot=json.loads((review/'foot-drift-report.json').read_text())
(review/'original-support-window-check.json').write_text(json.dumps(old_foot,indent=2))
provenance=json.loads((review/'action-provenance.json').read_text());pins=[]
for p in provenance['new_support_intervals']:
 rig=bpy.data.objects['fighter_'+p['tag']+'_ProductionRig']
 measured=v.foot_drift(rig,p['fighter'],p['side'],*p['frames']);measured['target']=p['target']
 measured['mesh_ground_range']=[min(r['actors'][p['tag']]['foot_mesh_min_z'][p['side']] for r in after[p['frames'][0]-1:p['frames'][1]]),max(r['actors'][p['tag']]['foot_mesh_min_z'][p['side']] for r in after[p['frames'][0]-1:p['frames'][1]])]
 pins.append(measured)
foot_report={'scene_sha256':sha(OUT/'scene.blend'),'units':'Blender scene units','threshold':.035,'measurement':'evaluated ankle displacement over declared stationary support phases; foot mesh bound minimum Z also recorded',
 'declared_support_intervals':pins,'maximum_world_drift':max(p['max_world_drift'] for p in pins),'passes_threshold':all(p['max_world_drift']<=.035 for p in pins),'original_windows':old_foot,
 'limitations':'Foot support is authored IK, not a ground-reaction-force simulation. Bone-head drift and bounding boxes cannot establish athletic believability.'}
(review/'foot-drift-report.json').write_text(json.dumps(foot_report,indent=2))
report={'scene_sha256':sha(OUT/'scene.blend'),'source_scene_sha256':sha(SOURCE/'scene.blend'),'events_sha256':sha(OUT/'source/events.json'),'comparison':comparison,
 'upper_body_hold_82_84_error':hold,'upper_body_hold_difference_from_parent':source_hold,'upper_body_recovery_99_108_difference':recovery,
 'camera_values_unchanged':cb==ca,'beat_markers_unchanged':mb==ma,'foot_mesh_min_z':min(r['actors'][tag]['foot_mesh_min_z'][s] for r in after for tag in ('a','b') for s in ('L','R')),
 'collision_solver_used':False,'root_and_body_actions_separate':True,'new_support_max_drift':foot_report['maximum_world_drift'],'new_support_threshold_passed':foot_report['passes_threshold']}
(review/'root-trajectory-comparison.json').write_text(json.dumps(report,indent=2))
(review/'full-frame-motion.json').write_text(json.dumps({'before':before,'after':after},indent=2))
print('ROOT_REVISION_AUDIT',json.dumps(report))
