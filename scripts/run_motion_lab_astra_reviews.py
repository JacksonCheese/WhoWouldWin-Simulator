"""Render all fixed/cinematic review angles of one immutable saved scene."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import argparse

root = Path(__file__).resolve().parents[1]
out = root/'outputs/combat_motion_lab_astra'
parser = argparse.ArgumentParser()
parser.add_argument('--blender', default='/Applications/Blender.app/Contents/MacOS/Blender')
args = parser.parse_args()

def render(view):
    with (out/f'review/render-{view}.log').open('w') as log:
        subprocess.run([args.blender, '-b', str(out/'scene.blend'), '--python-exit-code', '1',
                        '--python', str(root/'scripts/render_motion_lab_astra.py'), '--',
                        '--view', view, '--force'], stdout=log, stderr=subprocess.STDOUT, check=True)
    print('Rendered', view, flush=True)

with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(render, ('three-quarter','side','front-diagonal','cinematic-test','top-debug')))
