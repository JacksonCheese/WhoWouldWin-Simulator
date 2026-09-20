"""Encode a previously captured image sequence without rendering it again."""
import argparse
import json
from pathlib import Path
import imageio_ffmpeg
from capture_unity import encode, soundtrack

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("frames",type=Path)
parser.add_argument("--output",type=Path,required=True)
args=parser.parse_args()
manifest=json.loads((args.frames/"capture.json").read_text())
if not (args.frames/"soundtrack.wav").exists():
    soundtrack(json.loads(Path(manifest["sourceReplay"]).read_text()),args.frames/"soundtrack.wav",manifest["frames"]/manifest["fps"],manifest["capturedStart"])
args.output.parent.mkdir(parents=True,exist_ok=True)
encode(imageio_ffmpeg.get_ffmpeg_exe(),args.frames,args.output,manifest["fps"])
