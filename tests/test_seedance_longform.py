"""The editorial expansion must preserve the short authoritative seed-289 fight."""

from pathlib import Path

from whowouldwin.cinematic.seedance.longform_seed289 import (
    CAMERA_FAMILIES, EVENT_SHA, SOURCE_CHECKSUM, build_plan, prepare_longform,
)
from whowouldwin.cinematic.seedance.package import validate_package
from whowouldwin.simulation.replay import load_replay


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/seedance/seed289_60s"


def test_seed289_directed_plan_is_varied_and_source_locked():
    replay = load_replay(ASSETS / "source_replay.json")
    plan, beats = build_plan(replay)
    assert plan.source_checksum == SOURCE_CHECKSUM
    assert plan.canonical_event_sha256 == EVENT_SHA
    assert plan.outcome == replay["result"]
    assert plan.duration_seconds == 62
    assert len(plan.shots) == len(CAMERA_FAMILIES) == 28
    assert len({family for family in CAMERA_FAMILIES}) >= 12
    assert "overhead" in CAMERA_FAMILIES
    assert "over-shoulder projectile" in CAMERA_FAMILIES
    assert "perpendicular side impact" in CAMERA_FAMILIES
    assert "oblique contact close-up" in CAMERA_FAMILIES
    assert len(beats) == sum(len(frame["events"]) for frame in replay["frames"])
    assert [s.source_simulation_time for s in plan.shots] == sorted(s.source_simulation_time for s in plan.shots)
    assert all(left.ending_pose == right.starting_pose for left, right in zip(plan.shots, plan.shots[1:]))
    assert "straight ranged pellet" in plan.shots[12].seedance_prompt
    assert "No spiral orb" in plan.shots[12].negative_prompt
    for shot in plan.shots[21:26]:
        assert "noncanonical" in shot.editorial_note
        assert "never becomes a projectile" in shot.seedance_prompt or "Rasengan" in shot.action_description
        assert "No Rasengan hit" in shot.negative_prompt
    assert "heavy strike" in plan.shots[25].action_description


def test_image_backed_longform_package_validates(tmp_path):
    source = ASSETS / "source_replay.json"
    project, status = prepare_longform(source, tmp_path / "episode", ASSETS)
    assert status["ready_for_manual_upload"], status["issues"]
    assert status["missing_count"] == 0
    assert status["provider_calls"] == 0
    assert len(list(project.glob("shots/*/keyframe.png"))) == 28
    assert (project / "review/keyframe_camera_contact_sheet.jpg").is_file()
    assert "perpendicular side impact" in (project / "camera_grammar.md").read_text()
    assert (project / "shots/shot_013/ability_references/naruto_energy_orb.png").read_bytes() == (
        ASSETS / "energy-orb-straight.png").read_bytes()
    assert validate_package(project, write=False)["ready_for_manual_upload"]
    assert (project / "simulation.json").read_bytes() == source.read_bytes()
