"""CLI entry points for local Seedance preparation and strict readiness checks."""

from pathlib import Path
from whowouldwin.combat.environment import Matchup
from .package import prepare, stage_shared_references, validate_package


COMMANDS = {"prepare-seedance", "episode-plan", "prepare-seedance-longform", "finalize-seedance-longform", "validate-seedance", "seedance-missing", "seedance-stage-refs", "prepare-seedance25", "validate-seedance25"}


def register_commands(subs) -> None:
    seedance25 = subs.add_parser("prepare-seedance25", help="Build five flat-art Dreamina Seedance 2.5 sequence packages locally")
    seedance25.add_argument("--output", type=Path)
    seedance25.add_argument("--fps", type=int, default=15)
    seedance25_validate = subs.add_parser("validate-seedance25", help="Validate a local five-sequence Seedance 2.5 package")
    seedance25_validate.add_argument("project", type=Path)
    longform = subs.add_parser("prepare-seedance-longform", help="Build the 62-second image-backed seed-289 episode without a provider call")
    longform.add_argument("--source", type=Path)
    longform.add_argument("--assets", type=Path)
    longform.add_argument("--output", type=Path)
    finalize = subs.add_parser("finalize-seedance-longform", help="Audit the image-backed episode and repair only final-shot metadata")
    finalize.add_argument("project", type=Path)
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
    if args.command == "prepare-seedance25":
        from .seedance25 import DEFAULT_OUTPUT, build
        project, status = build(args.output or DEFAULT_OUTPUT, fps=args.fps)
        print(f"Prepared: {project}")
        print(f"Sequence 01 test: {'READY' if status['ready_for_sequence_01_test'] else 'BLOCKED'}")
        print(f"Sequences: {status['sequence_count']}; target length: {status['total_target_duration_seconds']}s")
        return 0 if status["ready_for_sequence_01_test"] else 2
    if args.command == "validate-seedance25":
        from .seedance25 import validate
        status = validate(args.project)
        print(f"Sequence 01 test: {'READY' if status['ready_for_sequence_01_test'] else 'BLOCKED'}")
        for issue in status["issues"]:
            print(f"  {issue}")
        return 0 if status["ready_for_sequence_01_test"] else 2
    if args.command == "finalize-seedance-longform":
        from .longform_seed289 import finalize_preupload
        status = finalize_preupload(args.project)
        print(f"Pre-upload status: {'READY' if status['ready_for_manual_upload'] else 'BLOCKED'}; issues: {status['missing_count']}")
        print(f"Audit: {args.project / 'review/preupload_audit.json'}")
        return 0 if status["ready_for_manual_upload"] else 2
    if args.command == "prepare-seedance-longform":
        from .longform_seed289 import prepare_longform
        root = Path(__file__).resolve().parents[4]
        assets = args.assets or root / "assets/seedance/seed289_60s"
        source = args.source or assets / "source_replay.json"
        output = args.output or root / "outputs/seedance_ready/naruto_vs_omniman_60s"
        project, status = prepare_longform(source, output, assets)
        print(f"Prepared: {project}")
        print(f"Canonical event SHA-256: {status['canonical_event_sha256']}")
        print(f"Manual upload status: {'READY' if status['ready_for_manual_upload'] else 'BLOCKED'}; invalid items: {status['missing_count']}")
        return 0 if status["ready_for_manual_upload"] else 2
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
