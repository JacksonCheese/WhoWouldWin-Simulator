"""CLI commands for character-package inspection and mapping assistance."""

from __future__ import annotations

import json
from pathlib import Path

from whowouldwin.cinematic.episodes.project import write_json

from .package import load_character_package
from .rig_mapping import suggest_rig_mapping
from .validation import validate_character_package


COMMANDS = {"validate-character", "suggest-rig-map"}


def register_commands(subs) -> None:
    validate = subs.add_parser(
        "validate-character",
        help="Validate a production CharacterPackage and inspect its Blender asset",
    )
    validate.add_argument("package", type=Path)
    validate.add_argument("--blender", type=Path)
    validate.add_argument("--skip-blender", action="store_true")
    validate.add_argument("--json", type=Path)

    suggest = subs.add_parser(
        "suggest-rig-map",
        help="Suggest a standard humanoid bone map without accepting ambiguous matches",
    )
    suggest.add_argument("package", type=Path)
    suggest.add_argument("--blender", type=Path)
    suggest.add_argument("--output", type=Path)


def _print_report(report) -> None:
    state = "VALID" if report.valid else "INVALID"
    print(f"{state}: {report.character_id or 'unknown'} ({report.package_root})")
    for issue in report.errors:
        print(f"ERROR {issue.code}: {issue.message}")
        if issue.suggestion:
            print(f"  Fix: {issue.suggestion}")
    for issue in report.warnings:
        print(f"WARNING {issue.code}: {issue.message}")
    for name, value in sorted(report.checks.items()):
        print(f"  {name}: {value}")


def handle(args) -> int:
    report = validate_character_package(
        args.package,
        blender=args.blender,
        inspect_blender=not getattr(args, "skip_blender", False),
    )
    if args.command == "validate-character":
        _print_report(report)
        if args.json:
            write_json(args.json, report)
        return 0 if report.valid else 1
    if not report.blender.get("bone_names"):
        _print_report(report)
        raise ValueError("Rig mapping requires a successful Blender armature inspection")
    package = load_character_package(args.package)
    proposal = suggest_rig_mapping(
        report.blender["bone_names"], package.manifest.armature
    )
    output = args.output or Path(package.root) / "rig_adapter.proposed.json"
    write_json(output, proposal)
    print(f"Proposed rig map: {output}")
    print(
        "Manual review required: "
        + ("yes" if proposal.manual_review_required else "no")
    )
    if proposal.unresolved_required_roles:
        print("Unresolved: " + ", ".join(proposal.unresolved_required_roles))
    return 0

