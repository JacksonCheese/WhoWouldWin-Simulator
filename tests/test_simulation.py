import json
import csv
import subprocess
import sys
import pytest
from whowouldwin.simulation.engine import Engine
from whowouldwin.simulation.monte_carlo import monte_carlo
from whowouldwin.simulation.replay import save_replay, load_replay, verify_replay, ReplayPlayer
from whowouldwin.combat.environment import Matchup
from whowouldwin.analytics.reports import write_reports


def test_same_seed_identical_events_and_states(profiles):
    first = Engine(seed=12345, profiles=profiles[:2], record=True)
    second = Engine(seed=12345, profiles=profiles[:2], record=True)
    assert first.run() == second.run()
    assert first.frames == second.frames
    fast = Engine(seed=12345, profiles=profiles[:2])
    assert fast.run() == first.result()
    assert not fast.frames


def test_different_seeds_can_diverge(profiles):
    results = [Engine(seed=s, profiles=profiles[:2]).run() for s in range(5)]
    assert len({r["duration"] for r in results}) > 1
    assert len({r["fighters"][1]["health"] for r in results}) > 1


def test_replay_is_self_contained_and_exact(tmp_path, profiles):
    e = Engine(seed=51, profiles=profiles[:2], record=True)
    result = e.run()
    path = save_replay(e, tmp_path / "fight.json")
    assert verify_replay(path) == result
    data = load_replay(path)
    player = ReplayPlayer(data)
    while not player.frame["state"]["done"]:
        player.step()
    assert player.frame["state"] == json.loads(json.dumps(e.world.snapshot()))
    player.restart()
    assert player.frame["state"]["tick"] == 0
    # All required interpretation data travels with the replay.
    assert len(data["characters"]) == 2
    assert data["frames"][0]["events"][0]["type"] == "FightStarted"


def test_replay_detects_corruption(tmp_path):
    e = Engine(Matchup(rules={"timeout": .1}), record=True)
    e.run()
    path = save_replay(e, tmp_path / "corrupt.json")
    raw = json.loads(path.read_text())
    raw["seed"] += 1
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="checksum"):
        load_replay(path)


def test_parallel_seed_schedule_matches_serial():
    config = Matchup(seed=100)
    serial, _ = monte_carlo(config, 20, workers=1)
    parallel, _ = monte_carlo(config, 20, workers=2)
    serial.pop("performance"); parallel.pop("performance")
    assert serial == parallel


def test_utility_debug_and_ability_variety(profiles):
    e = Engine(seed=42, profiles=profiles[:2], record=True)
    e.run()
    decisions = [event for frame in e.frames for event in frame["events"] if event["type"] == "ActionChosen"]
    assert {event["fighter"] for event in decisions} == {0, 1}
    assert len({event["action"] for event in decisions}) >= 8
    assert all("final" in event["values"]["utility"] and "resource" in event["values"]["utility"] for event in decisions)


@pytest.mark.slow
def test_thousand_fight_monte_carlo_smoke():
    report, metrics = monte_carlo(Matchup(), 1000)
    assert sum(f["wins"] for f in report["fighters"]) + report["draws"] == 1000
    assert len(metrics.durations) == 1000
    assert sum(report["duration"]["histogram"]["counts"]) == 1000
    assert 0 < report["duration"]["shortest"] <= report["duration"]["longest"] <= 180
    assert report["event_counts"]["FightEnded"] == 1000
    for name in ("AttackHit", "ProjectileSpawned", "AttackDodged", "AttackBlocked", "FlightStarted", "TransformationActivated", "Knockback"):
        assert report["event_counts"][name] > 0
    assert all(f["average_damage_dealt"] > 0 for f in report["fighters"])
    assert report["fighters"][0]["average_damage_dealt"] == pytest.approx(report["fighters"][1]["average_damage_received"])


def test_cli_reports_and_visual_replay(tmp_path):
    path = tmp_path / "fight.json"
    output = tmp_path / "reports"
    run = subprocess.run([sys.executable, "-m", "whowouldwin.cli.main", "simulate", "--runs", "1", "--seed", "51",
                          "--save-replay", str(path), "--output", str(output), "--quiet"], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    for filename in ("report.json", "report.txt", "summary.csv", "durations.csv", "win_percentage.png", "fight_durations.png", "finishing_methods.png"):
        assert (output / filename).stat().st_size > 0
    with (output / "durations.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1 and rows[0]["seed"] == "51"
    assert float(rows[0]["duration_seconds"]) > 0
    verification = subprocess.run([sys.executable, "-m", "whowouldwin.cli.main", "replay", str(path)], capture_output=True, text=True)
    assert verification.returncode == 0, verification.stderr
    screenshot = tmp_path / "visual.png"
    view = subprocess.run([sys.executable, "-m", "whowouldwin.visual.app", "--replay", str(path), "--headless", "--auto-quit", "--speed", "4", "--screenshot", str(screenshot)], capture_output=True, text=True, timeout=120)
    assert view.returncode == 0, view.stderr
    assert screenshot.stat().st_size > 1000
    assert "condition=ko" in view.stdout


def test_visual_live_engine_completes(tmp_path):
    screenshot = tmp_path / "live.png"
    replay = tmp_path / "visual-live.json"
    view = subprocess.run([sys.executable, "-m", "whowouldwin.visual.app", "--headless", "--auto-quit", "--seed", "42", "--speed", "4", "--save-replay", str(replay), "--screenshot", str(screenshot)], capture_output=True, text=True, timeout=120)
    assert view.returncode == 0, view.stderr
    assert screenshot.stat().st_size > 1000
    assert verify_replay(replay) == Engine(seed=42).run()
