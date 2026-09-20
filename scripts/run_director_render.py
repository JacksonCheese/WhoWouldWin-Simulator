"""Render in bounded Blender sessions; recover isolated Metal stalls.

All scene features and sample settings are retained. Only owned child processes
are stopped. Saved PNGs are resumed only when scene/render hashes match.
"""
import argparse, json, subprocess, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/first_production_fight_astra_final'
BLENDER='/Applications/Blender.app/Contents/MacOS/Blender'


def main():
    p=argparse.ArgumentParser();p.add_argument('--quality',action='store_true');p.add_argument('--force',action='store_true');args=p.parse_args()
    label='quality-preview' if args.quality else 'preview'
    folder=OUT/'renders'/label/'frames'
    if args.force and folder.exists():
        folder.rename(folder.with_name('frames_previous_'+str(time.time_ns())))
    folder.mkdir(parents=True,exist_ok=True)
    logs=OUT/'review/render-logs';logs.mkdir(parents=True,exist_ok=True)
    history=[]
    for start in range(1,541,24):
        end=min(540,start+23)
        for attempt in range(3):
            log=logs/f'{label}-{start:04d}-attempt{attempt+1}.log'
            cmd=[BLENDER,'-b',str(OUT/'scene.blend'),'--python-exit-code','1','--python',str(ROOT/'scripts/render_director_final.py'),
                 '--','--start',str(start),'--end',str(end)]
            if args.quality:cmd+=['--quality']
            if args.force and attempt==0:cmd+=['--force']
            with log.open('w') as handle:
                child=subprocess.Popen(cmd,stdout=handle,stderr=subprocess.STDOUT,cwd=ROOT)
                last_size=0;last_progress=time.monotonic();stalled=False
                while child.poll() is None:
                    time.sleep(2)
                    size=log.stat().st_size
                    if size!=last_size:last_size=size;last_progress=time.monotonic()
                    if time.monotonic()-last_progress>90:
                        stalled=True;child.terminate()
                        try:child.wait(timeout=10)
                        except subprocess.TimeoutExpired:child.kill();child.wait()
                        break
                result=child.wait()
            history.append({'start':start,'end':end,'attempt':attempt+1,'returncode':result,'stalled':stalled,'log':str(log.relative_to(OUT))})
            (OUT/'review'/f'{label}-render-sessions.json').write_text(json.dumps(history,indent=2))
            missing=[f for f in range(start,end+1) if not (folder/f'{f:04d}.png').exists()]
            if result==0 and not missing:break
            print(f'Retrying {label} {start}-{end}: return {result}, missing {len(missing)}, stall {stalled}',flush=True)
        else:raise RuntimeError(f'Render failed after 3 sessions for frames {start}-{end}; inspect {log}')
        print(f'{label}: {end}/540 source frames complete',flush=True)
    print('RENDER_COMPLETE',label,flush=True)


if __name__=='__main__':main()
