"""Read-only clearance and authored-foot-pin diagnostics of the saved edit."""
from pathlib import Path
import sys, json, hashlib
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_combat_motion_lab as lab

out = lab.ROOT / 'outputs/combat_motion_lab_astra'
v2 = lab.load_v2()
v2.OUTPUT = out
bpy.context.scene.frame_set(365)
bpy.context.view_layer.update()
report = v2.collision_report(tuple(bpy.data.objects['fighter_b_IK_hand.R'].matrix_world.translation), [])
pins = []
for slot in ('fighter_a', 'fighter_b'):
    rig = bpy.data.objects[slot + '_ProductionRig']
    for bone in rig.pose.bones:
        for c in bone.constraints:
            if c.type != 'IK' or not c.name.startswith('ASTRA support'):
                continue
            errors = []
            for frame in range(1, 541):
                bpy.context.scene.frame_set(frame)
                bpy.context.view_layer.update()
                if c.influence > .999:
                    errors.append((frame, (rig.matrix_world @ bone.tail - c.target.matrix_world.translation).length))
            pins.append({'constraint': c.name, 'bone': bone.name, 'slot': slot,
                         'held_frames': len(errors), 'max_error': max((e for _, e in errors), default=0),
                         'worst_frame': max(errors, key=lambda e: e[1])[0] if errors else None})
report['scene_sha256'] = hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()
report['foot_pin_diagnostics'] = pins
root = bpy.data.objects['fighter_b_Rig'].animation_data.action
expected = [270, 278, 285, 294, 303, 310, 316, 324, 332, 340, 350]
actual = [round(k.co.x) for c in root.fcurves if c.data_path == 'location' and c.array_index == 1
          for k in c.keyframe_points if 270 <= k.co.x <= 350]
assert actual == expected, f'Stale root impulse keys: {actual}'
report['authored_root_keys'] = actual
report['source_events_unchanged'] = (out/'source/events.json').read_bytes() == (lab.ROOT/'outputs/combat_motion_lab/source/events.json').read_bytes()
(out / 'review/collision_report.json').write_text(json.dumps(report, indent=2))
print(json.dumps({'issues': report['unintentional_issue_count'], 'worst': report['worst_unintentional'], 'pins': pins}, indent=2))
