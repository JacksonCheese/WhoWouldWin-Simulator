"""Assemble motion-lab PNGs into 15.2-second H.264 review videos."""
from __future__ import annotations
import argparse,hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
import imageio_ffmpeg
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"outputs/combat_motion_lab"
VIEWS=("side","three-quarter","front-diagonal","top-debug","cinematic-test")
EDIT=[(1,41,32),(42,61,20),(62,87,26),(88,131,30),(132,169,32),(170,228,40),(229,278,40),(279,341,63),(342,381,40),(382,438,57),(439,500,50),(501,540,26)]

def mapping():return [round(a+i*(b-a)/(n-1)) for a,b,n in EDIT for i in range(n)]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def encode(folder,frames,target):
    sequence=target.parent/(target.stem+"-edit-frames");sequence.mkdir(parents=True,exist_ok=True)
    for i,frame in enumerate(frames,1):
        dest=sequence/f"{i:04d}.png";src=(folder/f"{frame:04d}.png").resolve()
        if dest.is_symlink():dest.unlink()
        if not dest.exists():dest.symlink_to(src)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),"-y","-framerate","30","-i",str(sequence/"%04d.png"),"-frames:v",str(len(frames)),"-c:v","libx264","-preset","fast","-crf","18","-pix_fmt","yuv420p","-movflags","+faststart",str(target)],check=True,capture_output=True)

def sheet(folder,target):
    frames=[42,48,56,69,78,106,138,152,196,256,286,294,303,316,332,350,362,365,368,371,397,418,448,476,526]
    w,h=144,256;cols=5;rows=5
    image=Image.new("RGB",(w*cols,(h+18)*rows),(18,20,24));draw=ImageDraw.Draw(image)
    for i,frame in enumerate(frames):
        item=Image.open(folder/f"{frame:04d}.png").convert("RGB").resize((w,h));x=i%cols*w;y=i//cols*(h+18)
        image.paste(item,(x,y));draw.text((x+4,y+h+2),f"f{frame}",fill="white")
    image.save(target)

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--view",choices=[*VIEWS,"all"],default="all");args=parser.parse_args()
    frames=mapping();media=[]
    views=VIEWS if args.view=="all" else (args.view,)
    for view in views:
        folder=OUT/f"renders/{view}/frames";target=OUT/f"{view}.mp4"
        missing=[f for f in range(1,541) if not (folder/f"{f:04d}.png").exists()]
        if missing:raise RuntimeError(f"{view} missing {len(missing)} frames")
        encode(folder,frames,target);sheet(folder,OUT/f"review/{view}-contact-sheet.jpg")
        reader=imageio_ffmpeg.read_frames(str(target));metadata=next(reader);count=sum(1 for _ in reader)
        if metadata["size"]!=(360,640) or metadata["fps"]!=30 or count!=456:raise RuntimeError((view,metadata,count))
        media.append({"view":view,"path":str(target.relative_to(OUT)),"sha256":digest(target),"frames":count,"duration_seconds":count/30,"resolution":[360,640]})
    payload={"verified_utc":datetime.now(timezone.utc).isoformat(),"scene_sha256":digest(OUT/"scene.blend"),"events_sha256":digest(OUT/"source/events.json"),"source_frames":540,"output_frames":456,"views":list(views),"media":media,"normal_speed_visual_approval":False}
    (OUT/"review/delivery-provenance.json").write_text(json.dumps(payload,indent=2))
    print(json.dumps(payload,indent=2))

if __name__=="__main__":main()
