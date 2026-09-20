"""The Blender plan stays deterministic and source-provenanced without bpy."""

from pathlib import Path

import pytest

from whowouldwin.cinematic.blender_backend.adapter import (
    ACTION_PRIMITIVES,
    POSE_PRIMITIVES,
    build_hybrid_plan,
    build_prototype_plan,
)
from whowouldwin.cinematic.blender_backend.action_library import (
    CLIP_NAMES,
    STANDARD_HUMANOID_BONES,
    choose_reaction,
)
from whowouldwin.cinematic.blender_backend import project as blender_project
from whowouldwin.cinematic.blender_backend import runtime as blender_runtime
from whowouldwin.cinematic.blender_backend.cli import COMMANDS as BLENDER_COMMANDS
from whowouldwin.cinematic.episodes.adapter import adapt_replay
from whowouldwin.simulation.engine import Engine
from whowouldwin.simulation.replay import digest, load_replay, save_replay


@pytest.fixture(scope="module")
def replay(tmp_path_factory):
    root = tmp_path_factory.mktemp("blender-replay")
    engine = Engine(seed=69, record=True)
    result = engine.run()
    return save_replay(engine, root / "fight.json"), result, digest(engine.frames)


def test_plan_is_deterministic_and_uses_recorded_dodge_counter(replay):
    replay_path, result, frames = replay
    log = adapt_replay(load_replay(replay_path))
    first = build_prototype_plan(log)
    second = build_prototype_plan(log)
    assert first == second
    assert first.source_outcome_digest == digest(result)
    assert round(first.settings.duration_seconds * first.settings.fps) == 360
    assert first.camera_shots[0].start_frame == 1
    assert first.camera_shots[-1].end_frame == 360
    assert all(a in ACTION_PRIMITIVES for a in first.required_action_primitives)
    assert first.schema_version == 2
    assert tuple(first.required_pose_primitives) == POSE_PRIMITIVES
    dodge = next(i for i in first.instructions if i.action == "dodge")
    dash = next(i for i in first.instructions if i.action == "dash")
    counter = next(i for i in first.instructions if i.action == "heavy_punch")
    launch = next(i for i in first.instructions if i.action == "launch")
    source = {event.event_id: event for event in log.events}
    assert source[dodge.source_event_ids[0]].event_type == "AttackDodged"
    assert source[counter.source_event_ids[0]].event_type == "AttackHit"
    assert source[launch.source_event_ids[0]].event_type == "Knockback"
    assert dash.trajectory == "accelerating_blitz"
    assert dash.target_position != dash.overshoot_position
    assert counter.contact_position is not None
    assert counter.trajectory == "accelerating_blitz"
    assert launch.trajectory == "launch_trajectory"
    assert digest(load_replay(replay_path)["frames"]) == frames
    fracture = next(
        effect for effect in first.effects if effect.effect == "wall_fracture"
    )
    assert fracture.authority == "presentation"


def test_motion_lab_cli_commands_are_registered():
    assert {"render-motion-debug", "render-motion-review"} <= BLENDER_COMMANDS


def test_project_emits_self_contained_bpy_runner_and_command(replay, tmp_path):
    source, result, _ = replay
    root = blender_project.create_project(source, tmp_path / "poc")
    manifest, plan = blender_project.load_project(root)
    assert manifest.source_checksum == plan.source_checksum
    script = (root / "scene.py").read_text()
    assert "create_rig" in script and "create_cameras" in script
    assert "create_effect" in script and "join_skinned_body" in script
    assert 'parent_type = "BONE"' not in script
    assert 'constraints.new("IK")' in script
    command = blender_project.command_preview(root)
    assert command[-1] == "render"
    assert str(root / "blender_plan.json") in command
    assert result["winner"] == 0


def test_project_accepts_character_packages_and_versions_asset_runtime(replay, tmp_path):
    source, _, _ = replay
    package_root = Path(__file__).resolve().parents[1] / "assets/characters"
    root = blender_project.create_project(
        source,
        tmp_path / "packaged",
        hybrid=True,
        character_packages={
            "fighter_a": package_root / "v4_evaluation_a",
            "fighter_b": package_root / "v4_evaluation_b",
        },
    )
    manifest, plan = blender_project.load_project(root)
    assert (root / "character_assets.py").is_file()
    assert "load_package_animation_overrides" in (root / "character_assets.py").read_text()
    assert manifest.asset_runtime_sha256
    assert plan.characters["fighter_a"].character_package.endswith("v4_evaluation_a")
    assert plan.characters["fighter_b"].character_package.endswith("v4_evaluation_b")


def test_missing_optional_asset_fails_before_blender(tmp_path, replay):
    source, _, _ = replay
    log, _ = blender_project._event_log(source)
    plan = build_prototype_plan(log)
    data = plan.model_dump(mode="json")
    data["characters"]["fighter_a"]["model_path"] = "assets/missing.glb"
    with pytest.raises(ValueError, match="Missing Blender asset"):
        blender_project._validate_optional_assets(
            plan.__class__.model_validate(data), tmp_path
        )


def test_schema_rejects_camera_gaps(replay):
    source, _, _ = replay
    log, _ = blender_project._event_log(source)
    data = build_prototype_plan(log).model_dump(mode="json")
    data["camera_shots"][1]["start_frame"] += 1
    with pytest.raises(ValueError, match="contiguous"):
        build_prototype_plan(log).__class__.model_validate(data)


def test_v2_requires_contact_but_v1_projects_remain_loadable(replay):
    source, _, _ = replay
    log, _ = blender_project._event_log(source)
    plan = build_prototype_plan(log)
    data = plan.model_dump(mode="json")
    counter = next(i for i in data["instructions"] if i["action"] == "heavy_punch")
    counter["contact_position"] = None
    with pytest.raises(ValueError, match="contact attacks require target points"):
        plan.__class__.model_validate(data)

    data["schema_version"] = 1
    data.pop("required_pose_primitives")
    for instruction in data["instructions"]:
        for field in (
            "trajectory",
            "overshoot_position",
            "recovery_position",
            "contact_position",
        ):
            instruction.pop(field, None)
    legacy = plan.__class__.model_validate(data)
    assert legacy.schema_version == 1
    assert legacy.required_pose_primitives == []


def test_runtime_implements_every_declared_pose_primitive():
    assert set(POSE_PRIMITIVES) == set(blender_runtime.POSES)


def test_hybrid_plan_uses_authored_clips_and_standard_rig_contract(replay):
    replay_path, result, frames = replay
    log = adapt_replay(load_replay(replay_path))
    first = build_hybrid_plan(log)
    second = build_hybrid_plan(log)
    assert first == second
    assert first.schema_version == 3
    assert first.source_outcome_digest == digest(result)
    assert first.source_checksum == build_prototype_plan(log).source_checksum
    assert tuple(first.required_animation_clips) == CLIP_NAMES
    assert all(instruction.clip_stack for instruction in first.instructions)
    assert set(first.rig_adapters) == {"fighter_a", "fighter_b"}
    assert all(
        set(adapter.standard_to_target) == set(STANDARD_HUMANOID_BONES)
        for adapter in first.rig_adapters.values()
    )
    counter = next(i for i in first.instructions if i.action == "heavy_punch")
    assert counter.clip_stack[0].clip_id == "heavy_cross"
    assert counter.clip_stack[0].contact_frame == 163
    assert counter.clip_stack[0].time_warp.attack_scale < 0.5
    assert counter.clip_stack[0].time_warp.impact_hold_frames == 3
    launch = next(i for i in first.instructions if i.action == "launch")
    assert launch.trajectory == "rotational_launch"
    assert launch.angular_momentum is not None
    assert digest(load_replay(replay_path)["frames"]) == frames


def test_action_library_and_directional_reaction_selection():
    assert set(CLIP_NAMES) == set(blender_runtime.CLIP_BLUEPRINTS)
    upward = choose_reaction(
        attack_family="uppercut", direction=(0, 0, 1), relative_power=0.9
    )
    body = choose_reaction(
        attack_family="kick", direction=(-1, 0, 0), relative_power=0.5
    )
    assert upward.launch_clip_id == "launch_upward"
    assert upward.family == "upward_launch"
    assert body.clip_id == "hit_body"
    assert body.launch_clip_id is None


def test_project_can_emit_self_contained_hybrid_scene(replay, tmp_path):
    source, _, _ = replay
    root = blender_project.create_project(source, tmp_path / "hybrid", hybrid=True)
    manifest, plan = blender_project.load_project(root)
    assert plan.schema_version == 3
    assert plan.action_library_version == "generic_humanoid_authored_v1"
    assert manifest.source_checksum == plan.source_checksum
    script = (root / "scene.py").read_text()
    assert "build_action_library" in script
    assert "add_nla_clip" in script
    assert "apply_hybrid_instruction" in script
