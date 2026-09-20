"""Encode the directing pass with the same editorial timing as the source lab."""
from pathlib import Path
import sys, json
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assemble_combat_motion_lab as assembly

assembly.OUT = assembly.ROOT / 'outputs/combat_motion_lab_astra'
assembly.main()
out = assembly.OUT
frames = list(range(268, 439))
target = out / 'close-exchange.mp4'
assembly.encode(out/'renders/three-quarter/frames', frames, target)
reader = assembly.imageio_ffmpeg.read_frames(str(target))
meta = next(reader)
count = sum(1 for _ in reader)
assert count == 171 and meta['size'] == (360, 640) and meta['fps'] == 30
path = out/'review/delivery-provenance.json'
data = json.loads(path.read_text())
data['media'].append({'view': 'close-exchange', 'path': target.name, 'sha256': assembly.digest(target),
                      'frames': count, 'duration_seconds': count/30, 'resolution': [360,640]})
data['editorial_source_frame_map'] = assembly.mapping()
data['close_exchange_source_frames'] = frames
data['renderer_wrapper_sha256'] = assembly.digest(Path(__file__).with_name('render_motion_lab_astra.py'))
data['assembler_sha256'] = assembly.digest(Path(__file__))
path.write_text(json.dumps(data, indent=2))
