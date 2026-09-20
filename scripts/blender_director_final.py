"""Shot-specific directing edits to a COPY of the certified V2 scene.

Run with Blender -b V2/scene.blend --python this_file. No simulator or asset
architecture changes. The existing Actions remain the animation source.
"""
from __future__ import annotations
import bpy
import hashlib
import importlib.util
import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'outputs/first_production_fight_v2'
OUTPUT = ROOT / 'outputs/first_production_fight_astra_final'
SCENE = bpy.context.scene
SCRIPT_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def load_v2():
    spec = importlib.util.spec_from_file_location('director_v2', ROOT/'scripts/blender_first_production_fight_v2.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.OUTPUT = OUTPUT
    module.base.OUTPUT = OUTPUT
    return module


def smooth(action):
    for curve in action.fcurves:
        for key in curve.keyframe_points:
            key.handle_left_type = key.handle_right_type = 'AUTO_CLAMPED'
            if key.interpolation != 'CONSTANT': key.interpolation = 'BEZIER'


def repair_nla(v2):
    """Repair actual strip data, not the NLA architecture. No bind-pose gaps."""
    ends = {'fighter_a_Rig':[45,105,149,270,314,360,438,502,540],
            'fighter_b_Rig':[58,95,136,175,238,284,352,398,540]}
    report=[]
    for name, desired in ends.items():
        rig=bpy.data.objects[name]
        for track,end in zip(rig.animation_data.nla_tracks,desired):
            s=track.strips[0]
            before=s.frame_end
            s.repeat=1.0
            s.scale=(end-s.frame_start)/(s.action_frame_end-s.action_frame_start)
            s.frame_end=end
            s.extrapolation='HOLD_FORWARD'
            s.blend_in=3 if s.frame_start>1 else 0
            s.blend_out=0
            report.append({'rig':name,'action':s.action.name,'start':s.frame_start,'old_end':before,'end':s.frame_end})
        smooth(rig.animation_data.action)
    (OUTPUT/'review/nla-repair.json').write_text(json.dumps(report,indent=2))


def polish_actions():
    """Phase-offset accents and restrained torso bends on existing native Actions."""
    for action in bpy.data.actions:
        if not action.name.startswith('WWS_CHAR_'): continue
        for curve in action.fcurves:
            if 'rotation_euler' not in curve.data_path: continue
            bone=curve.data_path.split('"')[1]
            scale=1.0
            if bone in {'pelvis','spine','chest'}:
                scale=.32 if 'impact_launch' in action.name else (.50 if 'rasengan_attack' in action.name else .70)
            if bone=='head': scale=.62
            for key in curve.keyframe_points:
                key.co.y*=scale
                # Small stagger in existing curves: hip impulse precedes chest/arm.
                if key.co.x not in action.frame_range:
                    lag={'pelvis':-.65,'spine':-.3,'chest':.25,'clavicle.R':.5}.get(bone,0)
                    key.co.x+=lag
            curve.update()
        smooth(action)


def arm_pose_edits():
    """Direct existing Action poses with target-based elbow/wrist placement.

    The rig adapter and runtime IK are untouched. These are authoring-time keys
    on native Actions, evaluated in the source rig's own coordinates.
    """
    for prefix in ['fighter_a','fighter_b']:
        rig=bpy.data.objects[prefix+'_Rig']
        root_action=rig.animation_data.action
        transform=rig.matrix_world.copy()
        tracks=[(t,t.mute) for t in rig.animation_data.nla_tracks]
        constraints=[(c,c.mute) for b in rig.pose.bones for c in b.constraints]
        for t,_ in tracks: t.mute=True
        for c,_ in constraints: c.mute=True
        rig.animation_data.action=None
        rig.matrix_world.identity()
        character='omniman' if prefix=='fighter_a' else 'naruto'
        for action in [a for a in bpy.data.actions if a.name.startswith('WWS_CHAR_'+character)]:
            # Keep attack/contact correction and named defensive hand paths intact.
            if any(n in action.name for n in ['rasengan_attack','melee_redirect','super_punch']): continue
            rig.animation_data.action=action
            frames=sorted({round(k.co.x) for c in action.fcurves for k in c.keyframe_points})
            for frame in frames:
                SCENE.frame_set(frame)
                rig.matrix_world.identity()
                bpy.context.view_layer.update()
                flight=any(n in action.name for n in ['flight_blitz','ninja_dash'])
                reaction=any(n in action.name for n in ['impact_launch','midair_recovery','airborne_turn'])
                charge='rasengan_charge' in action.name
                for side,sign in [('L',1),('R',-1)]:
                    upper=rig.pose.bones['upper_arm.'+side]
                    lower=rig.pose.bones['forearm.'+side]
                    chest=rig.pose.bones['chest'].matrix
                    shoulder=upper.head.copy()
                    # Author compact elbows, distinguish guarded versus trailing arms.
                    if flight:
                        elbow_offset=Vector((-.20,sign*.22,-.30))
                        wrist_offset=Vector((-.24,sign*.20,-.61))
                    elif reaction:
                        elbow_offset=Vector((-.12,sign*.25,-.22))
                        wrist_offset=Vector((.10,sign*.36,-.42))
                    elif charge and side=='R':
                        elbow_offset=Vector((.16,sign*.21,-.30))
                        wrist_offset=Vector((.54,sign*.18,-.18))
                    else:
                        elbow_offset=Vector((.10,sign*.14,-.35))
                        wrist_offset=Vector((.48,sign*.03,-.08))
                    # Offset in root coordinates: preserve existing torso rotation.
                    elbow=shoulder+elbow_offset
                    wrist=shoulder+wrist_offset
                    for bone,target in [(upper,elbow),(lower,wrist)]:
                        direction=(target-bone.head).normalized()
                        matrix=bone.matrix.copy()
                        delta=(bone.tail-bone.head).normalized().rotation_difference(direction)
                        matrix=delta.to_matrix().to_4x4()@matrix
                        matrix.translation=bone.head.copy()
                        bone.matrix=matrix
                        bone.rotation_mode='XYZ'
                        bone.keyframe_insert('rotation_euler',frame=frame)
                        bpy.context.view_layer.update()
            smooth(action)
        rig.animation_data.action=root_action
        rig.matrix_world=transform
        for t,m in tracks: t.mute=m
        for c,m in constraints: c.mute=m
    SCENE.frame_set(1)


def cape_deformation():
    """Replace only the rigid cape slab with a 9x13 authored deforming surface."""
    cape=bpy.data.objects['OmniMan_Cape']
    cape.location.x-=.14
    material=cape.data.materials[0]
    # Bone-parent local coordinates are inherited from the existing cape object.
    # Reuse its actual mesh extents to avoid assuming a different bone basis.
    old=[v.co.copy() for v in cape.data.vertices]
    bounds=[(min(p[i] for p in old),max(p[i] for p in old)) for i in range(3)]
    # Existing cube is local XYZ: thin X, width Y, length Z.
    width=bounds[1][1]-bounds[1][0]
    low,high=bounds[2]
    vertices=[]; faces=[]
    for row in range(13):
        t=row/12
        for col in range(9):
            u=col/8*2-1
            vertices.append((-.025-.06*t*t, u*width*.5*(.84+.16*t), high-(high-low)*t))
    for row in range(12):
        for col in range(8):
            a=row*9+col
            faces.append((a,a+1,a+10,a+9))
    mesh=bpy.data.meshes.new('Astra_Cape_SecondarySurface')
    mesh.from_pydata(vertices,[],faces);mesh.update()
    cape.data=mesh;mesh.materials.append(material)
    for modifier in list(cape.modifiers): cape.modifiers.remove(modifier)
    for p in mesh.polygons:p.use_smooth=True
    cape.shape_key_add(name='Basis')
    for name in ['Trail','Brake','BankLeft','BankRight']:
        key=cape.shape_key_add(name=name)
        for i,v in enumerate(key.data):
            t=(i//9)/12;u=(i%9)/8*2-1
            if name=='Trail':
                v.co.x-=.65*t*t
                v.co.z+=.40*t*t
                v.co.y+=.09*math.sin(t*7+u*2)*t
            elif name=='Brake':
                v.co.x-=.17*math.sin(t*math.pi)
                v.co.z+=.40*t
                v.co.y*=1-.25*t
            else:
                sign=1 if name=='BankLeft' else -1
                v.co.y+=sign*.30*t*t
                v.co.x-=.15*math.sin(t*8+u*3)*t
                v.co.z+=sign*u*.13*t
    for f,trail,brake,bank in [(1,0,0,0),(48,.1,0,0),(61,1,0,.5),(72,.8,.1,.8),(90,.2,.8,-.3),(130,.1,.15,0),(275,0,0,0),(365,.1,.2,-.3),(371,.1,.2,-.3),(386,1,0,.8),(417,.8,0,-1),(442,.4,.8,.6),(470,.7,.1,-.3),(540,.4,0,0)]:
        for n,value in [('Trail',trail),('Brake',brake),('BankLeft',max(bank,0)),('BankRight',max(-bank,0))]:
            key=cape.data.shape_keys.key_blocks[n];key.value=value;key.keyframe_insert('value',frame=f)
    # Remove board-like rotation/scaling extremes; shape deformation supplies lag.
    for c in cape.animation_data.action.fcurves:
        if c.data_path=='rotation_euler':
            for k in c.keyframe_points:k.co.y*=.22
        if c.data_path=='scale':
            for k in c.keyframe_points:k.co.y=1+(k.co.y-1)*.22
    sub=cape.modifiers.new('Secondary surface smoothing','SUBSURF');sub.levels=1
    solid=cape.modifiers.new('Cape thickness','SOLIDIFY');solid.thickness=.012


def energy_look(v2):
    root=bpy.data.objects['Rasengan_Control']
    # Disable opaque full torus cages. Fine partial curve wisps retain animation.
    for o in bpy.data.objects:
        if o.name.startswith('Rasengan_Swirl_') or o.name=='Rasengan_EnergyTrail':o.hide_render=True
    for name,color,strength,alpha in [('Rasengan_Core',(.008,.12,.85,1),1.8,.65),('Rasengan_HotCore',(.06,.40,1,1),2.6,1),('Rasengan_Swirl',(.015,.34,1,1),2.1,.58)]:
        mat=bpy.data.materials[name];mat.diffuse_color=(*color[:3],alpha)
        bs=mat.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Base Color'].default_value=color
        bs.inputs['Emission Color'].default_value=color
        bs.inputs['Emission Strength'].default_value=strength
        bs.inputs['Alpha'].default_value=alpha
        bs.inputs['Roughness'].default_value=.26
    bpy.data.objects['Rasengan_Core'].scale*=.72
    bpy.data.objects['Rasengan_HotCore'].scale*=.58
    for idx in range(7):
        curve=bpy.data.curves.new('ChakraWisp','CURVE');curve.dimensions='3D';curve.bevel_depth=.0055;curve.bevel_resolution=2
        spline=curve.splines.new('POLY');spline.points.add(39)
        r=.23+.012*idx
        for j,p in enumerate(spline.points):
            a=j/39*math.pi*1.45
            p.co=(r*math.cos(a),r*math.sin(a),.04*math.sin(a*3+idx),1)
        obj=bpy.data.objects.new('Astra_ChakraWisp_'+str(idx),curve);bpy.context.collection.objects.link(obj)
        obj.parent=root;curve.materials.append(bpy.data.materials['Rasengan_Swirl'])
        for f in [170,228,342,362,365,368,371,378,392]:
            obj.rotation_euler=(idx*.48+f*.013,idx*.85,f*(.15+idx*.018))
            obj.keyframe_insert('rotation_euler',frame=f)
    light=bpy.data.lights['Rasengan_Light']
    for c in light.animation_data.action.fcurves:
        if c.data_path=='energy':
            for k in c.keyframe_points:k.co.y*=.12
    for o in bpy.data.objects:
        if o.name.startswith('Rasengan_ImpactArc'):
            o.hide_render=True
    # Keep release energy localized; do not wash away contact silhouette.
    for c in root.animation_data.action.fcurves:
        if c.data_path=='scale':
            for k in c.keyframe_points:
                if k.co.x==378:k.co.y=.95
    if SCENE.use_nodes:
        for n in SCENE.node_tree.nodes:
            if n.type=='GLARE':
                n.threshold=2.0;n.mix=-.92
    SCENE.view_settings.view_transform='AgX'
    SCENE.view_settings.exposure=-.2
    # A shadowed directional key anchors the feet. Non-shadowing cinematic fill
    # and rim preserve dark-costume readability without extra competing shadows.
    for name in ['City_BlueFill','Hero_Rim','Rasengan_Light']:
        light=bpy.data.lights.get(name)
        if light:light.use_shadow=False
    fill=bpy.data.lights.get('City_BlueFill')
    if fill:
        fill.energy=1100
        fill.color=(.24,.40,.85)


def destruction_timing():
    """Move existing staged wall break to contact; dust trails the fragments."""
    for o in bpy.data.objects:
        if not o.animation_data or not o.animation_data.action:continue
        if o.name.startswith(('CrashWall_','WallDebris','WallDust','CrashBreach')):
            delay=5 if 'Dust' in o.name else 0
            for c in o.animation_data.action.fcurves:
                for k in c.keyframe_points:
                    if k.co.x>1:k.co.x-=28-delay
                c.update()
    for o in bpy.data.objects:
        if o.name.startswith('Awning_') and abs(o.location.x+10.5)<3 and o.location.y>0:
            # The awning spans the head-height breach: break it with the facade.
            o.hide_render=False;o.keyframe_insert('hide_render',frame=1)
            o.keyframe_insert('hide_render',frame=81)
            o.hide_render=True;o.keyframe_insert('hide_render',frame=82)


def face_exchange(v2):
    """Shot-specific yaw corrections: fighters face the actual line of action."""
    a=bpy.data.objects['fighter_a_Rig'];b=bpy.data.objects['fighter_b_Rig']
    keys=[]
    for f in [270,278,289,299,303,316,326,338,350,360,365,368,371,379]:
        SCENE.frame_set(f)
        angle=math.atan2(a.location.y-b.location.y,a.location.x-b.location.x)
        keys.append((f,angle))
    for f,angle in keys:
        SCENE.frame_set(f)
        for rig,yaw in [(a,angle+math.pi),(b,angle)]:
            rig.rotation_euler.z=yaw
            rig.keyframe_insert('rotation_euler',index=2,frame=f)
    # Keep the newly authored compact reaction arm. The older V2 Euler override
    # extended it back into Naruto's head during the newly phased release.


def power_flight():
    rig=bpy.data.objects['fighter_a_Rig']
    for f,tilt in [(42,0),(48,.18),(56,.95),(61,1.15),(65,1.18),(70,.76),(78,.15),(96,-.15),
                   (448,.15),(466,.48),(488,.72),(500,.68),(540,.64)]:
        SCENE.frame_set(f);rig.rotation_euler.y=tilt
        rig.keyframe_insert('rotation_euler',index=1,frame=f)
    action=bpy.data.actions['WWS_CHAR_omniman_flight_blitz']
    for c in action.fcurves:
        if c.data_path in ['pose.bones["spine"].rotation_euler','pose.bones["chest"].rotation_euler']:
            for k in c.keyframe_points:k.co.y*=.20


def hero_timing():
    mappings={
        'WWS_CHAR_omniman_impact_launch':[(357,1),(362,1),(365,4),(368,4),(371,7),(381,13),(412,20),(438,28)],
        'WWS_CHAR_naruto_rasengan_attack':[(342,1),(355,5),(362,9),(365,10),(368,10),(371,13),(380,19),(398,26)],
    }
    for name in ['fighter_a_Rig','fighter_b_Rig']:
        for track in bpy.data.objects[name].animation_data.nla_tracks:
            for s in track.strips:
                if s.action.name not in mappings:continue
                s.use_animated_time=True
                for f,value in mappings[s.action.name]:
                    s.strip_time=value;s.keyframe_insert('strip_time',frame=f)
                for c in s.fcurves:
                    for k in c.keyframe_points:
                        k.interpolation='LINEAR'


def hand_accents(v2):
    """Use the existing hand presets at the actual directed action times."""
    for side,keys in {
        'R':[(306,'RELAXED'),(312,'CLOSED_FIST'),(320,'CLOSED_FIST'),(330,'CUPPED'),(338,'CUPPED'),(371,'CUPPED')],
        'L':[(322,'CLOSED_FIST'),(328,'OPEN_PALM'),(338,'OPEN_PALM'),(347,'CLOSED_FIST')],
    }.items():
        prefix='naruto_'+side
        controls=v2.base_humanoid.HandControls(
            root=bpy.data.objects[prefix+'_HandControl'],palm=bpy.data.objects[prefix+'_Palm'],
            fingers=[bpy.data.objects[prefix+'_Finger_'+str(i)] for i in range(4)],
            thumb=bpy.data.objects[prefix+'_Thumb'])
        for frame,pose in keys:v2.base_humanoid.set_hand_pose(controls,pose,frame)
    (OUTPUT/'review/hand-direction.json').write_text(json.dumps({
        'counter':{'hand':'naruto.R','frames':[312,320],'preset':'CLOSED_FIST'},
        'guard_redirect':{'hand':'naruto.L','frames':[328,338],'preset':'OPEN_PALM'},
        'rasengan':{'hand':'naruto.R','frames':[338,371],'preset':'CUPPED'},
        'omniman':'existing CLOSED_FIST presets preserved'},indent=2))


def direct_surface_contact(v2):
    """Shot-specific hand-target keys follow the moving chest during entry.

    V2's fixed future impact point can intersect the earlier approach pose after
    the clip-range repair. Keep the same IK constraint and contact event window.
    """
    omni=bpy.data.objects['fighter_a_ProductionRig']
    naruto=bpy.data.objects['fighter_b_ProductionRig']
    root=bpy.data.objects['fighter_b_Rig']
    control=bpy.data.objects['fighter_b_IK_hand.R']
    ik=next(c for c in root.pose.bones['forearm.R'].constraints if c.type=='IK')
    # Preserve the earlier blocked body counter as a visible glove/guard contact.
    for frame in range(306,323):
        influence=min(1,max(0,(frame-312)/2),(322-frame)/6)
        SCENE.frame_set(frame);ik.influence=influence
        ik.keyframe_insert('influence',frame=frame)
        bpy.context.view_layer.update()
        cap=v2.capsule_for(omni,'omniman','forearm.L')
        center=cap.a.lerp(cap.b,.85)
        outward=Vector((root.location.x-center.x,root.location.y-center.y,0)).normalized()
        desired=center+outward*.23
        if influence>.4:
            for _ in range(8):
                hand=v2.capsule_for(naruto,'naruto','hand.R')
                error=desired-hand.b
                if error.length<.01:break
                control.location+=error*.60
                bpy.context.view_layer.update()
        control.keyframe_insert('location',frame=frame)
    for frame,influence in [(371,1),(373,.8),(375,.15),(376,0),(379,0)]:
        ik.influence=influence;ik.keyframe_insert('influence',frame=frame)
    surface_points={}
    for frame in range(348,380):
        SCENE.frame_set(frame);bpy.context.view_layer.update()
        cap=v2.capsule_for(omni,'omniman','chest')
        center=(cap.a+cap.b)*.5
        outward=Vector((root.location.x-center.x,root.location.y-center.y,0)).normalized()
        approach=max(0,(365-frame)/17)*.45 if frame<365 else max(0,(frame-371)/8)*.50
        # Shot-specific sternum ray on the actual evaluated skin. A capsule
        # radius alone left the smaller blue effect visibly floating off skin.
        body=bpy.data.objects['OmniMan_Body'].evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=body.to_mesh()
        tree=BVHTree.FromPolygons([body.matrix_world@v.co for v in mesh.vertices],[tuple(p.vertices) for p in mesh.polygons])
        body.to_mesh_clear()
        origin=center+Vector((0,0,.08))+outward*2
        point,normal,_,_=tree.ray_cast(origin,-outward,3)
        if point is None:point=center+outward*.30
        desired=point+outward*(.30+approach)
        surface_points[frame]=(point.copy(),outward.copy(),approach)
        for _ in range(5):
            hand=v2.capsule_for(naruto,'naruto','hand.R')
            error=desired-hand.b
            if error.length<.008:break
            control.location+=error*.75
            bpy.context.view_layer.update()
        control.keyframe_insert('location',frame=frame)
    energy=bpy.data.objects['Rasengan_Control']
    for c in energy.constraints:c.mute=True
    # The energy rides the cupped hand, rather than the wrist IK control.
    for frame in range(170,393):
        SCENE.frame_set(frame);bpy.context.view_layer.update()
        hand=v2.capsule_for(naruto,'naruto','hand.R')
        energy.location=hand.b+(hand.b-hand.a).normalized()*.06
        if 348<=frame<=371:
            point,outward,approach=surface_points[frame]
            energy.location=point+outward*(.145+approach)
        energy.keyframe_insert('location',frame=frame)
    (OUTPUT/'review/hero-surface-targets.json').write_text(json.dumps([
        {'frame':f,'skin_surface':list(p),'outward':list(n),'approach_offset':a,
         'energy_center_offset_at_contact':.145} for f,(p,n,a) in surface_points.items()],indent=2))
    SCENE.frame_set(365)
    return tuple(control.location)


def frame_cameras(v2):
    """Hand-chosen viewing directions with evaluated-body framing, baked per shot."""
    views=[(-1,-.24,.10),(1,-.5,.12),(1,-.35,.15),(-1,-.8,.16),(-1,-.25,.12),
           (1,-.28,.12),(1,-.35,.17),(1,-.65,.14),(1,-.65,.13),(-.6,-1,.13),(1,-1,.12),(-1,-.22,.10)]
    subjects=[['fighter_a','fighter_b'],['fighter_a'],['fighter_a','fighter_b'],['fighter_a'],['fighter_b'],['fighter_b'],
              ['fighter_a','fighter_b'],['fighter_a','fighter_b'],['fighter_a','fighter_b'],['fighter_a'],['fighter_a'],['fighter_a','fighter_b']]
    markers=sorted([m for m in SCENE.timeline_markers if m.camera],key=lambda m:m.frame)
    specs=[]
    SCENE.render.resolution_x=360;SCENE.render.resolution_y=640
    for idx,m in enumerate(markers):
        start=m.frame;end=markers[idx+1].frame-1 if idx+1<len(markers) else 540
        camera=m.camera;target=camera.constraints[0].target
        camera.animation_data_clear();target.animation_data_clear();camera.data.animation_data_clear()
        camera.data.lens=43 if idx in [5,7,8] else 38
        camera.data.clip_start=.06;camera.data.clip_end=300
        direction=Vector(views[idx]).normalized()
        for frame in range(start,end+1):
            SCENE.frame_set(frame);bpy.context.view_layer.update()
            points=[]
            for prefix in subjects[idx]:
                rig=bpy.data.objects[prefix+'_ProductionRig']
                roles=['Head','SpineUpper','Hips','Hand_L','Hand_R']
                if idx not in [5,7,8]:roles+=['Foot_L','Foot_R']
                for role in roles:
                    bone=rig.pose.bones[role]
                    points.extend([rig.matrix_world@bone.head,rig.matrix_world@bone.tail])
            low=Vector([min(p[j] for p in points) for j in range(3)])
            high=Vector([max(p[j] for p in points) for j in range(3)])
            center=(low+high)*.5
            center.z+=.08
            target.location=center
            distance=4.8
            for _ in range(50):
                camera.location=center+direction*distance
                # The modular storefronts begin beyond the sidewalk. Keep cameras
                # in the street rather than letting a framing fit enter a facade.
                camera.location.y=max(-4.7,min(4.7,camera.location.y))
                bpy.context.view_layer.update()
                proj=[world_to_camera_view(SCENE,camera,p) for p in points]
                if all(.13<p.x<.87 and .13<p.y<.85 and p.z>0 for p in proj):break
                distance*=1.045
            # Preserve a stable impact hold; directional impulse only after release.
            if idx==8:
                entry=min(1,max(0,(frame-354)/9))
                release=min(1,max(0,(frame-371)/10))
                camera.location=center+(camera.location-center)*(1-.18*entry+.13*release)
            if idx==8 and 372<=frame<=377:
                camera.location.z+=.06*math.sin((frame-371)*2.2)*(378-frame)/6
            camera.keyframe_insert('location',frame=frame);target.keyframe_insert('location',frame=frame)
        specs.append({'shot':m.name,'frames':[start,end],'view_direction':list(direction),'subjects':subjects[idx],'lens':camera.data.lens})
    (OUTPUT/'review/camera-direction.json').write_text(json.dumps(specs,indent=2))


def main():
    for p in ['review','renders/preview','renders/quality-preview']:(OUTPUT/p).mkdir(parents=True,exist_ok=True)
    for p in ['source','characters','environment']:
        if (SOURCE/p).exists():shutil.copytree(SOURCE/p,OUTPUT/p,dirs_exist_ok=True)
    v2=load_v2()
    repair_nla(v2);polish_actions();arm_pose_edits();face_exchange(v2);power_flight();hero_timing()
    hand_accents(v2)
    cape_deformation();energy_look(v2);destruction_timing()
    # The source system remains authoritative for contact/clearance.
    surface=v2.refine_rasengan_tangent()
    corrections=v2.apply_clearance_solver()
    surface=v2.refine_rasengan_tangent()
    surface=direct_surface_contact(v2)
    report=v2.collision_report(surface,corrections)
    frame_cameras(v2)
    SCENE['wws_director_source_sha256']=hashlib.sha256((SOURCE/'scene.blend').read_bytes()).hexdigest()
    SCENE['wws_director_script_sha256']=SCRIPT_SHA
    SCENE['wws_director_build_utc']=datetime.now(timezone.utc).isoformat()
    SCENE.render.engine='BLENDER_EEVEE_NEXT';SCENE.eevee.taa_render_samples=4
    SCENE.render.use_motion_blur=True;SCENE.render.motion_blur_shutter=.20
    SCENE.frame_start=1;SCENE.frame_end=540;SCENE.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT/'scene.blend'))
    print('DIRECTOR_BUILD_COMPLETE',report['unintentional_issue_count'])


if __name__=='__main__':main()
