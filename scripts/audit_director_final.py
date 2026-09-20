"""Audit the saved scene and critical evaluated meshes; never certify aesthetics."""
import bpy, hashlib, importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/first_production_fight_astra_final'
scene=bpy.context.scene
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('director_audit',ROOT/'scripts/blender_director_final.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
v2=module.load_v2()
scene.frame_set(365)
report=v2.collision_report(tuple(bpy.data.objects['fighter_b_IK_hand.R'].location),[])
mesh=v2.mesh_level_report()
# Reuse the existing mesh audit without writing into the certified V2 directory.
script=(ROOT/'scripts/audit_first_production_fight_v2_hand_meshes.py').read_text()
script=script.replace('outputs/first_production_fight_v2/review/hand_mesh_clearance_report.json',
                      'outputs/first_production_fight_astra_final/review/hand_mesh_clearance_report.json')
exec(compile(script,'director_hand_mesh_audit','exec'),{'__file__':str(ROOT/'scripts/audit_first_production_fight_v2_hand_meshes.py')})
source=ROOT/'outputs/first_production_fight_v2'
payload={'scene_sha256':digest(OUT/'scene.blend'),
    'director_source_matches_saved_scene':digest(ROOT/'scripts/blender_director_final.py')==scene['wws_director_script_sha256'],
    'certified_source_scene_unchanged':digest(source/'scene.blend')==scene['wws_director_source_sha256'],
    'events_unchanged':digest(source/'source/events.json')==digest(OUT/'source/events.json'),
    'source_event_sha256':digest(OUT/'source/events.json'),
    'frames_collision_validated':report['frames_evaluated'],
    'unsupported_proxy_issues':report['unintentional_issue_count'],
    'normal_speed_human_viewing_certified':False,
    'note':'Geometry and source provenance checks do not certify visual quality.'}
(OUT/'review/saved-scene-audit.json').write_text(json.dumps(payload,indent=2))
print('DIRECTOR_SAVED_SCENE_AUDIT',json.dumps(payload))
