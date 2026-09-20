"""The shot pipeline interprets completed replays without changing combat facts."""

import ast
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image
from pydantic import ValidationError
from whowouldwin.combat.environment import Matchup
from whowouldwin.simulation.engine import Engine
from whowouldwin.simulation.replay import (
    digest,
    load_replay,
    save_replay,
    verify_replay,
)
from whowouldwin.cinematic.episodes.adapter import adapt_replay
from whowouldwin.cinematic.episodes.continuity import ContinuityTracker
from whowouldwin.cinematic.episodes.director import CinematicDirector, budget_frames
from whowouldwin.cinematic.episodes.editor import inspect_video
from whowouldwin.cinematic.episodes.project import (
    assemble_episode,
    direct_episode,
    load_episode,
    render_episode,
    set_shot_status,
    storyboard_episode,
    file_hash,
)
from whowouldwin.cinematic.episodes.providers import (
    ImageRequest,
    MockImageProvider,
    MockVideoProvider,
    VideoOptions,
    provider_settings,
)
from whowouldwin.cinematic.episodes.schemas import (
    CinematicBattleEvent,
    DirectorSettings,
    EditorialEffects,
    EventLog,
    SelectorSettings,
    ShotList,
    ShotStatus,
    ShotType,
    StateFrame,
)
from whowouldwin.cinematic.episodes.selector import CinematicEventSelector
from whowouldwin.cinematic.episodes.storyboard import (
    MockStoryboardRenderer,
    RenderContext,
)
from whowouldwin.cinematic.episodes.visual_bibles import load_arena, load_visuals

SMALL = DirectorSettings(
    duration_seconds=30, shot_count=15, width=180, height=320, fps=10
)


@pytest.fixture(scope="module")
def battle(tmp_path_factory):
    engine = Engine(seed=69, record=True)
    engine.run()
    path = save_replay(engine, tmp_path_factory.mktemp("episode-source") / "fight.json")
    return path, load_replay(path)


@pytest.fixture(scope="module")
def log(battle):
    return adapt_replay(battle[1])


@pytest.fixture(scope="module")
def direction(log):
    moments = CinematicEventSelector().select(log)
    visuals = load_visuals(log.fighter_profile_ids)
    arena = load_arena()
    shots = CinematicDirector().direct(log, moments, visuals, arena, SMALL)
    return moments, visuals, arena, shots


def test_adapter_preserves_each_source_event_and_damage(battle, log):
    source = [e for frame in battle[1]["frames"] for e in frame["events"]]
    assert len(source) == len(log.events)
    assert log.outcome == battle[1]["result"]
    assert len(log.state_timeline) == len(battle[1]["frames"])
    for index, (raw, event) in enumerate(zip(source, log.events)):
        assert event.source_index == index
        assert event.source_event_ids == [f"sim-{index:06d}"]
        assert event.event_type == raw["type"]
        assert event.simulation_time == raw["timestamp"]
        assert event.source_values == raw["values"]
        assert event.damage == (
            raw["values"]["damage"] if raw["type"] == "DamageApplied" else 0
        )
        assert event.health_after_damage == (
            raw["values"]["health"] if raw["type"] == "DamageApplied" else None
        )
    assert any(e.velocities["omniman"].y != 0 for e in log.events)
    assert all(
        not e.environment_effect or not e.environment_effect["persistent_destruction"]
        for e in log.events
    )


def test_adapter_and_director_never_mutate_source(battle, direction):
    before = digest(battle[1])
    log = adapt_replay(battle[1])
    moments, visuals, arena, _ = direction
    CinematicDirector().direct(log, moments, visuals, arena, SMALL)
    assert digest(battle[1]) == before
    log.events[0].source_values["test"] = "local copy"
    assert digest(battle[1]) == before


def test_mirror_match_has_two_distinct_entities(tmp_path):
    e = Engine(
        Matchup(fighter_a="naruto", fighter_b="naruto", rules={"timeout": 0.1}),
        record=True,
    )
    e.run()
    log = adapt_replay(load_replay(save_replay(e, tmp_path / "mirror.json")))
    assert log.fighter_profile_ids == {"naruto@0": "naruto", "naruto@1": "naruto"}
    assert len(log.initial_states) == 2
    visuals = load_visuals(log.fighter_profile_ids)
    shots = CinematicDirector().direct(
        log, CinematicEventSelector().select(log), visuals, load_arena(), SMALL
    )
    assert len(shots.shots[-1].subjects) == 2  # Timeout draw does not invent a winner.
    assert "Draw" in shots.shots[-1].action_description


def event(index, kind, time, **kwargs):
    return CinematicBattleEvent(
        event_id=f"event-{index:06d}",
        simulation_time=time,
        actor_id="naruto",
        target_ids=["omniman"],
        ability_id="strike",
        event_type=kind,
        source_event_ids=[f"sim-{index:06d}"],
        source_index=index,
        source_tick=round(time * 20),
        **kwargs,
    )


def test_importance_prioritizes_outcome_transform_and_first_hit(log):
    selector = CinematicEventSelector()
    attack = next(e for e in log.events if e.damage > 0)
    regular = sum(selector.score(attack).values())
    assert sum(selector.score(attack, first_hit=True).values()) > regular
    assert sum(selector.score(attack, repetitions=9).values()) < regular
    transform = event(0, "TransformationActivated", 0)
    outcome = event(1, "FightEnded", 1)
    assert sum(selector.score(transform).values()) > regular
    assert sum(selector.score(outcome).values()) > regular


def test_grouping_collapses_contact_but_separates_new_attacks(log):
    events = [
        event(0, "AttackStarted", 1),
        event(1, "AttackHit", 1.1),
        event(2, "DamageApplied", 1.1, damage=60, impact_score=0.6),
        event(3, "Knockback", 1.15),
        event(4, "AttackStarted", 1.2),
        event(5, "AttackDodged", 1.3, narrative_tags=["successful_defense"]),
    ]
    sample = log.model_copy(update={"events": events})
    selected = CinematicEventSelector(SelectorSettings(minimum_score=0)).select(sample)
    assert len(selected) == 2
    assert selected[0].source_event_ids == [f"event-{i:06d}" for i in range(4)]
    assert selected[1].moment_type == "dodge"
    assert not set(selected[0].source_event_ids) & set(selected[1].source_event_ids)


def test_selection_is_bounded_and_keeps_finisher(direction, log):
    moments = direction[0]
    assert len(moments) <= 28 < len(log.events)
    assert moments[0].moment_type == "faceoff"
    assert moments[-1].moment_type == "outcome"
    assert any(m.moment_type == "finisher" for m in moments)
    assert all(m.start_time <= m.end_time for m in moments)
    assert {i for m in moments for i in m.source_event_ids} <= {
        e.event_id for e in log.events
    }


@pytest.mark.parametrize(
    "seconds,count,fps", [(30, 15, 10), (60, 24, 30), (90, 35, 60), (30.15, 35, 20)]
)
def test_frame_budget_is_exact_and_bounded(seconds, count, fps):
    settings = DirectorSettings(duration_seconds=seconds, shot_count=count, fps=fps)
    frames = budget_frames([1 + i % 3 for i in range(count)], settings)
    assert sum(frames) == round(seconds * fps)
    assert all(0.5 <= f / fps <= 4 for f in frames)
    assert frames[0] == round(settings.intro_seconds * fps)
    assert frames[-1] == round(settings.outro_seconds * fps)


def test_impossible_budget_rejected():
    with pytest.raises(ValueError, match="cannot fit"):
        budget_frames([1] * 15, DirectorSettings(duration_seconds=90, shot_count=15))
    with pytest.raises(ValidationError, match="Resolution"):
        DirectorSettings(width=1081)


def test_director_variety_chronology_prompts_and_serialization(log, direction):
    moments, visuals, arena, shots = direction
    second = CinematicDirector().direct(log, moments, visuals, arena, SMALL)
    assert shots == second
    assert ShotList.model_validate_json(shots.model_dump_json()) == shots
    assert EventLog.model_validate_json(log.model_dump_json()) == log
    assert shots.shots[0].shot_type == ShotType.ESTABLISHING
    assert shots.shots[-1].shot_type == ShotType.VICTORY
    assert len({s.shot_type for s in shots.shots}) >= 7
    assert len({s.camera_motion for s in shots.shots}) >= 7
    assert any(len(s.subjects) == 1 for s in shots.shots[1:-1])
    assert [s.simulation_end for s in shots.shots] == sorted(
        s.simulation_end for s in shots.shots
    )
    assert all(
        s.source_moment_ids and s.source_event_ids and s.negative_constraints
        for s in shots.shots
    )
    assert all(
        "interpretation" in " ".join(s.negative_constraints) for s in shots.shots
    )
    assert shots.outcome_digest == digest(log.outcome)


def test_continuity_matches_every_recorded_frame(log, direction):
    tracker = ContinuityTracker(log, direction[1], direction[2])
    for frame in log.state_timeline[::17] + log.state_timeline[-1:]:
        c = tracker.at(frame.simulation_time)
        for key, state in frame.fighters.items():
            assert c.characters[key].health == state.health
            assert c.characters[key].transformation == state.transformation
            assert c.characters[key].location == state.position
            assert c.characters[key].persistent_effects == state.statuses
            assert c.characters[key].visible_injuries == []
            assert c.characters[key].clothing_damage == []
        assert c.environmental_destruction == []


def test_omitted_events_form_expiry_and_healing_do_not_reset_wear(log, direction):
    initial = copy.deepcopy(log.initial_states)
    injured = copy.deepcopy(initial)
    healed = copy.deepcopy(initial)
    injured["naruto"].health_fraction = 0.15
    injured["naruto"].transformation = "chakra"
    injured["naruto"].statuses = ["power"]
    sample = log.model_copy(
        update={
            "events": [],
            "state_timeline": [
                StateFrame(simulation_time=0, fighters=initial),
                StateFrame(simulation_time=1, fighters=injured),
                StateFrame(simulation_time=2, fighters=healed),
            ],
        }
    )
    tracker = ContinuityTracker(sample, direction[1], direction[2])
    middle = tracker.at(1).characters["naruto"]
    after = tracker.at(2).characters["naruto"]
    assert middle.transformation == "chakra"
    assert after.transformation is None and after.persistent_effects == []
    assert middle.surface_wear == after.surface_wear == "heavy surface scuffs"
    assert middle.costume_version == after.costume_version


def test_visual_bibles_are_separate_development_fixtures():
    visuals = load_visuals({s: s for s in ("naruto", "omniman", "aang", "homelander")})
    assert len(visuals) == 4
    for profile in visuals.values():
        assert profile.development_fixture
        assert profile.costume_description and profile.prohibited_visual_changes
        assert profile.color_palette
        assert "physical" not in profile.model_dump()
    assert load_arena().development_fixture


def test_mock_storyboards_are_byte_deterministic_and_varied(tmp_path, direction, log):
    _, visuals, _, shots = direction
    renderer = MockStoryboardRenderer()
    context = RenderContext(tmp_path, SMALL, visuals, log.fighter_names)
    frame = renderer.render(shots.shots[0], context)
    original = frame.path.read_bytes()
    assert renderer.render(shots.shots[0], context).path.read_bytes() == original
    other = renderer.render(shots.shots[2], context)
    assert other.sha256 != frame.sha256
    with Image.open(frame.path) as image:
        assert image.size == (180, 320)
        assert len(image.getcolors(180 * 320)) > 30


def test_live_providers_cannot_be_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("WWS_VIDEO_PROVIDER", "paid-provider")
    with pytest.raises(ValidationError):
        provider_settings()
    monkeypatch.delenv("WWS_VIDEO_PROVIDER")
    path = tmp_path / "providers.json"
    path.write_text('{"network_enabled": true}')
    with pytest.raises(ValidationError):
        provider_settings(path)
    assert provider_settings().estimated_cost_usd == 0


def test_mock_provider_contract_creates_actual_decodable_clip(tmp_path):
    source = tmp_path / "board.png"
    Image.new("RGB", (180, 320), "#333333").save(source)
    keyframe = MockImageProvider().generate_keyframe(
        ImageRequest("fixture", (), "9:16", (), 180, 320, tmp_path / "key.png", source)
    )
    assert keyframe.path.read_bytes() == source.read_bytes()
    options = VideoOptions(
        180, 320, 10, 10, "tracking shot", EditorialEffects(punch_in=0.1)
    )
    clip = MockVideoProvider().generate_video(
        keyframe.path, "local motion", 1, "9:16", (), options, tmp_path / "clip.mp4"
    )
    assert clip.actual_cost_usd == 0
    metadata = inspect_video(clip.path)
    assert metadata["frames"] == 10
    assert metadata["duration"] == pytest.approx(1)
    assert (metadata["width"], metadata["height"]) == (180, 320)
    with pytest.raises(ValueError, match="budget"):
        MockVideoProvider().generate_video(
            keyframe.path, "", 2, "9:16", (), options, tmp_path / "bad.mp4"
        )


def test_manifest_approval_rejection_and_revision(battle, tmp_path):
    project = direct_episode(battle[0], tmp_path / "episode", settings=SMALL)
    manifest, shots = load_episode(project)
    assert manifest.simulation_seed == 69 and manifest.actual_cost_usd == 0
    assert all(s.status == ShotStatus.DRAFT for s in shots.shots)
    with pytest.raises(ValueError, match="approval"):
        render_episode(project)
    with pytest.raises(ValueError, match="storyboard"):
        set_shot_status(project, "shot-001", ShotStatus.APPROVED)
    storyboard_episode(project)
    set_shot_status(project, "shot-001", ShotStatus.APPROVED)
    render_episode(project, shot_id="shot-001")
    first = load_episode(project)[0]
    assert first.render_approvals["shot-001"] == "approved"
    assert first.assets["clip:shot-001"].shot_version == 1
    set_shot_status(project, "shot-001", ShotStatus.REJECTED)
    with pytest.raises(ValueError, match="review"):
        render_episode(project, allow_draft=True, shot_id="shot-001")
    set_shot_status(
        project,
        "shot-001",
        ShotStatus.NEEDS_REGENERATION,
        motion_prompt="Revised static camera; preserve source action.",
    )
    revised = load_episode(project)
    assert revised[1].shots[0].version == 2
    assert revised[1].shots[1].version == 1
    assert "clip:shot-001" not in revised[0].assets
    assert "final_video" not in revised[0].assets
    storyboard_episode(project)
    set_shot_status(project, "shot-001", ShotStatus.APPROVED)
    render_episode(project, shot_id="shot-001")
    final = load_episode(project)[0]
    assert final.assets["clip:shot-001"].shot_version == 2
    assert (project / "clips/shot-001-v1.mp4").exists()  # Prior revision retained.
    assert (project / "clips/shot-001-v2.mp4").exists()
    assert file_hash(project / "simulation.json") == file_hash(battle[0])


def test_episode_resume_rejects_changed_settings_and_manual_edits(battle, tmp_path):
    project = direct_episode(battle[0], tmp_path / "resume", settings=SMALL)
    assert direct_episode(battle[0], project, settings=SMALL) == project
    with pytest.raises(ValueError, match="different"):
        direct_episode(
            battle[0], project, settings=SMALL.model_copy(update={"screen_shake": 0})
        )
    path = project / "shot_list.json"
    payload = json.loads(path.read_text())
    payload["shots"][0]["keyframe_prompt"] = "manual edit"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="revision workflow"):
        load_episode(project)


def test_full_mock_cli_video_and_source_outcome_invariant(tmp_path, battle):
    project = tmp_path / "complete"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "whowouldwin.cli.main",
            "create-video",
            "naruto",
            "omni_man",
            "--seed",
            "69",
            "--mock",
            "--duration",
            "30",
            "--shots",
            "15",
            "--fps",
            "10",
            "--width",
            "180",
            "--output",
            str(project),
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "Paid API calls: 0" in result.stdout
    manifest, shots = load_episode(project)
    assert manifest.stage == "ASSEMBLED"
    assert set(manifest.render_approvals.values()) == {"explicit mock draft override"}
    with pytest.raises(ValueError, match="approval"):
        render_episode(project)  # A prior draft preview does not grant human approval.
    validation = json.loads((project / "final/validation.json").read_text())
    assert validation["frames"] == 300
    assert validation["duration"] == pytest.approx(30)
    assert validation["simulation_outcome"] == battle[1]["result"]
    assert validation["outcome_digest"] == digest(battle[1]["result"])
    for path in [
        "simulation.json",
        "events.json",
        "moments.json",
        "shot_list.json",
        "continuity.json",
        "manifest.json",
        "storyboard/contact-sheet.png",
        "audio/mock-sfx.wav",
        "audio/timing.json",
        "final/captions.srt",
        "final/episode.mp4",
    ]:
        assert (project / path).stat().st_size > 0
    assert "wins by ko" in (project / "final/captions.srt").read_text()
    before = file_hash(project / "clips/shot-002-v1.mp4")
    render_episode(project, allow_draft=True)
    assert file_hash(project / "clips/shot-002-v1.mp4") == before
    assert verify_replay(project / "simulation.json") == battle[1]["result"]
    # A fresh engine still yields exactly the recorded result and every tick/event.
    engine = Engine(seed=69, record=True)
    assert engine.run() == battle[1]["result"]
    assert digest(engine.frames) == digest(battle[1]["frames"])


def test_simulation_layer_has_no_cinematic_or_renderer_imports():
    root = Path(__file__).resolve().parents[1] / "src/whowouldwin"
    for package in ("combat", "simulation", "ai", "characters"):
        for path in (root / package).glob("*.py"):
            tree = ast.parse(path.read_text())
            imports = [
                n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
            ]
            imports += [
                a.name
                for n in ast.walk(tree)
                if isinstance(n, ast.Import)
                for a in n.names
            ]
            assert not any(
                any(p in value.split(".") for p in ("cinematic", "visual", "pygame"))
                for value in imports
            ), path


@pytest.mark.parametrize(
    "a,b",
    [
        ("naruto", "omniman"),
        ("aang", "homelander"),
        ("naruto", "aang"),
        ("omniman", "homelander"),
    ],
)
def test_overlapping_moments_never_rewind_continuity(a, b, tmp_path):
    for seed in (0, 4, 9):
        engine = Engine(Matchup(fighter_a=a, fighter_b=b, seed=seed), record=True)
        engine.run()
        log = adapt_replay(load_replay(save_replay(engine, tmp_path / "source.json")))
        shots = CinematicDirector().direct(
            log,
            CinematicEventSelector().select(log),
            load_visuals(log.fighter_profile_ids),
            load_arena(),
            DirectorSettings(),
        )
        times = [s.continuity_state.simulation_time for s in shots.shots]
        assert times == sorted(times)
        assert (
            shots.shots[-1].continuity_state.simulation_time == log.outcome["duration"]
        )


def test_arena_accumulates_only_explicit_normalized_destruction(log, direction):
    blast = event(
        0,
        "Explosion",
        1,
        environment_effect={"kind": "blast", "persistent_destruction": False},
    )
    broken = event(
        1,
        "EnvironmentChanged",
        2,
        environment_effect={
            "persistent_destruction": True,
            "description": "Recorded west wall damage",
            "state_update": {"west_wall": "damaged"},
            "basis": "Explicit test fixture",
        },
    )
    sample = log.model_copy(update={"events": [blast, broken]})
    tracker = ContinuityTracker(sample, direction[1], direction[2])
    assert tracker.at(1).environmental_destruction == []
    assert tracker.at(2).environmental_destruction == ["Recorded west wall damage"]
    assert tracker.at(9).arena_state["west_wall"] == "damaged"


def test_failed_direction_leaves_no_partial_episode(battle, tmp_path):
    output = tmp_path / "invalid-budget"
    with pytest.raises(ValueError, match="cannot fit"):
        direct_episode(
            battle[0],
            output,
            settings=DirectorSettings(duration_seconds=90, shot_count=15),
        )
    assert not output.exists()
