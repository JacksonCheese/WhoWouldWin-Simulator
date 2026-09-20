from pathlib import Path
import argparse,bpy,sys
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/combat_motion_lab_production_skin_sole_binding';CAMS={'shot1':'SKINTEST_CAM_AttackSlip','shot2':'SKINTEST_CAM_RasenganEntry','shot3':'SKINTEST_CAM_Recoil','foot':'SKINBIND_CAM_Foot'}
p=argparse.ArgumentParser();p.add_argument('--shot',choices=CAMS,required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True);p.add_argument('--tier',choices=('clean','quality','foot'),required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);s=bpy.context.scene;s.camera=bpy.data.objects[CAMS[a.shot]]
for m in s.timeline_markers:m.camera=s.camera
s.frame_start=a.start;s.frame_end=a.end;s.render.fps=30;s.render.image_settings.file_format='PNG';s.render.resolution_percentage=100
if a.tier=='clean':s.render.engine='BLENDER_WORKBENCH';s.display.shading.light='STUDIO';s.display.shading.studio_light='rim.sl';s.display.shading.color_type='MATERIAL';s.display.shading.show_shadows=True;s.display.shading.show_cavity=True;s.render.resolution_x,s.render.resolution_y=360,640;s.render.use_motion_blur=False
else:s.render.engine='BLENDER_EEVEE_NEXT';s.render.resolution_x,s.render.resolution_y=((720,1280) if a.tier=='quality' else (360,640));s.eevee.taa_render_samples=1;s.render.use_motion_blur=a.tier=='quality';s.render.motion_blur_shutter=.28
folder=OUT/'renders'/({'clean':'preview','quality':'quality-preview','foot':'foot-closeup'}[a.tier])/a.shot;folder.mkdir(parents=True,exist_ok=True);s.render.filepath=str(folder)+'/'
bpy.ops.render.render(animation=True);print('SOLE_BINDING_RENDERED',a.tier,a.shot,a.start,a.end)
