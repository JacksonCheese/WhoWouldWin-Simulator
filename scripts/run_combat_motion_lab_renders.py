"""Run the five fast review renders in bounded, resumable Blender sessions."""
from __future__ import annotations
import argparse, subprocess, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs/combat_motion_lab"
BLENDER=Path("/Applications/Blender.app/Contents/MacOS/Blender")
VIEWS=("side","three-quarter","front-diagonal","top-debug","cinematic-test")


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--view",choices=[*VIEWS,"all"],default="all");parser.add_argument("--force",action="store_true");parser.add_argument("--blender",type=Path,default=BLENDER);args=parser.parse_args()
    views=VIEWS if args.view=="all" else (args.view,)
    logs=OUT/"review/render-logs";logs.mkdir(parents=True,exist_ok=True)
    for view in views:
        for start in range(1,541,90):
            end=min(540,start+89)
            missing=[f for f in range(start,end+1) if not (OUT/f"renders/{view}/frames/{f:04d}.png").exists()]
            if not args.force and not missing:
                continue
            command=[str(args.blender),"-b",str(OUT/"scene.blend"),"--python-exit-code","1","--python",str(ROOT/"scripts/render_combat_motion_lab.py"),"--","--view",view,"--start",str(start),"--end",str(end)]
            if args.force:command.append("--force")
            log=logs/f"{view}-{start:04d}.log"
            with log.open("w") as handle:
                result=subprocess.run(command,cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT)
            if result.returncode:raise RuntimeError(f"{view} {start}-{end} failed; inspect {log}")
            print(f"{view}: {end}/540",flush=True)
    print("MOTION_LAB_ALL_RENDERS_COMPLETE",flush=True)


if __name__=="__main__":main()
