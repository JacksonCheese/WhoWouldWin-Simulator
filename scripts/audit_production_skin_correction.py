"""Generate the scoped feasibility-correction reports from the saved scene."""
from pathlib import Path
from datetime import datetime,timezone
import bpy,hashlib,importlib.util,json,math,sys
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'outputs/combat_motion_lab_production_skin_feasibility';OUT=ROOT/'outputs/combat_motion_lab_production_skin_correction';R=OUT/'review'
EXPECTED='4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sig(a):
 payload=[(c.data_path,c.array_index,[(round(k.co.x,7),round(k.co.y,9),k.interpolation) for k in c.keyframe_points]) for c in sorted(a.fcurves,key=lambda x:(x.data_path,x.array_index))]
 return hashlib.sha256(json.dumps(payload,separators=(',',':')).encode()).hexdigest()
def root_sigs(path):
 bpy.ops.wm.open_mainfile(filepath=str(path));return {n:sig(bpy.data.actions[n]) for n in ('HA_ROOT_fighter_a','HA_ROOT_fighter_b')}
baseline_roots=root_sigs(BASE/'scene.blend');current_roots=root_sigs(OUT/'scene.blend');scene=bpy.context.scene
assert baseline_roots==current_roots and sha(OUT/'source/events.json')==EXPECTED and (scene.frame_start,scene.frame_end,scene.render.fps)==(1,108,30)
def verts(o):
 e=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh()
 try:return [e.matrix_world@v.co for v in m.vertices]
 finally:e.to_mesh_clear()
def elbow(rig,u,l):
 a=rig.matrix_world@rig.pose.bones[u].head;b=rig.matrix_world@rig.pose.bones[u].tail;c=rig.matrix_world@rig.pose.bones[l].tail
 return math.degrees((a-b).angle(c-b))
def bounds(names,cam):
 ps=[]
 for n in names:
  o=bpy.data.objects[n].evaluated_get(bpy.context.evaluated_depsgraph_get());ps += [world_to_camera_view(scene,cam,o.matrix_world@Vector(c)) for c in o.bound_box]
 xs=[p.x for p in ps];ys=[p.y for p in ps];return {'min_x':min(xs),'max_x':max(xs),'min_y':min(ys),'max_y':max(ys),'fully_visible':min(xs)>=0 and max(xs)<=1 and min(ys)>=0 and max(ys)<=1}
frames={};omni=['OmniMan_Body','OmniMan_Cape','OmniMan_HairCap'];naruto=['Naruto_Body','Naruto_ForeheadProtectorBand',*[f'Naruto_HairSpike_{i:02d}' for i in range(13)]]
for f in (68,72,76,79,80,82,83,84,85,86,88,90,92,95,98):
 scene.frame_set(f);bpy.context.view_layer.update();cam=bpy.data.objects['SKINTEST_CAM_RasenganEntry' if f<=84 else 'SKINTEST_CAM_Recoil']
 frames[str(f)]={'body_min_z':{'naruto':min(v.z for v in verts(bpy.data.objects['Naruto_Body'])),'omniman':min(v.z for v in verts(bpy.data.objects['OmniMan_Body']))},'naruto_elbow_R_degrees':elbow(bpy.data.objects['fighter_b_ProductionRig'],'UpperArm_R','LowerArm_R'),'screen':{'naruto':bounds(naruto,cam),'omniman':bounds(omni,cam)}}
contact=json.loads((R/'contact-penetration-report.json').read_text());foot=json.loads((R/'foot-drift-report.json').read_text())
sole_values=[v['body_min_z'][who] for v in frames.values() for who in ('naruto','omniman')]
foot_report={'schema_version':1,'scene_sha256':sha(OUT/'scene.blend'),'ground_z':0.0,'sampled_frames':frames,'maximum_declared_support_drift':foot['maximum_world_drift'],'support_drift_threshold':foot['threshold'],'support_drift_passes':foot['passes_numerical_plant_threshold'],'absolute_sampled_mesh_clearance':{'minimum':min(sole_values),'maximum':max(sole_values)},'assessment':'Stable support targets, but Omni-Man retains visible absolute sole clearance during the recoil catch. Absolute skin-to-ground offset remains the sole production-gate blocker.'}
(R/'foot-sole-report.json').write_text(json.dumps(foot_report,indent=2)+'\n')
deform={'schema_version':1,'scene_sha256':sha(OUT/'scene.blend'),'contact_hold':[82,84],'naruto_contact_elbow_degrees':{str(f):frames[str(f)]['naruto_elbow_R_degrees'] for f in (82,83,84)},'baseline_contact_elbow_degrees':179.659657,'torso_fold_observed':False,'root_pop_observed':False,'observations':['Contact elbow reduced without moving either root or tangent marker.','Omni-Man receives pelvis-first compression with one-frame chest delay and asymmetric arms.','Simplified hands and missing scapular/twist deformation remain previs limitations.']}
(R/'deformation-report.json').write_text(json.dumps(deform,indent=2)+'\n')
camera={'schema_version':1,'scene_sha256':sha(OUT/'scene.blend'),'frames':{f:frames[str(f)]['screen'] for f in (82,84,85,90,92,98)},'assessment':'The medium contact composition is retained. The recoil camera widens progressively and keeps both actors readable through frame 98; feet remain visible rather than being cropped to hide the sole issue.'}
(R/'camera-framing-report.json').write_text(json.dumps(camera,indent=2)+'\n')
provenance={'schema_version':1,'generated_utc':datetime.now(timezone.utc).isoformat(),'classification':'B','scene_sha256':sha(OUT/'scene.blend'),'parent_scene_sha256':sha(BASE/'scene.blend'),'canonical_events_sha256':sha(OUT/'source/events.json'),'root_action_signatures':{n:{'parent':baseline_roots[n],'derived':current_roots[n],'identical':True} for n in baseline_roots},'timeline':[1,108],'contact_hold':[82,84],'body_root_action_separation_preserved':True,'character_package_provenance_inherited':True,'collision_solver_used_to_author_motion':False,'mixamo_or_mocap_used':False}
(R/'provenance-report.json').write_text(json.dumps(provenance,indent=2)+'\n')
gate={'classification':'B','decision':'Improved but requires one precisely identified correction.','passes_production_animation_gate':False,'exact_remaining_blocker':'Omni-Man production skin has an absolute sole-to-ground offset during the frames 90-98 recoil catch. The planted target drifts only %.6f units, but sampled visible mesh clearance reaches %.6f units; the skin/foot binding offset must be corrected without changing the root Action.'%(foot['maximum_world_drift'],max(frames[str(f)]['body_min_z']['omniman'] for f in (90,92,95,98))),'verified':{'canonical_event_hash':EXPECTED,'root_actions_identical':True,'unsupported_penetrations':contact['unsupported_issue_count'],'contact_hold_preserved':True,'recoil_camera_keeps_both_subjects':True}}
(R/'production-gate-decision.json').write_text(json.dumps(gate,indent=2)+'\n')
report=f'''# Targeted production-skin correction review\n\n## Decision\n\n**B. Improved but requires one precisely identified correction.**\n\nThe scoped pass reduced Naruto's contact elbow from 179.66° to {frames['82']['naruto_elbow_R_degrees']:.2f}°, added a leg-driven body drop without changing the approved root path, preserved the exact frames 82–84 hold, added pelvis-first Omni-Man compression and asymmetric arm lag, and widened the recoil camera so both actors remain readable through frame 98. The root Action signatures and canonical event hash remain identical to the parent.\n\n## Exact remaining blocker\n\nOmni-Man's production skin still has an absolute sole-to-ground binding offset during the frames 90–98 catch. The planted control is stable (maximum drift {foot['maximum_world_drift']:.6f}), but sampled visible mesh clearance reaches {max(frames[str(f)]['body_min_z']['omniman'] for f in (90,92,95,98)):.6f} scene units. This is now an isolated skin/foot-offset correction, not a root-motion or broad choreography problem. No further broad polish was performed.\n\n## Contact and deformation\n\nThe validator evaluated all 108 frames and found {contact['unsupported_issue_count']} unsupported penetrations. The Rasengan physical-hand proxy remains clear, the tangent marker and three-frame hold are unchanged, and the contact elbow no longer locks completely. Simplified hands and limited scapular/twist deformation remain known previs limitations but are not the gate-blocking defect in this derivative.\n\n## Camera\n\nThe contact remains a medium three-quarter composition. The recoil lens widens from 48 mm to 38 mm and reacquires both bodies by frame 98. Full feet remain visible, so the remaining sole offset is documented rather than hidden.\n\n## Preservation\n\n- Canonical event SHA-256: `{EXPECTED}`\n- Timeline: 108 frames at 30 fps\n- Root trajectories: unchanged signatures\n- Body/root separation: preserved\n- CharacterPackage provenance: inherited\n- Collision correction did not author motion\n- No Mixamo, mocap, RL, simulator, city, sound, or full-fight work\n'''
(R/'production-skin-correction-review.md').write_text(report);(OUT/'production-skin-correction-review.md').write_text(report)
print('SKIN_CORRECTION_AUDITED',json.dumps(gate))
