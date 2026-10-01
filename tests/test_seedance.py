"""Source truth, reproducibility, continuity and missing-art gates for Seedance prep."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
from PIL import Image

import pytest

from whowouldwin.cinematic.seedance import package as seedance_package
from whowouldwin.cinematic.seedance.planning import adapt_beats, ability_specs, direct, load_bibles
from whowouldwin.cli.main import main
from whowouldwin.combat.environment import Matchup
from whowouldwin.simulation.engine import Engine
from whowouldwin.simulation.replay import digest, load_replay, save_replay, verify_replay


@pytest.fixture
def replay_file(tmp_path):
    engine = Engine(Matchup(seed=289), record=True)
    expected = engine.run()
    path = save_replay(engine, tmp_path / "fight.json")
    return path, expected


def _tree_hashes(folder: Path):
    return {str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in folder.rglob("*") if path.is_file()}


def test_beats_and_plans_are_deterministic_and_canonical(replay_file):
    path, result = replay_file
    replay = load_replay(path)
    before = path.read_bytes()
    first, beats, specs = direct(replay)
    second, again, _ = direct(load_replay(path))
    assert first.model_dump() == second.model_dump()
    assert [beat.model_dump() for beat in beats] == [beat.model_dump() for beat in again]
    assert len(beats) == sum(len(frame["events"]) for frame in replay["frames"])
    assert first.canonical_event_sha256 == digest([event for frame in replay["frames"] for event in frame["events"]])
    assert first.outcome == result == verify_replay(path)
    assert path.read_bytes() == before
    assert all(shot.seedance_prompt and shot.negative_prompt and shot.required_reference_images for shot in first.shots)
    assert all(left.continuity_end == right.continuity_start for left, right in zip(first.shots, first.shots[1:]))
    assert all(0.5 <= shot.duration_seconds <= 3 for shot in first.shots)
    assert 6 <= len(first.shots) <= 12
    assert "finisher" in first.shots[-2].action_description.lower() or first.shots[-2].source_simulation_time <= result["duration"]
    assert set(specs) == {f"{c['identity']['id']}:{a['id']}" for c in replay["characters"] for a in c["abilities"]}


def test_all_supported_bibles_load():
    bibles = load_bibles(["naruto", "omniman", "aang", "homelander"])
    assert all(bible.required_views == ["front", "side", "three_quarter"] for bible in bibles.values())
    assert "blond" in bibles["naruto"].face_and_hair_anchors[0].lower()
    root = Path(__file__).resolve().parents[1]
    for name in bibles:
        assert (root / f"data/seedance_visual_bibles/{name}.json").read_bytes() == (
            root / f"src/whowouldwin/data/seedance_visual_bibles/{name}.json").read_bytes()


def test_package_reproduces_exactly_and_flags_missing_art(tmp_path, monkeypatch, replay_file):
    monkeypatch.setattr(seedance_package, "REFERENCE_VIDEOS", ())
    replay_path, _ = replay_file
    output = tmp_path / "episode"
    project, status = seedance_package.prepare(replay_path, output=output)
    assert project == output.resolve()
    assert status["ready_for_manual_upload"] is False
    assert any("character_references" in issue for issue in status["issues"])
    assert any("first_frame/approved.png" in issue for issue in status["issues"])
    shot = output / "shots/shot_001"
    assert (shot / "first_frame/blocking.svg").is_file()
    assert not (shot / "character_references/naruto_front.png").exists()
    manifest = json.loads((shot / "upload_manifest.json").read_text())
    assert all(not Path(name).is_absolute() for name in manifest["required_upload_images"])
    batch = json.loads((output / "seedance_batch_manifest.json").read_text())
    assert Path(batch["package_root_absolute"]).is_absolute()
    assert all(not Path(item["relative_shot_directory"]).is_absolute() for item in batch["shots"])
    hashes = _tree_hashes(output)
    shutil.rmtree(output)
    _, regenerated = seedance_package.prepare(replay_path, output=output)
    assert regenerated == status
    assert _tree_hashes(output) == hashes


def test_bad_art_does_not_pass_and_active_cli_needs_no_blender(tmp_path, monkeypatch, replay_file):
    monkeypatch.setattr(seedance_package, "REFERENCE_VIDEOS", ())
    path, _ = replay_file
    output = tmp_path / "episode"
    monkeypatch.setitem(sys.modules, "bpy", None)
    assert main(["prepare-seedance", str(path), "--output", str(output)]) == 0
    fake = output / "shots/shot_001/character_references/naruto_front.png"
    fake.write_bytes(b"not a valid image" * 4)
    assert seedance_package.validate_package(output)["ready_for_manual_upload"] is False
    assert main(["seedance-missing", str(output)]) == 2


def test_continuity_violation_is_rejected(tmp_path, monkeypatch, replay_file):
    monkeypatch.setattr(seedance_package, "REFERENCE_VIDEOS", ())
    path, _ = replay_file
    output, _ = seedance_package.prepare(path, output=tmp_path / "episode")
    plan_path = output / "episode_plan.json"
    plan = json.loads(plan_path.read_text())
    plan["shots"][0]["continuity_end"]["camera_side"] = "north side, reversed"
    plan["shots"][1]["continuity_start"]["camera_side"] = "north side, reversed"
    plan_path.write_text(json.dumps(plan))
    status = seedance_package.validate_package(output, write=False)
    assert any("camera crossed the action axis" in issue for issue in status["issues"])


def test_approved_image_files_can_complete_the_manual_gate(tmp_path, monkeypatch, replay_file):
    monkeypatch.setattr(seedance_package, "REFERENCE_VIDEOS", ())
    path, _ = replay_file
    output, status = seedance_package.prepare(path, output=tmp_path / "episode")
    assert not status["ready_for_manual_upload"]
    for shot in status["shots"]:
        folder = output / shot["relative_shot_directory"]
        for name in shot["required_upload_images"]:
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (12, 12), (100, 50, 25)).save(target)
    # Tiny generated images exercise validation only; they are not production art.
    assert seedance_package.validate_package(output)["ready_for_manual_upload"]


def test_shared_references_stage_only_valid_user_images(tmp_path, monkeypatch, replay_file):
    monkeypatch.setattr(seedance_package, "REFERENCE_VIDEOS", ())
    path, _ = replay_file
    output, _ = seedance_package.prepare(path, output=tmp_path / "episode")
    source = output / "shared_references/character_references/naruto_front.png"
    Image.new("RGB", (12, 12), (100, 50, 25)).save(source)
    staged = seedance_package.stage_shared_references(output)
    assert staged["staged_count"] == 8
    assert all((output / f"shots/shot_{index:03d}/character_references/naruto_front.png").is_file()
               for index in range(1, 9))
    assert not staged["validation"]["ready_for_manual_upload"]
