"""Run the four requested full-length sanity batches and save reviewable artifacts."""
import json
from pathlib import Path
from whowouldwin.combat.environment import Matchup
from whowouldwin.simulation.engine import Engine
from whowouldwin.simulation.monte_carlo import monte_carlo
from whowouldwin.simulation.replay import save_replay, verify_replay
from whowouldwin.analytics.reports import write_reports


def main():
    rows = []
    for fighter, opponent in [("naruto", "omniman"), ("aang", "homelander"), ("naruto", "aang"), ("omniman", "homelander")]:
        config = Matchup(fighter_a=fighter, fighter_b=opponent, seed=42)
        slug = f"{fighter}_vs_{opponent}"
        print(f"Running {slug}: 1,000 fights", flush=True)
        report, metrics = monte_carlo(config, 1000)
        assert report["event_counts"]["FightEnded"] == 1000
        assert all(f["average_damage_dealt"] > 0 for f in report["fighters"])
        assert report["duration"]["shortest"] < report["duration"]["longest"]
        assert report["duration"]["longest"] <= config.rules.timeout
        report["saved_replays"] = []
        for label, original in metrics.interesting.items():
            engine = Engine(config, seed=original["seed"], profiles=metrics.profiles, record=True)
            assert engine.run() == original
            path = save_replay(engine, Path("replays") / slug / f"{label}.json")
            assert verify_replay(path) == original
            report["saved_replays"].append(str(path))
            if slug == "naruto_vs_omniman":
                save_replay(engine, Path("replays") / f"{label}.json")
        write_reports(report, Path("reports") / slug, metrics.durations)
        row = {"matchup": slug, "wins": [f["wins"] for f in report["fighters"]], "draws": report["draws"],
               "median": report["duration"]["median"], "mean": report["duration"]["mean"],
               "shortest": report["duration"]["shortest"], "longest": report["duration"]["longest"],
               "performance": report["performance"], "conditions": report["conditions"],
               "attack_hit_rates": [{a["id"]: round(a["hit_rate"], 1) for a in f["abilities"] if a["hits"]} for f in report["fighters"]],
               "event_counts": report["event_counts"]}
        rows.append(row)
        print(json.dumps(row), flush=True)
    Path("reports/validation_summary.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
