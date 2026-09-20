"""Deterministic editorial trims and review sheets for the director render."""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path
import imageio_ffmpeg
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/first_production_fight_astra_final'
# Contact/exchange frames are retained 1:1. Compress only travel/setup/aftermath.
EDIT=[(1,41,32),(42,61,20),(62,87,26),(88,131,30),(132,169,32),
      (170,228,40),(229,278,40),(279,341,63),(342,381,40),(382,438,57),
      (439,500,50),(501,540,26)]


def mapping():
    return [round(a+i*(b-a)/(n-1)) for a,b,n in EDIT for i in range(n)]


def encode(folder: Path, frames: list[int], target: Path):
    sequence=target.parent/(target.stem+'-edit-frames')
    sequence.mkdir(parents=True,exist_ok=True)
    for i,f in enumerate(frames):
        src=folder/f'{f:04d}.png'
        if not src.exists():raise FileNotFoundError(src)
        dest=sequence/f'{i+1:04d}.png'
        if dest.is_symlink():dest.unlink()
        dest.symlink_to(src.resolve())
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-framerate','30','-i',str(sequence/'%04d.png'),
                    '-frames:v',str(len(frames)),'-c:v','libx264','-preset','fast','-crf','18',
                    '-pix_fmt','yuv420p','-movflags','+faststart',str(target)],check=True,capture_output=True)


def sheet(folder, frames, target, cols=6):
    w,h=180,320
    out=Image.new('RGB',(w*cols,((len(frames)+cols-1)//cols)*(h+20)),(18,20,25))
    draw=ImageDraw.Draw(out)
    for i,f in enumerate(frames):
        img=Image.open(folder/f'{f:04d}.png').convert('RGB').resize((w,h))
        x=i%cols*w;y=i//cols*(h+20)
        out.paste(img,(x,y));draw.text((x+5,y+h+3),f'frame {f}',fill='white')
    out.save(target)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--quality',action='store_true');args=parser.parse_args()
    label='quality-preview' if args.quality else 'preview'
    folder=OUT/'renders'/label/'frames'
    frames=mapping()
    encode(folder,frames,folder.parent/'fight.mp4')
    encode(folder,list(range(342,411)),OUT/'review'/('hero-impact.mp4' if args.quality else 'hero-impact-fast.mp4'))
    sheet(folder,[16,56,69,88,146,196,256,286,303,316,332,354,360,365,368,371,381,406,436,466,526],OUT/'review'/f'{label}-contact-sheet.jpg')
    for start in range(1,541,90):
        sheet(folder,list(range(start,min(start+90,541),5)),OUT/'review'/f'{label}-temporal-{start:03d}.jpg')
    (OUT/'review/edit-decision-list.json').write_text(json.dumps({'fps':30,'source_frames':540,'output_frames':len(frames),
        'duration_seconds':len(frames)/30,'segments':[{'source_in':a,'source_out':b,'output_frames':n} for a,b,n in EDIT],
        'output_to_source_frames':frames,'contact_frames_retimed':False},indent=2))
    # Preserve the existing sound hooks, with explicit source/editorial timing.
    # No audio is generated or mixed before visual approval.
    cues=json.loads((ROOT/'outputs/first_production_fight_v2/review/sound-cues.json').read_text())
    for cue in cues['cues']:
        source_frame=cue['frame']
        if cue['cue'] in {'concrete_break','glass_break'}:source_frame-=28
        output_index=min(range(len(frames)),key=lambda i:abs(frames[i]-source_frame))
        cue['source_frame']=source_frame
        cue['frame']=output_index+1
        cue['time_seconds']=round(output_index/30,5)
    cues['timing_basis']='director edit; source_frame preserves Blender timeline'
    (OUT/'review/sound-cues.json').write_text(json.dumps(cues,indent=2))
    print(f'{label}: {len(frames)} frames, {len(frames)/30:.2f}s')


if __name__=='__main__':main()
