"""FFmpeg assembly and local timing tracks. This module has no combat logic."""

from pathlib import Path
import json
import math
import wave
import numpy as np
from .providers import run_ffmpeg
from .schemas import ShotList


def timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def timing_tracks(project: Path, shot_list: ShotList) -> tuple[Path, Path]:
    (project / "audio").mkdir(exist_ok=True)
    (project / "final").mkdir(exist_ok=True)
    captions = []
    narration = []
    effects = []
    cursor = 0.0
    for i, shot in enumerate(shot_list.shots):
        end = cursor + shot.duration_seconds
        captions.append(
            f"{i+1}\n{timestamp(cursor)} --> {timestamp(end)}\n{shot.narration_hint}\n"
        )
        narration.append(
            {
                "shot_id": shot.shot_id,
                "start": cursor,
                "end": end,
                "text": shot.narration_hint,
                "audio_generated": False,
            }
        )
        effects.extend(
            {
                "shot_id": shot.shot_id,
                "time": cursor + cue.offset_seconds,
                "cue": cue.cue,
                "authority": "presentation",
            }
            for cue in shot.audio_cues
        )
        cursor = end
    srt = project / "final/captions.srt"
    srt.write_text("\n".join(captions), encoding="utf-8")
    (project / "audio/timing.json").write_text(
        json.dumps({"sound_effects": effects, "narration": narration}, indent=2) + "\n"
    )
    rate = 22050
    mix = np.zeros(round(cursor * rate), dtype=np.float64)
    for index, effect in enumerate(effects):
        length = 0.65 if effect["cue"] == "transformation" else 0.25
        t = np.arange(round(length * rate)) / rate
        frequency = 100 if effect["cue"] in {"impact", "final_impact"} else 350
        wavelet = (
            np.sin(2 * math.pi * (frequency * t - 45 * t * t)) * np.exp(-t * 18) * 0.22
        )
        start = round(effect["time"] * rate)
        count = min(len(wavelet), len(mix) - start)
        if count > 0:
            mix[start : start + count] += wavelet[:count]
    audio = project / "audio/mock-sfx.wav"
    with wave.open(str(audio), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes((np.tanh(mix) * 32767).astype("<i2").tobytes())
    return srt, audio


def assemble_video(
    project: Path,
    shot_list: ShotList,
    clips: list[Path],
    *,
    comment="MOCK ANIMATIC; simulation interpretation; no AI media API calls",
) -> Path:
    if len(clips) != len(shot_list.shots):
        raise ValueError("Each shot needs one current rendered clip")
    srt, audio = timing_tracks(project, shot_list)
    final = project / "final"
    edited = final / "edited"
    edited.mkdir(exist_ok=True)
    selected = []
    for shot, source in zip(shot_list.shots, clips):
        effects = shot.editorial
        filters = []
        if effects.impact_freeze_seconds:
            filters.extend(
                [
                    f"tpad=start_mode=clone:start_duration={effects.impact_freeze_seconds}",
                    f"trim=duration={shot.duration_seconds}",
                    "setpts=PTS-STARTPTS",
                ]
            )
        if effects.flash:
            at = effects.impact_freeze_seconds
            filters.append(
                f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.5:t=fill:enable='between(t,{at},{at+.035})'"
            )
        if effects.fade_in:
            filters.append(f"fade=t=in:st=0:d={effects.fade_in}")
        if effects.fade_out:
            filters.append(
                f"fade=t=out:st={shot.duration_seconds-effects.fade_out}:d={effects.fade_out}"
            )
        destination = edited / f"{shot.shot_id}-v{shot.version}.mp4"
        if filters:
            run_ffmpeg(
                [
                    "-i",
                    str(source),
                    "-vf",
                    ",".join(filters),
                    "-frames:v",
                    str(shot.frame_count),
                    "-r",
                    str(shot_list.settings.fps),
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "21",
                    "-pix_fmt",
                    "yuv420p",
                    "-threads",
                    "2",
                    str(destination),
                ]
            )
            selected.append(destination)
        else:
            selected.append(source)
    concat = final / "concat.txt"
    # Relative, application-generated paths avoid concat quoting of user directory names.
    import os

    rows = []
    for path in selected:
        relative = Path(os.path.relpath(path, final)).as_posix()
        if "'" in relative or "\n" in relative:
            raise ValueError("Unexpected generated clip path")
        rows.append(f"file '{relative}'")
    concat.write_text("\n".join(rows) + "\n")
    output = final / "episode.mp4"
    run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-i",
            str(audio),
            "-i",
            str(srt),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-map",
            "2:s:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=eng",
            "-metadata",
            f"comment={comment}",
            "-t",
            str(sum(s.frame_count for s in shot_list.shots) / shot_list.settings.fps),
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    return output


def inspect_video(path: Path) -> dict:
    import imageio_ffmpeg

    reader = imageio_ffmpeg.read_frames(str(path))
    metadata = next(reader)
    reader.close()
    frames, duration = imageio_ffmpeg.count_frames_and_secs(str(path))
    return {
        "width": metadata["size"][0],
        "height": metadata["size"][1],
        "fps": metadata["fps"],
        "frames": frames,
        "duration": duration,
    }
