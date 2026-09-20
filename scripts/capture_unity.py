"""Capture deterministic Unity frames, synthesize an event-aligned sound track, encode MP4."""
import argparse
import json
from pathlib import Path
import subprocess
import wave
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
UNITY_PROJECT=ROOT/"unity/WhoWouldWinVisual"
DEFAULT_UNITY=Path("/Applications/Unity/Hub/Editor/6000.5.8f1/Unity.app/Contents/MacOS/Unity")
DEFAULT_PLAYER=UNITY_PROJECT/"Builds/WhoWouldWinCinematic.app/Contents/MacOS/WhoWouldWin Cinematic"
SOUNDS={"Finisher":"ko","HeavyHit":"heavy","MeleeHit":"punch","BlockImpact":"block","DashPast":"dash","ProjectileCast":"projectile","Transformation":"transform","BeamCast":"projectile","Clash":"block","Charge":"charge","Teleport":"dash","Flight":"dash","SuccessfulDodge":"dash","GroundImpact":"heavy"}


def soundtrack(replay,output,duration,start=0):
    rate=22050
    mix=np.zeros(int(duration*rate),dtype=np.float64)
    cache={}
    for cue in replay["cues"]:
        key="charge" if cue["kind"]=="AnticipateAttack" and cue["vfx"] in {"energy","vortex"} else SOUNDS.get(cue["kind"])
        if cue["kind"]=="HeavyHit" and cue["vfx"] in {"vortex","shockwave"}:key="explosion"
        if not key:continue
        if key not in cache:
            path=UNITY_PROJECT/"Assets/Resources/Audio"/f"{key}.wav"
            with wave.open(str(path),"rb") as handle:
                if handle.getframerate()!=rate or handle.getnchannels()!=1 or handle.getsampwidth()!=2:
                    raise ValueError("Offline sound hooks currently require mono 22,050 Hz PCM16 WAV files")
                cache[key]=np.frombuffer(handle.readframes(handle.getnframes()),dtype='<i2').astype(float)/32768
        sample=cache[key];position=round((cue["start"]-start)*rate)
        source_offset=max(0,-position);destination=max(0,position)
        length=min(len(sample)-source_offset,len(mix)-destination)
        if length>0:mix[destination:destination+length]+=sample[source_offset:source_offset+length]*(.35+cue["intensity"]*.45)
    pcm=(np.tanh(mix)*.85*32767).astype('<i2')
    with wave.open(str(output),"wb") as handle:
        handle.setnchannels(1);handle.setsampwidth(2);handle.setframerate(rate);handle.writeframes(pcm.tobytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True,help="Output .mp4")
    parser.add_argument("--frames-dir",type=Path)
    parser.add_argument("--unity",type=Path,default=DEFAULT_UNITY)
    parser.add_argument("--player",type=Path,default=DEFAULT_PLAYER)
    parser.add_argument("--build",action="store_true")
    parser.add_argument("--width",type=int,default=1080)
    parser.add_argument("--height",type=int,default=1920)
    parser.add_argument("--fps",type=int,default=60)
    parser.add_argument("--frames",type=int,help="Limit frames for visual QA")
    parser.add_argument("--start",type=float,default=0)
    parser.add_argument("--hide-hud",action="store_true")
    parser.add_argument("--frames-only",action="store_true")
    args=parser.parse_args()
    if not (64 <= args.width <= 4096 and 64 <= args.height <= 4096 and 1 <= args.fps <= 120):
        parser.error("Dimensions must be 64–4096 and fps 1–120")
    if args.width % 2 or args.height % 2:
        parser.error("MP4 capture dimensions must be even")
    if args.start < 0 or (args.frames is not None and args.frames < 1):
        parser.error("Start must be nonnegative and frame count positive")
    args.output=args.output.resolve();args.output.parent.mkdir(parents=True,exist_ok=True)
    frames=(args.frames_dir or args.output.with_suffix("")).resolve();frames.mkdir(parents=True,exist_ok=True)
    if args.build or not args.player.exists():
        print("Building Unity player…",flush=True)
        subprocess.run([str(args.unity),"-batchmode","-nographics","-projectPath",str(UNITY_PROJECT),"-executeMethod","WhoWouldWin.Editor.ProjectBuilder.BuildMac","-quit","-logFile",str(ROOT/"reports/unity-build.log")],check=True)
    command=[str(args.player),"-replay",str(args.replay.resolve()),"-capture-dir",str(frames),"-capture-width",str(args.width),"-capture-height",str(args.height),"-capture-fps",str(args.fps),"-capture-start",str(args.start),"-quit-after-capture","-logFile",str(frames/"player.log")]
    if args.frames:command += ["-capture-frames",str(args.frames)]
    if args.hide_hud:command += ["-hide-hud"]
    print(f"Capturing {args.width}×{args.height} at {args.fps} fps → {frames}",flush=True)
    if any(frames.glob("frame_*.png")) or (frames/"capture.json").exists():
        raise SystemExit(f"Capture directory already contains frames: {frames}. Choose a new --frames-dir to avoid mixing captures.")
    # Fail quickly on a player startup exception or stalled capture, retaining its log.
    with subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT) as player:
        last_count=-1;last_progress=time.monotonic()
        while player.poll() is None:
            count=sum(1 for _ in frames.glob("frame_*.png"))
            if count!=last_count:last_count=count;last_progress=time.monotonic()
            log=frames/"player.log"
            if log.exists() and "Exception:" in log.read_text(errors="replace"):
                player.terminate();player.wait(timeout=15)
                raise RuntimeError(f"Unity capture failed; inspect {log}")
            if time.monotonic()-last_progress>120:
                player.terminate();player.wait(timeout=15)
                raise TimeoutError(f"No capture progress for 120 seconds; inspect {log}")
            time.sleep(.5)
        if player.returncode:raise RuntimeError(f"Unity exited {player.returncode}; inspect {frames/'player.log'}")
    manifest=json.loads((frames/"capture.json").read_text())
    if manifest["frames"]<1:raise RuntimeError("Unity produced no frames")
    replay=json.loads(args.replay.read_text());audio=frames/"soundtrack.wav"
    soundtrack(replay,audio,manifest["frames"]/args.fps,args.start)
    if args.frames_only:
        print(f"Saved frames, capture manifest and soundtrack to {frames}")
        return
    try:
        import imageio_ffmpeg
    except ImportError:
        raise SystemExit("Frames/audio saved. To encode MP4: pip install -e '.[video]' and run scripts/encode_capture.py")
    encode(imageio_ffmpeg.get_ffmpeg_exe(),frames,args.output,args.fps)
    print(f"Saved {args.output}; source winner={manifest['finalOutcome']['winner']}; complete={manifest['complete']}")


def encode(ffmpeg,frames,output,fps):
    subprocess.run([ffmpeg,"-y","-hide_banner","-loglevel","warning","-framerate",str(fps),"-i",str(frames/"frame_%05d.png"),"-i",str(frames/"soundtrack.wav"),"-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p","-r",str(fps),"-c:a","aac","-b:a","96k","-movflags","+faststart","-shortest",str(output)],check=True)


if __name__=="__main__":main()
