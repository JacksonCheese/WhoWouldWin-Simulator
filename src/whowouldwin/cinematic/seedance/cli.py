"""CLI entry points for local Seedance preparation and strict readiness checks."""

from pathlib import Path
from whowouldwin.combat.environment import Matchup
from .package import prepare, stage_shared_references, validate_package


COMMANDS = {"prepare-seedance", "episode-plan", "validate-seedance", "seedance-missing", "seedance-stage-refs"}


def register_commands(subs) -> None:
    for name in ("prepare-seedance", "episode-plan"):
        parser = subs.add_parser(name, help="Prepare a deterministic local short-shot package without calling Seedance")
        parser.add_argument("source", help="Replay JSON path or first fighter ID")
        parser.add_argument("opponent", nargs="?", help="Second fighter ID when source is a fighter ID")
        parser.add_argument("--seed", type=int, default=289)
        parser.add_argument("--duration", type=float, default=10)
        parser.add_argument("--shots", type=int, default=8)
        parser.add_argument("--fps", type=int, choices=(24, 30), default=30)
        parser.add_argument("--output", type=Path)
    for name in ("validate-seedance", "seedance-missing"):
        parser = subs.add_parser(name, help="Validate manual image references and report missing upload assets")
        parser.add_argument("project", type=Path)
    stage = subs.add_parser("seedance-stage-refs", help="Copy approved common images into each shot folder")
    stage.add_argument("project", type=Path)


def handle(args) -> int:
    if args.command == "seedance-stage-refs":
        result = stage_shared_references(args.project)
        print(f"Staged {result['staged_count']} valid common reference images; still missing/invalid: {result['validation']['missing_count']}")
        return 0 if result["validation"]["ready_for_manual_upload"] else 2
    if args.command in {"validate-seedance", "seedance-missing"}:
        status = validate_package(args.project)
        if status["issues"]:
            print(f"BLOCKED: {status['missing_count']} missing or invalid required items")
            for item in status["issues"]:
                print(f"  {item}")
            return 2
        print(f"READY for manual upload: {args.project.resolve()}; no provider calls made")
        return 0
    source = Path(args.source)
    if source.is_file():
        if args.opponent:
            raise ValueError("Opponent is not accepted when source is a replay file")
        selected = source
    else:
        if not args.opponent:
            raise ValueError("Supply a replay JSON or two fighter IDs")
        aliases = {"omni_man": "omniman", "omni-man": "omniman"}
        selected = Matchup(fighter_a=aliases.get(args.source, args.source),
                           fighter_b=aliases.get(args.opponent, args.opponent), seed=args.seed)
    project, status = prepare(selected, output=args.output, duration=args.duration,
                              shots=args.shots, fps=args.fps)
    print(f"Prepared: {project}")
    print(f"Canonical event SHA-256: {status['canonical_event_sha256']}")
    print(f"Replay checksum: {status['source_replay_checksum']}")
    print(f"Manual upload status: {'READY' if status['ready_for_manual_upload'] else 'BLOCKED'}; missing/invalid items: {status['missing_count']}")
    print(f"Review: {project / 'validation-summary.md'}")
    return 0
