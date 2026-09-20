"""Explicit small-sequence commands. Mock selection never consults Runway credentials."""

import json
from pathlib import Path
from . import project

COMMANDS = {
    "golden-sequence",
    "golden-references",
    "golden-estimate",
    "golden-keyframes",
    "approve-keyframes",
    "golden-animate",
    "golden-assemble",
    "golden-trim",
    "golden-link-task",
}


def register_commands(subs):
    p = subs.add_parser(
        "golden-sequence",
        help="Plan 4–8 coverage shots from a real episode; --mock creates a local preview",
    )
    p.add_argument("episode", type=Path)
    p.add_argument("--output", type=Path, default=Path("outputs/golden_sequence"))
    p.add_argument("--duration", type=float, default=10)
    p.add_argument("--shots", type=int, default=7)
    p.add_argument("--width", type=int, default=720)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--start-time", type=float)
    p.add_argument("--end-time", type=float)
    p.add_argument("--start-moment")
    p.add_argument("--end-moment")
    p.add_argument(
        "--mock",
        action="store_true",
        help="Complete a local mock preview; does not approve keyframes",
    )
    p = subs.add_parser(
        "golden-references",
        help="Validate/package local character and style/arena references",
    )
    p.add_argument("project", type=Path)
    p.add_argument("--directory", type=Path)
    p.add_argument("--approve", action="store_true")
    p = subs.add_parser(
        "golden-estimate",
        help="Show the generation price estimate without network calls",
    )
    p.add_argument("project", type=Path)
    p.add_argument("--image-model", default="gen4_image_turbo")
    p.add_argument("--video-model", default="gen4_turbo")
    p.add_argument("--generation-seconds", type=int, default=5)
    for command in ["golden-keyframes", "golden-animate"]:
        p = subs.add_parser(
            command,
            help="Generate only "
            + (
                "keyframes; stop for review"
                if command == "golden-keyframes"
                else "video from approved keyframes"
            ),
        )
        p.add_argument("project", type=Path)
        p.add_argument("--provider", choices=["mock", "runway"], default="mock")
        p.add_argument("--real", action="store_true")
        p.add_argument(
            "--max-cost",
            type=float,
            help="Cumulative sequence USD cap, including prior and unresolved jobs",
        )
        p.add_argument(
            "--model",
            default=(
                "gen4_image_turbo" if command == "golden-keyframes" else "gen4_turbo"
            ),
        )
        p.add_argument("--shot")
        p.add_argument(
            "--retry-failed",
            action="store_true",
            help="Explicitly permit another paid task after a known failure, within cap",
        )
        if command == "golden-keyframes":
            p.add_argument(
                "--regenerate",
                action="store_true",
                help="New version of exactly --shot; invalidates its approval and clip",
            )
        else:
            p.add_argument("--generation-seconds", type=int, default=5)
            p.add_argument(
                "--allow-draft",
                action="store_true",
                help="Mock preview only; forbidden for real animation",
            )
    p = subs.add_parser(
        "approve-keyframes",
        help="Approve the exact current keyframe bytes before animation",
    )
    p.add_argument("project", type=Path)
    p.add_argument("--shot")
    p.add_argument("--all", action="store_true")
    p.add_argument("--reject", action="store_true")
    p = subs.add_parser(
        "golden-assemble", help="Trim full clips and assemble the short vertical edit"
    )
    p.add_argument("project", type=Path)
    p = subs.add_parser(
        "golden-trim",
        help="Select a better interval from a full clip; never regenerates",
    )
    p.add_argument("project", type=Path)
    p.add_argument("--shot", required=True)
    p.add_argument("--in-seconds", type=float, required=True)
    p = subs.add_parser(
        "golden-link-task",
        help="Recover a lost submission response using an exact known task ID; no API call",
    )
    p.add_argument("project", type=Path)
    p.add_argument("--job", required=True)
    p.add_argument("--task-id", required=True)


def handle(args):
    c = args.command
    if c == "golden-sequence":
        output = project.create_sequence(
            args.episode,
            args.output,
            duration=args.duration,
            shots=args.shots,
            width=args.width,
            fps=args.fps,
            start_time=args.start_time,
            end_time=args.end_time,
            start_moment=args.start_moment,
            end_moment=args.end_moment,
        )
        print(f"Golden plan: {output}", flush=True)
        if args.mock:
            project.keyframes(output)
            project.animate(output, allow_draft=True)
            print(project.assemble(output))
        print(json.dumps(project.estimate(output), indent=2))
        return 0
    root = args.project.resolve()
    if c == "golden-references":
        project.references(root, args.directory, approve=args.approve)
    elif c == "golden-estimate":
        print(
            json.dumps(
                project.estimate(
                    root, args.image_model, args.video_model, args.generation_seconds
                ),
                indent=2,
            )
        )
    elif c == "golden-keyframes":
        project.keyframes(
            root,
            provider=args.provider,
            real=args.real,
            max_cost=args.max_cost,
            model=args.model,
            shot_id=args.shot,
            regenerate_one=args.regenerate,
            retry_failed=args.retry_failed,
        )
        print(f'Review {root / "contact-sheet.png"}; animation has not been started.')
    elif c == "approve-keyframes":
        if not args.all and not args.shot:
            raise ValueError("Specify --shot or --all after reviewing the keyframes")
        if args.all and args.shot:
            raise ValueError("Choose either --all or --shot")
        project.approve_keyframes(root, args.shot, reject=args.reject)
    elif c == "golden-animate":
        project.animate(
            root,
            provider=args.provider,
            real=args.real,
            max_cost=args.max_cost,
            model=args.model,
            seconds=args.generation_seconds,
            shot_id=args.shot,
            allow_draft=args.allow_draft,
            retry_failed=args.retry_failed,
        )
    elif c == "golden-assemble":
        print(project.assemble(root))
    elif c == "golden-trim":
        project.trim(root, args.shot, args.in_seconds)
    elif c == "golden-link-task":
        project.link_task(root, args.job, args.task_id)
    return 0
