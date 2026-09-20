"""Golden coverage and paid-provider contracts tested offline against the official SDK."""

import copy
import json
from pathlib import Path
import socket
from types import SimpleNamespace
import pytest
from PIL import Image
import httpx
from runwayml import RunwayML

from whowouldwin.simulation.engine import Engine
from whowouldwin.simulation.replay import save_replay, load_replay, digest
from whowouldwin.cinematic.episodes.project import (
    direct_episode,
    load_episode,
    file_hash,
    write_json,
    record_asset,
    save_manifest,
)
from whowouldwin.cinematic.episodes.schemas import (
    DirectorSettings,
    ShotList,
    ShotStatus,
    AssetReference,
    EditorialEffects,
)
from whowouldwin.cinematic.episodes.providers import ImageRequest, VideoOptions
from whowouldwin.cinematic.episodes.editor import inspect_video
from whowouldwin.cinematic.golden import project as g
from whowouldwin.cinematic.golden.director import load_abilities, TEMPLATES
from whowouldwin.cinematic.golden.schemas import GoldenState
from whowouldwin.cinematic.golden.runway import (
    RunwaySession,
    RunwayImageProvider,
    RunwayVideoProvider,
    generation_cost,
    project_lock,
)
from whowouldwin.cinematic.golden.references import inspect_pack, for_shot


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Golden tests must never open a network connection")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.delenv("RUNWAYML_API_SECRET", raising=False)


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    root = tmp_path_factory.mktemp("golden-source")
    engine = Engine(seed=69, record=True)
    engine.run()
    replay = save_replay(engine, root / "replay.json")
    parent = direct_episode(
        replay,
        root / "episode",
        settings=DirectorSettings(
            duration_seconds=30, shot_count=15, width=180, height=320, fps=10
        ),
    )
    return parent, load_replay(replay)


@pytest.fixture
def golden(source, tmp_path):
    return g.create_sequence(source[0], tmp_path / "golden", width=180, fps=10)


@pytest.fixture
def real_plan(source, tmp_path):
    return g.create_sequence(source[0], tmp_path / "real-plan")


@pytest.fixture
def refs(tmp_path):
    root = tmp_path / "references"
    for group, names in {
        "naruto": ["front", "three-quarter", "action"],
        "omniman": ["front", "three-quarter", "side"],
        "style": ["style-01"],
        "arena": ["rooftop"],
    }.items():
        (root / group).mkdir(parents=True)
        for i, name in enumerate(names):
            Image.new("RGB", (320, 400), (80 + i * 30, 100, 140)).save(
                root / group / (name + ".png")
            )
    return root


def test_coverage_reuses_contacts_and_varies_rhythm(golden, source):
    m, shots, state = g.load(golden)
    assert state.selection_end == 22.55
    assert state.selection_start == 21.8
    assert len(shots.shots) == 7
    assert sum(s.frame_count for s in shots.shots) == 100
    durations = [s.duration_seconds for s in shots.shots]
    assert min(durations) == 0.5 and max(durations) == 2.4
    assert len(set(durations)) >= 5
    assert len({s.camera_angle for s in shots.shots}) >= 5
    assert len({s.source_moment_ids[0] for s in shots.shots}) < len(shots.shots)
    finishers = [
        s
        for s in shots.shots
        if s.source_moment_ids == shots.shots[-1].source_moment_ids
    ]
    assert (
        len(finishers) == 6 and len({tuple(s.source_event_ids) for s in finishers}) == 1
    )
    assert shots.shots[-1].coverage_role == "victory"
    assert shots.outcome == source[1]["result"]
    recorded = load_replay(golden / "simulation.json")
    assert digest(recorded["frames"]) == digest(source[1]["frames"])
    assert ShotList.model_validate_json(shots.model_dump_json()) == shots
    assert {
        "FINISHER",
        "TRANSFORMATION",
        "SPEED_BLITZ",
        "POWER_ATTACK",
        "DODGE",
        "HEAVY_COUNTER",
    } <= TEMPLATES.keys()


def test_specific_ability_semantics_and_prompt_limit(golden):
    m, shots, state = g.load(golden)
    profiles = json.loads((golden / "ability_visuals.json").read_text())
    assert len(profiles) >= 18
    for shot in shots.shots:
        assert shot.ability_visual_id in profiles
        assert len(shot.keyframe_prompt.encode("utf-16-le")) // 2 <= 1000
        assert "energy orb" not in shot.keyframe_prompt.lower()
        assert "@look" in shot.keyframe_prompt
        assert "no" in shot.motion_prompt.lower()
    assert "blue" in shots.shots[3].keyframe_prompt.lower()
    assert "releases" in shots.shots[2].action_description
    for shot in shots.shots:
        assert all(
            constraint in shot.keyframe_prompt
            for constraint in shot.negative_constraints
        )
    assert all(p["development_fixture"] for p in profiles.values())
    assert "rasengan" not in json.dumps(profiles).lower()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start_time": 10.2, "end_time": 11.2},
        {"start_moment": "moment-0021", "end_moment": "moment-0023"},
    ],
)
def test_explicit_transformation_selection(source, tmp_path, kwargs):
    # Parent moment IDs are kept stable; no re-selection/reindexing.
    parent = source[0]
    moments = json.loads((parent / "moments.json").read_text())
    form = next(m for m in moments if m["moment_type"] == "transformation")
    if "start_moment" in kwargs:
        kwargs = {"start_moment": form["moment_id"], "end_time": 11.2}
    root = g.create_sequence(parent, tmp_path / "selected", width=180, fps=10, **kwargs)
    _, shots, state = g.load(root)
    assert any(s.coverage_role == "medium_reveal" for s in shots.shots)
    assert shots.shots[-1].coverage_role != "victory"
    times = [s.continuity_state.simulation_time for s in shots.shots]
    assert times == sorted(times)


def test_missing_reference_error_is_clear_and_no_paid_fallback(real_plan, tmp_path):
    with pytest.raises(ValueError, match="Missing local references:.*naruto/front"):
        inspect_pack(tmp_path / "missing", ["naruto", "omniman"])
    with pytest.raises(ValueError, match="Supply local references"):
        g.keyframes(real_plan, provider="runway", real=True, max_cost=2)
    assert g.load(real_plan)[2].jobs == []


def test_pack_approval_and_tamper_detection(real_plan, refs):
    g.references(real_plan, refs)
    m, shots, state = g.load(real_plan)
    with pytest.raises(ValueError, match="Review the packed"):
        for_shot(real_plan, state, shots.shots[0])
    g.references(real_plan, approve=True)
    m, shots, state = g.load(real_plan)
    selected = for_shot(real_plan, state, shots.shots[0])
    assert [r.asset_id for r in selected] == ["naruto", "omniman", "look"]
    assert all(Path(r.path).stat().st_size < 3_750_000 for r in selected)
    (real_plan / "references/naruto/front.png").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="Reference changed"):
        for_shot(real_plan, state, shots.shots[0])


def test_keyframe_checkpoint_and_single_revision(golden):
    g.keyframes(golden)
    m, shots, state = g.load(golden)
    assert state.keyframe_approvals == {}
    assert not list((golden / "clips").glob("*.mp4"))
    with pytest.raises(ValueError, match="approve this exact keyframe"):
        g.animate(golden)
    g.approve_keyframes(golden, shot_id="shot-001")
    assert "shot-001" in g.load(golden)[2].keyframe_approvals
    sibling = file_hash(golden / "keyframes/shot-002-v1-mock.png")
    g.keyframes(golden, shot_id="shot-001", regenerate_one=True)
    m, shots, state = g.load(golden)
    assert shots.shots[0].version == 2 and shots.shots[1].version == 1
    assert "shot-001" not in state.keyframe_approvals
    assert sibling == file_hash(golden / "keyframes/shot-002-v1-mock.png")


def test_real_opt_in_and_finite_budget_are_required(real_plan):
    for kwargs in [
        {"provider": "runway"},
        {"real": True},
        {"provider": "runway", "real": True},
        {"provider": "runway", "real": True, "max_cost": float("nan")},
        {"provider": "runway", "real": True, "max_cost": float("inf")},
    ]:
        with pytest.raises(ValueError):
            g.keyframes(real_plan, **kwargs)
    with pytest.raises(ValueError, match="never bypasses"):
        g.animate(real_plan, provider="runway", real=True, max_cost=2, allow_draft=True)


def test_cost_estimate_and_model_constraints(golden):
    e = g.estimate(golden)
    assert e["one_pass_usd"] == pytest.approx(1.89)
    assert e["image_cost_usd"] == pytest.approx(0.14)
    assert generation_cost("video", "gen4_turbo", 5) == 0.25
    with pytest.raises(ValueError, match="5 or 10"):
        generation_cost("video", "gen4_turbo", 2)
    assert generation_cost("video", "gen4.5", 2) == 0.24
    with pytest.raises(ValueError, match="verified"):
        generation_cost("image", "unknown-model")


class FakeRunway:
    """Actual official SDK talking ONLY to an in-process HTTPX transport."""

    def __init__(self, *, fail=False, unknown=False, poll_error=False):
        self.posts = []
        self.gets = 0
        self.fail = fail
        self.unknown = unknown
        self.poll_error = poll_error
        self.client = RunwayML(
            api_key="offline-test-secret",
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(self.respond)),
        )

    def respond(self, request):
        if request.method == "POST":
            self.posts.append(json.loads(request.content))
            if self.unknown:
                raise httpx.ReadTimeout("ambiguous response", request=request)
            return httpx.Response(200, json={"id": "task-001"})
        self.gets += 1
        if self.poll_error and self.gets == 1:
            return httpx.Response(503, json={"error": "temporary"})
        if self.fail:
            return httpx.Response(
                200,
                json={
                    "id": "task-001",
                    "createdAt": "2026-09-06T00:00:00Z",
                    "status": "FAILED",
                    "failure": "redacted",
                    "failureCode": "SAFETY.TEST",
                    "cost": {"credits": 0},
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "task-001",
                "createdAt": "2026-09-06T00:00:00Z",
                "status": "SUCCEEDED",
                "output": ["https://example.invalid/fixture.png"],
                "cost": {"credits": 2},
            },
        )

    @staticmethod
    def download(url, path):
        Image.new("RGB", (720, 1280), "#384858").save(path)

    def session(self, root, **kwargs):
        return RunwaySession(
            root,
            client_factory=lambda: self.client,
            downloader=self.download,
            sleeper=lambda _: None,
            poll_seconds=0,
            progress=None,
            **kwargs,
        )


def test_official_image_request_poll_cost_cache_and_no_automatic_video(real_plan, refs):
    g.references(real_plan, refs, approve=True)
    fake = FakeRunway(poll_error=True)
    g.keyframes(
        real_plan,
        provider="runway",
        real=True,
        max_cost=2,
        shot_id="shot-001",
        session_factory=fake.session,
    )
    assert len(fake.posts) == 1 and fake.gets == 2
    payload = fake.posts[0]
    assert payload["model"] == "gen4_image_turbo" and payload["ratio"] == "720:1280"
    assert len(payload["referenceImages"]) == 3
    assert all(
        x["uri"].startswith("data:image/jpeg;base64,")
        for x in payload["referenceImages"]
    )
    m, shots, state = g.load(real_plan)
    assert state.jobs[0].task_id == "task-001" and state.jobs[0].actual_usd == 0.02
    assert state.jobs[0].poll_retries == 1
    assert state.keyframe_approvals == {}
    assert not list((real_plan / "clips").glob("*.mp4"))
    g.keyframes(
        real_plan,
        provider="runway",
        real=True,
        max_cost=2,
        shot_id="shot-001",
        session_factory=fake.session,
    )
    assert len(fake.posts) == 1
    text = (real_plan / "manifest.json").read_text()
    assert "offline-test-secret" not in text and "data:image" not in text


def test_budget_rejects_entire_image_batch_before_client_creation(real_plan, refs):
    g.references(real_plan, refs, approve=True)

    def forbidden(*args, **kwargs):
        raise AssertionError("Must reject before provider construction")

    with pytest.raises(ValueError, match="Budget rejected before submission"):
        g.keyframes(
            real_plan,
            provider="runway",
            real=True,
            max_cost=0.13,
            session_factory=forbidden,
        )
    assert g.load(real_plan)[2].jobs == []


def test_unknown_post_is_not_repeated_and_resumes_linked_task(real_plan, refs):
    g.references(real_plan, refs, approve=True)
    fake = FakeRunway(unknown=True)
    with pytest.raises(RuntimeError, match="unknown"):
        g.keyframes(
            real_plan,
            provider="runway",
            real=True,
            max_cost=2,
            shot_id="shot-001",
            session_factory=fake.session,
        )
    state = g.load(real_plan)[2]
    assert state.jobs[0].state == "UNKNOWN" and state.conservative_cost_usd == 0.02
    with pytest.raises(ValueError, match="outcome unknown"):
        g.keyframes(
            real_plan,
            provider="runway",
            real=True,
            max_cost=2,
            shot_id="shot-001",
            retry_failed=True,
            session_factory=fake.session,
        )
    assert len(fake.posts) == 1
    g.link_task(real_plan, state.jobs[0].job_key, "task-001")
    g.keyframes(
        real_plan,
        provider="runway",
        real=True,
        max_cost=2,
        shot_id="shot-001",
        session_factory=fake.session,
    )
    assert len(fake.posts) == 1 and g.load(real_plan)[2].jobs[0].state == "SUCCEEDED"


def test_known_failure_requires_explicit_retry(real_plan, refs):
    g.references(real_plan, refs, approve=True)
    fake = FakeRunway(fail=True)
    with pytest.raises(RuntimeError, match="task failed"):
        g.keyframes(
            real_plan,
            provider="runway",
            real=True,
            max_cost=2,
            shot_id="shot-001",
            session_factory=fake.session,
        )
    with pytest.raises(ValueError, match="retry-failed"):
        g.keyframes(
            real_plan,
            provider="runway",
            real=True,
            max_cost=2,
            shot_id="shot-001",
            session_factory=fake.session,
        )
    assert len(fake.posts) == 1
    fake.fail = False
    g.keyframes(
        real_plan,
        provider="runway",
        real=True,
        max_cost=2,
        shot_id="shot-001",
        retry_failed=True,
        session_factory=fake.session,
    )
    state = g.load(real_plan)[2]
    assert (
        len(fake.posts) == 2
        and len(state.jobs) == 2
        and state.conservative_cost_usd == 0.02
    )


def test_successful_task_download_retry_does_not_resubmit(real_plan, refs):
    g.references(real_plan, refs, approve=True)
    fake = FakeRunway()
    original = fake.download

    def failed(*args):
        raise OSError("offline download failure")

    fake.download = failed
    with pytest.raises(RuntimeError, match="same paid task"):
        g.keyframes(
            real_plan,
            provider="runway",
            real=True,
            max_cost=2,
            shot_id="shot-001",
            session_factory=fake.session,
        )
    fake.download = original
    g.keyframes(
        real_plan,
        provider="runway",
        real=True,
        max_cost=2,
        shot_id="shot-001",
        session_factory=fake.session,
    )
    assert len(fake.posts) == 1 and fake.gets == 2


def test_video_uses_approved_frame_and_full_generation_duration(
    real_plan, refs, tmp_path
):
    g.references(real_plan, refs, approve=True)
    fake = FakeRunway()
    g.keyframes(
        real_plan,
        provider="runway",
        real=True,
        max_cost=2,
        shot_id="shot-001",
        session_factory=fake.session,
    )
    with pytest.raises(ValueError, match="approve this exact keyframe"):
        g.animate(
            real_plan,
            provider="runway",
            real=True,
            max_cost=2,
            shot_id="shot-001",
            session_factory=fake.session,
        )
    g.approve_keyframes(real_plan, shot_id="shot-001")
    # A local real MP4 fixture is returned via the downloader, with no network.
    from whowouldwin.cinematic.episodes.providers import run_ffmpeg

    clip = tmp_path / "fixture.mp4"
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=gray:s=720x1280:r=24:d=5",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ]
    )
    import shutil

    fake.download = lambda url, path: shutil.copyfile(clip, path)
    g.animate(
        real_plan,
        provider="runway",
        real=True,
        max_cost=2,
        shot_id="shot-001",
        session_factory=fake.session,
    )
    payload = fake.posts[-1]
    assert payload["model"] == "gen4_turbo" and payload["duration"] == 5
    assert payload["promptImage"].startswith("data:image/png;base64,")
    assert (
        inspect_video(real_plan / "clips/shot-001-v1-runway-full.mp4")["frames"] == 120
    )


def test_complete_mock_trim_assembly_keeps_full_clips(golden):
    g.keyframes(golden)
    g.animate(golden, allow_draft=True)
    full = golden / "clips/shot-001-v1-mock-full.mp4"
    before = file_hash(full)
    assert inspect_video(full)["duration"] == 5
    g.trim(golden, "shot-001", 1.5)
    output = g.assemble(golden)
    assert inspect_video(output) == {
        "width": 180,
        "height": 320,
        "fps": 10.0,
        "frames": 100,
        "duration": 10.0,
    }
    assert file_hash(full) == before
    assert (golden / "contact-sheet.png").is_file()
    assert (
        "No real generations have been run"
        in (golden / "quality_report.md").read_text()
    )
    assert g.load(golden)[2].conservative_cost_usd == 0
    with pytest.raises(ValueError, match="exceeds"):
        g.trim(golden, "shot-001", 4.9)
