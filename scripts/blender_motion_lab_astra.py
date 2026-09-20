"""Sequence-specific animator edit of the preserved Motion Lab; run in Blender.

Existing evaluated Actions provide the poses. This edit bakes their overlap,
re-times body chains, adds authored offsets and short production-rig foot pins.
It does not create a replacement animation or combat architecture.
"""
from pathlib import Path
import bpy, math, json, hashlib, sys
from mathutils import Vector, Euler, Quaternion
sys.path.insert(0,str(Path(__file__).resolve().parent))
import blender_combat_motion_lab as lab
import render_combat_motion_lab as rendering

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'outputs/combat_motion_lab'
OUT=ROOT/'outputs/combat_motion_lab_astra'
S=bpy.context.scene

def smooth(t):
    t=max(0.,min(1.,t));return t*t*(3-2*t)

def envelope(f,a,b,c,d):
    return smooth((f-a)/max(1,b-a))*(1-smooth((f-c)/max(1,d-c)))

def lerp_keys(keys,f):
    if f<=keys[0][0]:return keys[0][1]
    if f>=keys[-1][0]:return keys[-1][1]
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if a<=f<=b:
            t=smooth((f-a)/(b-a));return x*(1-t)+y*t

def sample():
    cache={}
    for slot in ('fighter_a','fighter_b'):
        r=bpy.data.objects[slot+'_Rig'];cache[slot]={}
        for f in range(1,541):
            S.frame_set(f);bpy.context.view_layer.update()
            cache[slot][f]={b.name:b.rotation_euler.to_quaternion().copy() for b in r.pose.bones}
    return cache

def cached(cache,bone,f):
    f=max(1.,min(540.,f));a=int(f);b=min(540,a+1)
    return cache[a][bone].slerp(cache[b][bone],f-a)

def warp(f,slot):
    if slot=='fighter_b':
        points=[(1,1),(55,55),(61,65),(67,73),(75,81),(90,90),
                (132,132),(140,140),(146,153),(159,165),(175,175),
                (268,268),(278,278),(286,293),(300,304),(308,313),
                (316,320),(324,326),(333,335),(342,342),
                (351,351),(358,361),(365,365),(367,365),(371,371),(382,382),(540,540)]
    else:
        points=[(1,1),(42,42),(49,49),(55,62),(69,74),(87,87),
                (101,101),(112,120),(136,136),(145,145),(268,268),
                (279,283),(289,294),(305,306),(316,316),(350,350),
                (357,355),(362,357),(365,360),(367,360),(371,367),
                (378,381),(397,397),(418,418),(435,438),(450,451),(476,476),(502,502),(540,540)]
    for (a,x),(b,y) in zip(points,points[1:]):
        if a<=f<=b:return x+(y-x)*(f-a)/(b-a)
    return f

def direct_body(cache,slot):
    rig=bpy.data.objects[slot+'_Rig'];original=rig.animation_data.action
    rig.animation_data.action=original.copy();rig.animation_data.action.name='ASTRA_'+original.name
    for track in rig.animation_data.nla_tracks:track.mute=True
    action=bpy.data.actions.new('ASTRA_'+slot+'_ContinuousBody')
    action['edit_classification']='SEQUENCE-SPECIFIC; baked from existing evaluated ML Actions'
    # Quaternion curves prevent Euler wrap from creating an accidental long spin.
    for bone in rig.pose.bones:
        curves=[action.fcurves.new(bone.path_from_id('rotation_quaternion'),index=i,action_group=bone.name) for i in range(4)]
        previous=None;values=[]
        for f in range(1,541):
            time=warp(f,slot)
            active=envelope(f,38,48,500,522)
            # The pelvis initiates; ribcage, shoulder, forearm and wrist follow.
            delay={'pelvis':-1.0,'spine':0.,'chest':1.,'clavicle.L':1.5,'clavicle.R':1.5,
                   'upper_arm.L':2.,'upper_arm.R':2.,'forearm.L':2.5,'forearm.R':2.5,
                   'hand.L':3.,'hand.R':3.,'head':2.}.get(bone.name,0.)*active
            # Protect canonical contact: phase alignment is exact at impact.
            protect=envelope(f,360,364,368,376)
            delay*=1-protect
            q=cached(cache,bone.name,time-delay)
            if slot=='fighter_a':
                # Reuse the existing powered-travel silhouette during pursuit,
                # rather than stretching an 18-frame turn over four seconds.
                pursuit=envelope(f,175,193,233,261)
                q=q.slerp(cached(cache,bone.name,63+min(10,max(0,f-193))*.2),pursuit*.85)
            # A narrow quaternion filter bridges NLA boundaries without washing
            # out the fast acceleration and contact portion of a strike.
            smoothing=.18*(1-protect)
            q=q.slerp(cached(cache,bone.name,time-delay-2).slerp(cached(cache,bone.name,time-delay+2),.5),smoothing)
            e=q.to_euler('XYZ');off=Vector((0,0,0))
            if bone.name in ('pelvis','spine','chest'):
                # Reduce stacked waist bending; preserve total shoulder reach
                # through chest/clavicle rather than doubling three hinges.
                e.y*= {'pelvis':.78,'spine':.78,'chest':.84}[bone.name]
                if slot=='fighter_b':
                    load=envelope(f,128,138,140,147)+envelope(f,342,350,353,361)
                    turn=envelope(f,296,304,311,321)+envelope(f,346,355,365,378)
                    off.z+=turn*{'pelvis':-.10,'spine':-.075,'chest':-.035}[bone.name]
                    off.y+=load*{'pelvis':-.05,'spine':.045,'chest':-.035}[bone.name]
                    settle=envelope(f,156,163,166,181)
                    off.y+=settle*{'pelvis':.025,'spine':.12,'chest':.075}[bone.name]
                else:
                    bank=envelope(f,62,70,79,95)+.8*envelope(f,431,441,450,469)
                    off.x+=bank*{'pelvis':.055,'spine':.11,'chest':.14}[bone.name]
                    recoil=envelope(f,365,369,374,388)
                    off.y-=recoil*{'pelvis':.05,'spine':.13,'chest':.22}[bone.name]
            if bone.name.startswith('clavicle'):
                side=1 if bone.name.endswith('R') else -1
                drive=(envelope(f,277,286,292,309) if slot=='fighter_a' else envelope(f,298,308,317,328)+envelope(f,349,359,368,383))
                off.x+=.065*drive;off.z-=side*.13*drive;off.y+=side*.045*drive
            if bone.name.startswith(('forearm','hand')):
                side=1 if bone.name.endswith('R') else -1
                drive=envelope(f,274,286,292,309) if slot=='fighter_a' else envelope(f,296,308,316,328)+envelope(f,344,358,367,382)
                off.y+=side*.12*drive*(1-protect)
                if bone.name.startswith('hand'):off.x-=.075*drive
            if slot=='fighter_b' and bone.name=='head':
                off.z+=.10*envelope(f,278,286,292,304)
                off.y-=.08*envelope(f,350,358,365,380)
            if slot=='fighter_b' and f>=390:
                # The recovered guard keeps living after the launch: weight and
                # breath settle through the chain without translating the feet.
                settle=envelope(f,390,406,520,540)
                phase=(f-390)*.055
                if bone.name=='pelvis':off.y+=settle*.025*math.sin(phase)
                elif bone.name=='spine':off.x+=settle*.035*math.sin(phase+.5)
                elif bone.name=='chest':off.x+=settle*.05*math.sin(phase+.9)
                elif bone.name=='head':off.x-=settle*.025*math.sin(phase+.9)
                elif bone.name.startswith('upper_arm'):
                    side=1 if bone.name.endswith('R') else -1
                    off.z+=side*settle*.035*math.sin(phase+.7)
            if bone.name=='upper_arm.L':
                # Keep the recovering guard out of the opponent's striking lane.
                off.z+=(-.15*envelope(f,278,283,289,299) if slot=='fighter_b'
                        else .15*envelope(f,359,364,372,382))
            if slot=='fighter_a' and bone.name.startswith(('thigh','shin','foot','upper_arm','forearm')):
                side=1 if bone.name.endswith('R') else -1
                air=envelope(f,50,62,84,105)+envelope(f,375,387,467,493)
                phase=f*(.065 if f<110 else .048)+side*.9
                off.x+=air*(.065 if bone.name.startswith(('upper_arm','forearm')) else .14)*math.sin(phase)
                off.z+=air*side*.055*math.sin(phase*.7+.6)
            if slot=='fighter_b' and bone.name.startswith('foot'):
                side=1 if bone.name.endswith('R') else -1
                push=envelope(f,134,141,144,152)+envelope(f,350,358,361,371)
                off.x+=side*.14*push
            q=Euler(tuple(Vector(e)+off),'XYZ').to_quaternion()
            if previous and previous.dot(q)<0:q.negate()
            previous=q.copy();values.append(q)
        for i,curve in enumerate(curves):
            curve.keyframe_points.add(540)
            curve.keyframe_points.foreach_set('co',[v for f,q in enumerate(values,1) for v in (f,q[i])])
            for k in curve.keyframe_points:k.interpolation='LINEAR'
        bone.rotation_mode='QUATERNION'
    track=rig.animation_data.nla_tracks.new();track.name='ASTRA_SEQUENCE_BODY'
    strip=track.strips.new(action.name,1,action);strip.extrapolation='HOLD';strip.blend_type='REPLACE'
    return action

def smooth_root(slot):
    rig=bpy.data.objects[slot+'_Rig'];action=rig.animation_data.action
    # Remove isolated collision-correction impulses, retain their mean clearance
    # as a broad authored outside arc across the entire exchange.
    if slot=='fighter_b':
        anchors={f:None for f in (270,278,285,294,303,310,316,324,332,340,350)}
        for f in anchors:
            S.frame_set(f);anchors[f]=rig.location.copy()
        outside=(-.3,-.85,-1.50,-1.48,-1.40,-1.18,-.88,-1.0,-1.36,-1.18,-.86)
        for curve in action.fcurves:
            if curve.data_path=='location':
                # Remove backwards: Blender RNA point references shift when a
                # preceding point is deleted, so forward deletion skips keys.
                for k in reversed(list(curve.keyframe_points)):
                    if 270<=k.co.x<=350:curve.keyframe_points.remove(k)
                curve.update()
        for (f,loc),y in zip(anchors.items(),outside):
            rig.location=loc;rig.location.y=y
            rig.keyframe_insert('location',frame=f)
        for curve in action.fcurves:
            if curve.data_path=='location':
                for k in curve.keyframe_points:
                    if 270<=k.co.x<=350:
                        k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
    else:
        # Brief recovery, explosive pursuit, then braking. Endpoints and action
        # order are preserved; these are direct sequence curve edits.
        timing=[(145,145),(166,158),(189,166),(204,173),(216,196),(230,228),(246,252),(260,263),(268,268)]
        samples=[]
        for target,source in timing:
            S.frame_set(source);bpy.context.view_layer.update()
            samples.append((target,rig.location.copy(),rig.rotation_euler.copy()))
        for curve in action.fcurves:
            if curve.data_path in ('location','rotation_euler'):
                for k in reversed(list(curve.keyframe_points)):
                    if 145<=k.co.x<=268:curve.keyframe_points.remove(k)
                curve.update()
        for frame,position,rotation in samples:
            rig.location=position;rig.rotation_euler=rotation
            rig.keyframe_insert('location',frame=frame);rig.keyframe_insert('rotation_euler',frame=frame)
        for curve in action.fcurves:
            if curve.data_path=='location':
                for k in curve.keyframe_points:
                    if 145<=k.co.x<=268:
                        k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
    for curve in action.fcurves:
        if curve.data_path=='rotation_euler':
            previous=None
            for k in curve.keyframe_points:
                if curve.array_index==2 and previous is not None:
                    while k.co.y-previous>math.pi:k.co.y-=math.tau
                    while k.co.y-previous< -math.pi:k.co.y+=math.tau
                previous=k.co.y
                if k.interpolation!='CONSTANT':
                    k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'

def foot_pins(slot):
    """Short authored support intervals, corrected on the evaluated target rig.

    Pins are per-shot controls, not a generalized locomotion solver. Each targets
    an ankle and copies a fixed foot orientation; influence eases at release.
    """
    rig=bpy.data.objects[slot+'_ProductionRig'];records=[]
    windows=([(8,36,'L'),(36,48,'R'),(270,280,'L'),(310,320,'R'),(330,340,'L')]
             if slot=='fighter_a' else
             [(8,50,'L'),(53,60,'R'),(100,109,'L'),(129,139,'R'),(163,174,'L'),
              (180,225,'L'),(229,237,'R'),(280,288,'L'),(296,304,'R'),(307,315,'L'),
              (326,334,'R'),(343,354,'R'),(361,369,'L'),(389,405,'L'),
              (421,435,'R'),(450,465,'L'),(478,490,'R'),(505,529,'L')])
    collection=bpy.data.collections.new(slot+'_ASTRA_FOOT_CONTROLS');S.collection.children.link(collection)
    for idx,(a,b,side) in enumerate(windows):
        shin=rig.pose.bones['LowerLeg_'+side];foot=rig.pose.bones['Foot_'+side]
        S.frame_set(a);bpy.context.view_layer.update()
        target=bpy.data.objects.new(f'ASTRA_{slot}_plant_{idx:02d}',None);collection.objects.link(target)
        target.location=rig.matrix_world@shin.tail
        target.rotation_mode='QUATERNION';target.rotation_quaternion=(rig.matrix_world@foot.matrix).to_quaternion()
        # Keep the existing anatomical foot elevation; no forced flat-ground
        # target that would introduce an unrelated leg stretch.
        ik=shin.constraints.new('IK');ik.name=f'ASTRA support {a}-{b}';ik.target=target;ik.chain_count=2;ik.use_stretch=False
        rotation=foot.constraints.new('COPY_ROTATION');rotation.name=f'ASTRA sole {a}-{b}';rotation.target=target
        for c in (ik,rotation):
            for f,v in ((1,0),(a-3,0),(a,1),(b,1),(b+4,0),(540,0)):
                c.influence=v;c.keyframe_insert('influence',frame=max(1,f))
        # End support before root travel makes the fixed ankle unreachable.
        # Releasing into a step is preferable to an overstretched locked leg.
        end=b
        for f in range(a,b+1):
            S.frame_set(f);bpy.context.view_layer.update()
            if (rig.matrix_world@shin.tail-target.location).length>.025:
                end=max(a,f-2);break
        if end!=b:
            for c in (ik,rotation):
                for f in (b,b+4):c.keyframe_delete('influence',frame=f)
                for f,v in ((end,1),(end+2,0)):
                    c.influence=v;c.keyframe_insert('influence',frame=f)
            b=end
        records.append({'fighter':slot,'side':side,'frames':[a,b],'target':list(target.location),'classification':'SEQUENCE-SPECIFIC'})
    return records

def guard_arcs():
    """Direct a compact chamber/re-chamber instead of the old overhead windmill."""
    rig=bpy.data.objects['fighter_b_ProductionRig'];enemy=bpy.data.objects['fighter_a_ProductionRig']
    collection=bpy.data.collections.new('ASTRA_GUARD_CONTROLS');S.collection.children.link(collection)
    control=bpy.data.objects.new('ASTRA_Naruto_compact_guard',None);collection.objects.link(control)
    positions={}
    for f in range(270,347):
        S.frame_set(f);bpy.context.view_layer.update()
        chest=rig.matrix_world@rig.pose.bones['SpineUpper'].head
        other=enemy.matrix_world@enemy.pose.bones['SpineUpper'].head
        direction=other-chest;direction.z=0;direction.normalize()
        side=Vector((direction.y,-direction.x,0))
        positions[f]=chest+direction*.43+side*.25+Vector((0,0,.25))
    for f,p in positions.items():
        control.location=p;control.keyframe_insert('location',frame=f)
    ik=rig.pose.bones['LowerArm_R'].constraints.new('IK');ik.name='ASTRA compact guard';ik.chain_count=2;ik.target=control;ik.use_stretch=False
    for f,v in ((1,0),(270,0),(280,1),(300,1),(307,0),(321,0),(327,1),(339,1),(347,0),(540,0)):
        ik.influence=v;ik.keyframe_insert('influence',frame=f)

def clean_rasengan_arc(v2):
    """Replace inherited per-frame solver noise with one readable contact arc."""
    control=bpy.data.objects['fighter_b_IK_hand.R']
    omni=bpy.data.objects['fighter_a_ProductionRig']
    naruto=bpy.data.objects['fighter_b_Rig']
    S.frame_set(365);bpy.context.view_layer.update()
    contact=control.matrix_world.translation.copy()
    chest=v2.capsule_for(omni,'omniman','chest')
    center=chest.a.lerp(chest.b,.5)
    outward=Vector((naruto.location.x-center.x,naruto.location.y-center.y,0))
    outward.normalize()
    action=control.animation_data.action
    for curve in action.fcurves:
        if curve.data_path=='location':
            for key in reversed(list(curve.keyframe_points)):
                if 348<=key.co.x<=382:curve.keyframe_points.remove(key)
            curve.update()
    path=((348,1.08,-.46),(354,.72,-.34),(358,.44,-.25),(362,.20,-.12),
          (365,0,0),(368,0,0),(371,0,0),(374,.34,-.07),(379,.72,-.24),(382,.96,-.42))
    for frame,distance,z in path:
        control.location=contact+outward*distance+Vector((0,0,z))
        control.keyframe_insert('location',frame=frame)
    for curve in action.fcurves:
        if curve.data_path=='location':
            for key in curve.keyframe_points:
                if 348<=key.co.x<=382:
                    key.interpolation='BEZIER';key.handle_left_type=key.handle_right_type='AUTO_CLAMPED'
    # Let the authored shoulder/elbow arc lead the entry. Contact IK ramps only
    # in the final four frames, avoiding a straight IK pull through the torso.
    constraint=bpy.data.objects['fighter_b_Rig'].pose.bones['forearm.R'].constraints['Procedural contact hand.R']
    influence_action=constraint.id_data.animation_data.action
    path_id=constraint.path_from_id('influence')
    for curve in influence_action.fcurves:
        if curve.data_path==path_id:
            for key in reversed(list(curve.keyframe_points)):
                if 348<=key.co.x<=375:curve.keyframe_points.remove(key)
            curve.update()
    for frame,value in ((348,0),(354,.05),(358,.08),(361,.10),(363,.12),(364,.18),
                        (365,1),(371,1),(373,.8),(375,.15)):
        constraint.influence=value;constraint.keyframe_insert('influence',frame=frame)
    return tuple(contact)

def review_cameras():
    # Fixed 3/4 now covers the whole central entry; no moving/zooming camera.
    cam=bpy.data.objects['ML_CAM_three-quarter'];cam.data.lens=46
    lab.look_at(cam,(-.65,0,1.55))
    cam=bpy.data.objects['ML_CAM_front-diagonal'];cam.data.lens=43
    lab.look_at(cam,(-.65,0,1.55))
    # Side camera uses orthographic projection to make foot-height comparison
    # unambiguous. Full geography remains visible in the top view.
    cam=bpy.data.objects['ML_CAM_side'];cam.location=(-.6,-15,2.4)
    lab.look_at(cam,(-.6,0,1.5));cam.data.type='ORTHO';cam.data.ortho_scale=7

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ('source','review','renders'):(OUT/name).mkdir(exist_ok=True)
    (OUT/'source/events.json').write_bytes((SOURCE/'source/events.json').read_bytes())
    data=sample();actions=[];pins=[]
    for slot in ('fighter_a','fighter_b'):
        actions.append(direct_body(data[slot],slot).name);smooth_root(slot)
    for slot in ('fighter_a','fighter_b'):pins+=foot_pins(slot)
    guard_arcs()
    # Body sequencing changes the evaluated chest and shoulder surfaces. Refit
    # the existing V2 contact target only after those edits are final so the
    # hand approaches the surface and does not enter the head/chest early.
    v2=lab.load_v2();v2.OUTPUT=OUT
    v2.refine_rasengan_tangent()
    surface=clean_rasengan_arc(v2)
    review_cameras()
    # Overlay paths must come from the revised evaluated animation.
    overlay=bpy.data.collections['WWS_MOTION_OVERLAYS']
    for obj in list(overlay.objects):bpy.data.objects.remove(obj,do_unlink=True)
    lab.add_trajectory_overlays(overlay)
    rendering.set_mode('motion_debug')
    # Keep the saved scene clean when opened interactively, as well as rendered.
    S.render.engine='BLENDER_WORKBENCH';S.frame_set(316)
    S['astra_motion_source_sha256']=lab.digest(SOURCE/'scene.blend')
    S['astra_motion_builder_sha256']=lab.digest(Path(__file__))
    S['astra_motion_gate']='UNAPPROVED — render review required'
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'scene.blend'))
    (OUT/'review/edit-manifest.json').write_text(json.dumps({'source_sha256':lab.digest(SOURCE/'scene.blend'),
      'scene_sha256':lab.digest(OUT/'scene.blend'),'builder_sha256':lab.digest(Path(__file__)),
      'events_sha256':lab.digest(OUT/'source/events.json'),'actions':actions,'foot_pins':pins,
      'rasengan_surface_contact_world':surface,
      'classification':'Sequence-specific direct animation edit; original NLA tracks retained muted'},indent=2))
    print('ASTRA_MOTION_SAVED',OUT/'scene.blend')

if __name__=='__main__':main()
