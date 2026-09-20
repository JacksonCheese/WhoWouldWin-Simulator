"""Provider-neutral contracts plus strictly local mocks. No HTTP clients or live integrations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import os
import shutil
import subprocess
from .schemas import AssetReference, EditorialEffects, ProviderSettings


def provider_settings(path: Path | None = None) -> ProviderSettings:
    data = {} if path is None else __import__("json").loads(path.read_text())
    data.setdefault("image_provider", os.environ.get("WWS_IMAGE_PROVIDER", "mock"))
    data.setdefault("video_provider", os.environ.get("WWS_VIDEO_PROVIDER", "mock"))
    return ProviderSettings.model_validate(data)


def ffmpeg_binary() -> str:
    configured = os.environ.get("WWS_FFMPEG")
    if configured:
        binary = shutil.which(configured) or (
            configured if Path(configured).is_file() else None
        )
        if not binary:
            raise ValueError("WWS_FFMPEG does not name an executable")
        return binary
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        found = shutil.which("ffmpeg")
        if found:
            return found
        raise RuntimeError(
            "Install the local video extra: pip install -e '.[video]'"
        ) from None


def run_ffmpeg(args: list[str], *, cwd: Path | None = None, timeout=300):
    result = subprocess.run(
        [
            ffmpeg_binary(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            *args,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError("FFmpeg failed: " + result.stderr[-5000:])


@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    negative_constraints: tuple[str, ...]
    aspect_ratio: str
    references: tuple[AssetReference, ...]
    width: int
    height: int
    output: Path
    mock_source: Path | None = None


@dataclass(frozen=True)
class RenderedAsset:
    path: Path
    provider: str
    actual_cost_usd: float = 0


@dataclass(frozen=True)
class VideoOptions:
    width: int
    height: int
    fps: int
    frame_count: int
    camera_motion: str
    effects: EditorialEffects


class ImageProvider(Protocol):
    def generate_keyframe(self, request: ImageRequest) -> RenderedAsset: ...


class VideoProvider(Protocol):
    def generate_video(
        self,
        start_frame: Path,
        motion_prompt: str,
        duration: float,
        aspect_ratio: str,
        references: tuple[AssetReference, ...],
        options: VideoOptions,
        output: Path,
    ) -> RenderedAsset: ...


class MockImageProvider:
    def generate_keyframe(self, request: ImageRequest) -> RenderedAsset:
        from PIL import Image

        if request.mock_source is None:
            raise ValueError("Mock image generation requires a local storyboard source")
        with Image.open(request.mock_source) as image:
            if image.size != (request.width, request.height):
                raise ValueError("Storyboard dimensions do not match image request")
        request.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(request.mock_source, request.output)
        return RenderedAsset(request.output, "mock-image")


class MockVideoProvider:
    def generate_video(
        self,
        start_frame: Path,
        motion_prompt: str,
        duration: float,
        aspect_ratio: str,
        references: tuple[AssetReference, ...],
        options: VideoOptions,
        output: Path,
    ) -> RenderedAsset:
        if abs(duration - options.frame_count / options.fps) > 1e-8:
            raise ValueError("Video duration/frame budget mismatch")
        output.parent.mkdir(parents=True, exist_ok=True)
        # Motion is a deterministic animatic camera move over a labelled storyboard.
        effects = options.effects
        hold = 0  # Impact freeze is applied once by the assembly editor.
        progress = f"max(0,on-{hold})/{max(1,options.frame_count-hold)}"
        zoom = f"1.025+{effects.punch_in}*({progress})"
        shake = f"{effects.shake*4:.3f}*sin(on*2.1)*exp(-on/6)"
        x = f"iw/2-iw/zoom/2+{shake}"
        if "pan" in options.camera_motion or "track" in options.camera_motion:
            x = f"(iw-iw/zoom)*({progress})+{shake}"
        y = f"ih/2-ih/zoom/2+{effects.shake*3:.3f}*cos(on*1.7)*exp(-on/6)"
        camera = f"zoompan=z='{zoom}':x='{x}':y='{y}':d={options.frame_count}:s={options.width}x{options.height}:fps={options.fps}"
        # Keep mock labels phone-safe while the scene beneath moves.
        top = round(options.height * 0.18)
        bottom = round(options.height * 0.76)
        graph = (
            f"[0:v]split=3[scene][head][foot];[scene]{camera}[moving];"
            f"[head]crop={options.width}:{top}:0:0[header];"
            f"[foot]crop={options.width}:{options.height-bottom}:0:{bottom}[footer];"
            f"[moving][header]overlay=0:0[labeled];[labeled][footer]overlay=0:{bottom}[out]"
        )
        run_ffmpeg(
            [
                "-i",
                str(start_frame),
                "-filter_complex",
                graph,
                "-map",
                "[out]",
                "-frames:v",
                str(options.frame_count),
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
                str(output),
            ]
        )
        return RenderedAsset(output, "mock-video")
