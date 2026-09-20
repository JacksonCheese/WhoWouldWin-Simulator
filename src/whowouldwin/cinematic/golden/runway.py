"""Opt-in official SDK adapters with a durable pre-submission spending ledger.

POST is never retried automatically: a lost submission response may already have
incurred cost. Poll/download retries resume the recorded task, not a new generation.
"""

import base64
from contextlib import contextmanager
import hashlib
import os
import math
import threading
from pathlib import Path
import re
import time
from urllib.parse import urlparse

from whowouldwin.simulation.replay import digest
from whowouldwin.cinematic.episodes.project import (
    load_episode,
    save_manifest,
    file_hash,
    now,
)
from whowouldwin.cinematic.episodes.providers import RenderedAsset
from .schemas import GoldenState, ProviderJob
from .prompts import utf16_length

PRICE_DATE = "2026-09-06"
_LOCK_STATE = threading.local()
IMAGE_COST = {
    "gen4_image_turbo": 0.02,
    "gen4_image": 0.05,
}  # 720p; unknown models fail closed.
VIDEO_COST = {"gen4_turbo": 0.05, "gen4.5": 0.12}


def generation_cost(kind, model, seconds=5):
    if kind == "image":
        if model not in IMAGE_COST:
            raise ValueError(
                "No verified image price/model contract; use gen4_image_turbo or gen4_image"
            )
        return IMAGE_COST[model]
    if model not in VIDEO_COST:
        raise ValueError(
            "No verified video price/model contract; use gen4_turbo or gen4.5"
        )
    if model == "gen4_turbo" and seconds not in {5, 10}:
        raise ValueError(
            "Gen-4 Turbo uses 5 or 10 seconds; edit duration is independent"
        )
    if model == "gen4.5" and (
        not float(seconds).is_integer() or not 2 <= seconds <= 10
    ):
        raise ValueError("Gen-4.5 duration must be an integer from 2 to 10")
    return round(VIDEO_COST[model] * seconds, 6)


@contextmanager
def project_lock(project):
    """Reentrant per thread, exclusive across processes; crash releases the OS lock."""
    import fcntl

    key = str(Path(project).resolve())
    held = getattr(_LOCK_STATE, "held", set())
    if key in held:
        yield
        return
    with (Path(project) / ".generation.lock").open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(
                "Another generation/review command holds this episode lock"
            ) from None
        _LOCK_STATE.held = held | {key}
        try:
            yield
        finally:
            _LOCK_STATE.held = held
            fcntl.flock(handle, fcntl.LOCK_UN)


def totals(state):
    actual = round(sum(j.actual_usd or 0 for j in state.jobs), 6)
    conservative = round(
        sum(
            j.reserved_usd if j.actual_usd is None else j.actual_usd for j in state.jobs
        ),
        6,
    )
    return actual, conservative


def save_state(project, manifest, state, action):
    state.confirmed_cost_usd, state.conservative_cost_usd = totals(state)
    manifest.actual_cost_usd = state.confirmed_cost_usd
    manifest.golden = state.model_dump(mode="json")
    save_manifest(project, manifest, action)


def data_uri(path):
    from PIL import Image

    with Image.open(path) as im:
        im.verify()
        mime = Image.MIME.get(im.format)
    if mime not in {"image/png", "image/jpeg", "image/webp"}:
        raise ValueError("Reference/keyframe must be PNG, JPEG or WebP")
    uri = f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    if len(uri) > 5_000_000:
        raise ValueError("Encoded reference exceeds the Runway 5 MB data-URI limit")
    return uri


def sdk_client():
    secret = os.environ.get("RUNWAYML_API_SECRET")
    if not secret:
        raise ValueError(
            "Set RUNWAYML_API_SECRET in your terminal before selecting Runway"
        )
    from runwayml import RunwayML

    # Disable SDK automatic POST retries to avoid duplicate paid tasks after timeouts.
    return RunwayML(api_key=secret, max_retries=0, timeout=60)


def download(url, path):
    # A separate unauthenticated client avoids forwarding API credentials to CDN hosts.
    import httpx

    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("Provider output must be a credential-free HTTPS URL")
    temporary = path.with_suffix(path.suffix + ".part")
    path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        count = 0
        with temporary.open("wb") as handle:
            for chunk in response.iter_bytes():
                count += len(chunk)
                if count > 500_000_000:
                    raise ValueError("Provider output exceeds local 500 MB limit")
                handle.write(chunk)
    temporary.replace(path)


class RunwaySession:
    def __init__(
        self,
        project,
        *,
        real=False,
        max_cost=None,
        client_factory=sdk_client,
        downloader=download,
        sleeper=time.sleep,
        poll_seconds=5,
        timeout_seconds=900,
        retry_failed=False,
        progress=print,
    ):
        if not real:
            raise ValueError("Runway requires an explicit --real opt-in")
        if max_cost is None or not math.isfinite(max_cost) or max_cost < 0:
            raise ValueError("Runway requires a non-negative --max-cost")
        self.project = Path(project).resolve()
        self.max_cost = max_cost
        self.client_factory = client_factory
        self.downloader = downloader
        self.sleeper = sleeper
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self.retry_failed = retry_failed
        self.progress = progress

    def generate(self, **kwargs):
        with project_lock(self.project):
            return self._generate(**kwargs)

    def _generate(
        self, *, shot_id, version, kind, model, payload, fingerprint, output, cost
    ):
        # Called inside the command's project lock, also safe as a standalone provider call.
        manifest, _ = load_episode(self.project)
        state = GoldenState.model_validate(manifest.golden)
        signature = digest(fingerprint)
        matches = [
            j
            for j in state.jobs
            if j.request_digest == signature
            and j.kind == kind
            and j.shot_id == shot_id
            and j.shot_version == version
        ]
        job = matches[-1] if matches else None
        if (
            job
            and job.state == "SUCCEEDED"
            and output.is_file()
            and file_hash(output) == job.output_sha256
        ):
            return RenderedAsset(output, "runway", job.actual_usd or job.reserved_usd)
        if job and job.state in {"FAILED", "CANCELLED"}:
            if not self.retry_failed:
                raise ValueError(
                    f"{shot_id}: task {job.task_id} failed; review quality_report.md, then explicitly use --retry-failed"
                )
            job = None
        if job and not job.task_id:
            raise ValueError(
                f"{shot_id}: submission outcome unknown. Do not resubmit; link its Runway task ID with golden-link-task ({job.job_key})"
            )
        if not job:
            used = totals(state)[1]
            if used + cost > self.max_cost + 1e-9:
                raise ValueError(
                    f"Budget rejected before submission: ${used:.2f} committed + ${cost:.2f} > ${self.max_cost:.2f}"
                )
        client = (
            self.client_factory()
        )  # No construction or credential access during mock workflows.
        if not job:
            job = ProviderJob(
                job_key=f"{shot_id}-v{version}-{kind}-{signature[:8]}-{len(matches)+1}",
                shot_id=shot_id,
                shot_version=version,
                kind=kind,
                model=model,
                request_digest=signature,
                attempt=len(matches) + 1,
                reserved_usd=cost,
                output_path=output.relative_to(self.project).as_posix(),
                created_at=now(),
                state="SUBMITTING",
            )
            state.jobs.append(job)
            state.max_cost_usd = self.max_cost
            save_state(
                self.project,
                manifest,
                state,
                f"Reserved ${cost:.2f} before {kind} submission for {shot_id}",
            )
            try:
                task = (
                    client.text_to_image if kind == "image" else client.image_to_video
                ).create(**payload)
                job.task_id = task.id
                job.state = "PENDING"
                save_state(
                    self.project,
                    manifest,
                    state,
                    f"Runway task recorded: {job.task_id}",
                )
            except Exception as error:
                status = getattr(error, "status_code", None)
                job.state = (
                    "FAILED"
                    if status and 400 <= status < 500 and status != 408
                    else "UNKNOWN"
                )
                job.actual_usd = 0 if job.state == "FAILED" else None
                job.failure = f'{type(error).__name__}; HTTP {status or "unknown"}; response body omitted'
                state.failures.append(f"{job.job_key}: {job.failure}")
                save_state(
                    self.project,
                    manifest,
                    state,
                    "Submission error; no automatic paid retry",
                )
                raise RuntimeError(
                    f"Runway submission {job.state.lower()}; details recorded without credentials. No retry submitted."
                ) from None
        started = time.monotonic()
        errors = 0
        last = None
        while time.monotonic() - started <= self.timeout_seconds:
            try:
                task = client.tasks.retrieve(job.task_id)
            except Exception as error:
                errors += 1
                job.poll_retries += 1
                save_state(
                    self.project,
                    manifest,
                    state,
                    f"Task retrieval retry {errors}: {type(error).__name__}",
                )
                if errors >= 3:
                    raise RuntimeError(
                        f"Task polling interrupted; rerun to resume {job.task_id}; no new paid task"
                    ) from None
                self.sleeper(min(20, self.poll_seconds * errors))
                continue
            errors = 0
            job.state = task.status
            task_cost = getattr(task, "cost", None)
            credits = getattr(task_cost, "credits", None)
            if credits is not None:
                job.actual_usd = round(credits * 0.01, 6)
            if last != job.state:
                save_state(
                    self.project, manifest, state, f"Task {job.task_id}: {job.state}"
                )
                if self.progress:
                    self.progress(f"{shot_id}: {job.state} ({job.task_id})")
                last = job.state
            if task.status in {"FAILED", "CANCELLED"}:
                code = (
                    getattr(task, "failure_code", "provider failure")
                    or "provider failure"
                )
                job.failure = re.sub("[^A-Za-z0-9_. -]", "", code)[:120]
                state.failures.append(f"{job.job_key}: {job.failure}")
                save_state(
                    self.project,
                    manifest,
                    state,
                    "Terminal provider failure; retry requires explicit --retry-failed",
                )
                raise RuntimeError(
                    f"Runway task failed: {job.failure}; no new task submitted"
                )
            if task.status == "SUCCEEDED":
                try:
                    urls = task.output
                    if not urls:
                        raise ValueError("Successful task has no output")
                    self.downloader(urls[0], output)
                    if kind == "image":
                        from PIL import Image

                        with Image.open(output) as im:
                            im.verify()
                    else:
                        from whowouldwin.cinematic.episodes.editor import inspect_video

                        if inspect_video(output)["duration"] <= 0:
                            raise ValueError("Empty provider clip")
                except Exception as error:
                    job.failure = f"Output retrieval/validation: {type(error).__name__}"
                    save_state(
                        self.project,
                        manifest,
                        state,
                        "Successful paid task retained; output download may be resumed",
                    )
                    raise RuntimeError(
                        "Output download/validation failed. Rerun to retrieve the same paid task, not regenerate."
                    ) from None
                job.output_sha256 = file_hash(output)
                job.failure = None
                save_state(
                    self.project,
                    manifest,
                    state,
                    f"Cached {kind} from task {job.task_id}",
                )
                return RenderedAsset(
                    output,
                    "runway",
                    job.actual_usd if job.actual_usd is not None else cost,
                )
            self.sleeper(self.poll_seconds)
        save_state(
            self.project, manifest, state, "Polling timeout; task retained for resume"
        )
        raise RuntimeError(
            f"Task {job.task_id} remains {job.state}; rerun the same command to resume without another paid submission"
        )


class RunwayImageProvider:
    def __init__(self, session, shot, model="gen4_image_turbo"):
        self.session = session
        self.shot = shot
        self.model = model

    def generate_keyframe(self, request):
        cost = generation_cost("image", self.model)
        if (request.width, request.height) != (720, 1280):
            raise ValueError("The first real keyframe contract is 720x1280")
        if not 1 <= len(request.references) <= 3:
            raise ValueError("Runway image generation requires 1–3 packed references")
        if not 0 < utf16_length(request.prompt) <= 1000:
            raise ValueError("Image prompt must fit 1000 UTF-16 code units")
        refs = [
            {"uri": data_uri(Path(r.path)), "tag": r.asset_id}
            for r in request.references
        ]
        fingerprint = {
            "model": self.model,
            "prompt": request.prompt,
            "ratio": "720:1280",
            "references": [
                (r.asset_id, file_hash(Path(r.path))) for r in request.references
            ],
        }
        payload = dict(
            model=self.model,
            prompt_text=request.prompt,
            ratio="720:1280",
            reference_images=refs,
            seed=int(digest(fingerprint)[:8], 16),
        )
        return self.session.generate(
            shot_id=self.shot.shot_id,
            version=self.shot.version,
            kind="image",
            model=self.model,
            payload=payload,
            fingerprint=fingerprint,
            output=request.output,
            cost=cost,
        )


class RunwayVideoProvider:
    def __init__(self, session, shot, model="gen4_turbo"):
        self.session = session
        self.shot = shot
        self.model = model

    def generate_video(
        self,
        start_frame,
        motion_prompt,
        duration,
        aspect_ratio,
        references,
        options,
        output,
    ):
        cost = generation_cost("video", self.model, duration)
        if (options.width, options.height) != (720, 1280) or aspect_ratio != "9:16":
            raise ValueError("The first real video contract is 720x1280, 9:16")
        if not 0 < utf16_length(motion_prompt) <= 1000:
            raise ValueError("Video prompt must fit 1000 UTF-16 code units")
        fingerprint = {
            "model": self.model,
            "prompt": motion_prompt,
            "keyframe": file_hash(start_frame),
            "ratio": "720:1280",
            "duration": duration,
        }
        payload = dict(
            model=self.model,
            prompt_text=motion_prompt,
            prompt_image=data_uri(start_frame),
            ratio="720:1280",
            duration=int(duration),
            seed=int(digest(fingerprint)[:8], 16),
        )
        return self.session.generate(
            shot_id=self.shot.shot_id,
            version=self.shot.version,
            kind="video",
            model=self.model,
            payload=payload,
            fingerprint=fingerprint,
            output=output,
            cost=cost,
        )
