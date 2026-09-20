"""Resume-safe renders from the saved director scene, without rebuilding it."""
import bpy
from pathlib import Path
import sys, hashlib, json
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/first_production_fight_astra_final'
scene=bpy.context.scene
scene.render.resolution_percentage=100
scene.render.fps=30
proxies=bpy.data.collections.get('WWS_COLLISION_PROXIES')
if proxies:proxies.hide_render=True
quality='--quality' in sys.argv
scene.render.engine='BLENDER_EEVEE_NEXT' if quality else 'BLENDER_WORKBENCH'
scene.render.resolution_x=720 if quality else 360
scene.render.resolution_y=1280 if quality else 640
scene.display.shading.light='STUDIO'
scene.display.shading.studio_light='rim.sl'
scene.display.shading.color_type='MATERIAL'
scene.display.shading.show_shadows=True
scene.display.shading.show_cavity=True
scene.render.image_settings.file_format='PNG'
folder=OUT/('renders/quality-preview/frames' if quality else 'renders/preview/frames')
folder.mkdir(parents=True,exist_ok=True)
if '--stills' in sys.argv:
    frames=[16,56,69,88,146,196,256,286,303,316,332,354,360,365,368,371,381,406,436,466,526]
    if '--frames' in sys.argv:frames=[int(f) for f in sys.argv[sys.argv.index('--frames')+1].split(',')]
    folder=OUT/('review/quality-stills' if quality else 'review/director-stills')
    folder.mkdir(parents=True,exist_ok=True)
else:
    start=int(sys.argv[sys.argv.index('--start')+1]) if '--start' in sys.argv else 1
    end=int(sys.argv[sys.argv.index('--end')+1]) if '--end' in sys.argv else 540
    frames=range(start,end+1)
manifest={'scene_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),
          'renderer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'scene_path':bpy.data.filepath,'engine':scene.render.engine,
          'resolution':[scene.render.resolution_x,scene.render.resolution_y],
          'samples':scene.eevee.taa_render_samples if quality else None,'fps':30,
          'started_utc':datetime.now(timezone.utc).isoformat()}
record=folder/'render-provenance.json'
if record.exists() and '--force' not in sys.argv:
    previous=json.loads(record.read_text())
    for field in ['scene_sha256','renderer_sha256','engine','resolution','samples']:
        if previous.get(field)!=manifest[field]:raise RuntimeError('Render revision changed: '+field+'. Use --force to regenerate.')
record.write_text(json.dumps(manifest,indent=2))
pending=[f for f in frames if '--force' in sys.argv or not (folder/f'{f:04d}.png').exists()]
if '--stills' not in sys.argv and pending and pending==list(range(pending[0],pending[-1]+1)):
    # Keep Blender's render context alive within each bounded contiguous batch.
    scene.frame_start=pending[0];scene.frame_end=pending[-1]
    scene.render.filepath=str(folder)+'/'
    bpy.ops.render.render(animation=True)
else:
    for frame in pending:
        path=folder/f'{frame:04d}.png'
        scene.frame_set(frame)
        scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        print('DIRECTOR_FRAME',frame,flush=True)
print('DIRECTOR_RENDER_COMPLETE',flush=True)
