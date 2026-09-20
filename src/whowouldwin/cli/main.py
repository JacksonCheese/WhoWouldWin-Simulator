import argparse
import json
from pathlib import Path
import sys
import yaml
from whowouldwin.characters.validator import validate_directory
from whowouldwin.combat.environment import Matchup
from whowouldwin.simulation.engine import Engine
from whowouldwin.simulation.monte_carlo import monte_carlo
from whowouldwin.simulation.replay import save_replay, verify_replay, load_replay
from whowouldwin.analytics.reports import console_report, write_reports


def add_matchup_arguments(parser):
    parser.add_argument("--matchup", type=Path)
    parser.add_argument("--fighter")
    parser.add_argument("--opponent")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--timestep", type=float)
    parser.add_argument("--starting-distance", type=float)
    parser.add_argument("--width", type=float)
    parser.add_argument("--height", type=float)
    parser.add_argument("--scaling-a", choices=["low", "expected", "high"])
    parser.add_argument("--scaling-b", choices=["low", "expected", "high"])
    parser.add_argument(
        "--bloodlusted", action=argparse.BooleanOptionalAction, default=None
    )
    parser.add_argument("--lethal", action=argparse.BooleanOptionalAction, default=None)


def config_from_args(args) -> Matchup:
    data = yaml.safe_load(args.matchup.read_text()) if args.matchup else {}
    if not isinstance(data, dict):
        raise ValueError("Matchup must be a mapping")
    for field, flag in (
        ("fighter_a", "fighter"),
        ("fighter_b", "opponent"),
        ("seed", "seed"),
        ("starting_distance", "starting_distance"),
    ):
        if getattr(args, flag) is not None:
            data[field] = getattr(args, flag)
    for section, fields in {
        "rules": ("timeout", "timestep", "bloodlusted", "lethal"),
        "arena": ("width", "height"),
    }.items():
        for field in fields:
            if getattr(args, field) is not None:
                data.setdefault(section, {})[field] = getattr(args, field)
    for slot in "ab":
        value = getattr(args, f"scaling_{slot}")
        if value is not None:
            data.setdefault("scaling", {})[f"fighter_{slot}"] = value
    return Matchup.model_validate(data)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="WhoWouldWin · deterministic combat, reports and replay"
    )
    subs = parser.add_subparsers(dest="command", required=True)
    sim = subs.add_parser("simulate", help="Run one or many autonomous battles")
    add_matchup_arguments(sim)
    sim.add_argument("--runs", type=int, default=1)
    sim.add_argument(
        "--workers",
        type=int,
        default=1,
        help="0 = auto, default = 1; seeds are worker-independent",
    )
    sim.add_argument("--output", type=Path)
    sim.add_argument("--no-charts", action="store_true")
    sim.add_argument("--quiet", action="store_true")
    sim.add_argument("--save-interesting", action="store_true")
    sim.add_argument("--replay-dir", type=Path, default=Path("replays"))
    sim.add_argument(
        "--save-replay", type=Path, help="Save the single battle (requires --runs 1)"
    )
    sim.add_argument(
        "--debug-ai",
        action="store_true",
        help="Print chosen score components for one fight",
    )
    replay = subs.add_parser(
        "replay", help="Verify a replay against its seed and embedded profiles"
    )
    replay.add_argument("path", type=Path)
    replay.add_argument("--visual", action="store_true")
    validation = subs.add_parser("validate", help="Validate every character document")
    validation.add_argument("--directory", type=Path)
    export = subs.add_parser(
        "export-unity",
        help="Compile an authoritative replay into a Unity cinematic timeline",
    )
    export.add_argument("path", type=Path)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument(
        "--profiles", type=Path, help="Optional presentation mapping directory"
    )
    from whowouldwin.cinematic.episodes.cli import register_commands, handle, COMMANDS

    register_commands(subs)
    from whowouldwin.cinematic.golden.cli import (
        register_commands as golden_register,
        handle as golden_handle,
        COMMANDS as GOLDEN_COMMANDS,
    )

    golden_register(subs)
    from whowouldwin.cinematic.blender_backend.cli import (
        COMMANDS as BLENDER_COMMANDS,
        handle as blender_handle,
        register_commands as blender_register,
    )

    blender_register(subs)
    from whowouldwin.cinematic.assets.cli import (
        COMMANDS as ASSET_COMMANDS,
        handle as asset_handle,
        register_commands as asset_register,
    )

    asset_register(subs)
    args = parser.parse_args(argv)
    try:
        if args.command in ASSET_COMMANDS:
            return asset_handle(args)
        if args.command in GOLDEN_COMMANDS:
            return golden_handle(args)
        if args.command in BLENDER_COMMANDS:
            return blender_handle(args)
        if args.command in COMMANDS:
            return handle(args)
        if args.command == "export-unity":
            from whowouldwin.cinematic.exporter import export_unity

            cinematic = export_unity(
                args.path, args.output, profile_directory=args.profiles
            )
            print(
                f"Exported {args.output}: {cinematic['metadata']['simulationDuration']:.2f}s combat, "
                f"{cinematic['metadata']['presentationDuration']:.2f}s presentation, "
                f"{len(cinematic['cues'])} choreography cues; authoritative outcome preserved"
            )
            return 0
        if args.command == "validate":
            print("Validated: " + ", ".join(validate_directory(args.directory)))
            return 0
        if args.command == "replay":
            if args.visual:
                from whowouldwin.visual.app import main as visual_main

                return visual_main(["--replay", str(args.path)])
            result = verify_replay(args.path)
            print(
                f"Replay verified: seed {result['seed']}, {result['duration']:.2f}s, winner slot {result['winner']}, {result['condition']}"
            )
            return 0
        if (args.save_replay or args.debug_ai) and args.runs != 1:
            raise ValueError("--save-replay and --debug-ai require --runs 1")
        config = config_from_args(args)

        def progress(done, total):
            if not args.quiet:
                print(
                    f"\rSimulating {done:,}/{total:,} ({100 * done / total:.0f}%)",
                    end="",
                    file=sys.stderr,
                    flush=True,
                )

        report, metrics = monte_carlo(
            config, args.runs, workers=args.workers, progress=progress
        )
        if not args.quiet:
            print(file=sys.stderr)
        selections = dict(metrics.interesting) if args.save_interesting else {}
        paths = []
        if args.save_replay or args.debug_ai:
            engine = Engine(config, profiles=metrics.profiles, record=True)
            engine.run()
            if args.save_replay:
                paths.append(save_replay(engine, args.save_replay))
            if args.debug_ai:
                for frame in engine.frames:
                    for event in frame["events"]:
                        if event["type"] == "ActionChosen":
                            print(
                                f"{event['timestamp']:6.2f}s slot {event['fighter']} {event['action']}: {json.dumps(event['values']['utility'])}"
                            )
        for label, result in selections.items():
            engine = Engine(
                config, seed=result["seed"], profiles=metrics.profiles, record=True
            )
            if engine.run() != result:
                raise RuntimeError(
                    "Representative replay differs from Monte Carlo result"
                )
            paths.append(save_replay(engine, args.replay_dir / f"{label}.json"))
        report["saved_replays"] = [str(p) for p in paths]
        directory = (
            args.output
            or Path("reports")
            / f"{metrics.profiles[0].identity.id}_vs_{metrics.profiles[1].identity.id}"
        )
        files = write_reports(
            report, directory, metrics.durations, charts=not args.no_charts
        )
        print(console_report(report))
        print(
            f"\nCompleted in {report['performance']['wall_seconds']:.2f}s ({report['performance']['fights_per_second']:.1f} fights/sec)"
        )
        print("Reports: " + ", ".join(str(p) for p in files))
        if paths:
            print("Saved: " + ", ".join(str(p) for p in paths))
        if args.save_interesting and "upset" not in selections:
            print(
                "No upset replay: this batch has no winning minority (or wins are tied)."
            )
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(2, f"Error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
