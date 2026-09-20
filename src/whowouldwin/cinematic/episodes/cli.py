"""CLI coordination for the local shot pipeline; existing simulation commands remain intact."""

from pathlib import Path
import tempfile
from whowouldwin.combat.environment import Matchup
from whowouldwin.simulation.engine import Engine
from whowouldwin.simulation.replay import save_replay
from .project import (
    assemble_episode,
    direct_episode,
    load_episode,
    render_episode,
    set_shot_status,
    storyboard_episode,
)
from .schemas import DirectorSettings, SelectorSettings, ShotStatus

COMMANDS = {
    "direct",
    "storyboard",
    "approve-shot",
    "revise-shot",
    "render",
    "assemble",
    "create-video",
    "episode-status",
    "debug-view",
}


def direction_arguments(parser):
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--aspect", choices=["9:16", "16:9"], default="9:16")
    parser.add_argument("--shots", type=int, default=24)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--style", default=DirectorSettings().visual_style)
    parser.add_argument("--shake", type=float, default=0.65)
    parser.add_argument("--group-window", type=float, default=0.4)
    parser.add_argument("--minimum-score", type=float, default=0.23)
    parser.add_argument("--visual-profiles", type=Path)
    parser.add_argument("--arena-visual", type=Path)
    parser.add_argument("--provider-config", type=Path)
    parser.add_argument("--output", type=Path)


def register_commands(subs):
    direct = subs.add_parser(
        "direct",
        help="Select events and plan a versioned cinematic episode from a saved replay",
    )
    direct.add_argument("replay_path", type=Path)
    direction_arguments(direct)
    direct.add_argument("--representative", default="saved battle supplied by user")
    for command in ("storyboard", "assemble", "episode-status"):
        parser = subs.add_parser(
            command,
            help={
                "storyboard": "Generate local mock storyboard frames and contact sheet",
                "assemble": "Edit/mux current clips into the final video",
                "episode-status": "Show episode and per-shot approval status",
            }[command],
        )
        parser.add_argument("project", type=Path)
    approve = subs.add_parser(
        "approve-shot",
        help="Review storyboard status; approval is required by render unless explicitly overridden",
    )
    approve.add_argument("project", type=Path)
    approve.add_argument("shot_id", nargs="?")
    approve.add_argument("--all", action="store_true")
    approve.add_argument(
        "--status", choices=["APPROVED", "REJECTED", "DRAFT"], default="APPROVED"
    )
    revise = subs.add_parser(
        "revise-shot", help="Create a new version of one shot and invalidate its render"
    )
    revise.add_argument("project", type=Path)
    revise.add_argument("shot_id")
    revise.add_argument("--motion-prompt")
    revise.add_argument("--keyframe-prompt")
    render = subs.add_parser(
        "render", help="Render mock clips, using current approved storyboards"
    )
    render.add_argument("project", type=Path)
    render.add_argument("--mock", action="store_true")
    render.add_argument("--allow-draft", action="store_true")
    render.add_argument("--shot")
    create = subs.add_parser(
        "create-video",
        help="Run one real battle through the complete local mock video pipeline",
    )
    create.add_argument("fighter")
    create.add_argument("opponent")
    create.add_argument("--seed", type=int, default=69)
    create.add_argument(
        "--mock",
        "--dry-run",
        action="store_true",
        dest="mock",
        help="Explicitly preview draft shots with local mocks; approval bypass is recorded",
    )
    direction_arguments(create)
    debug = subs.add_parser(
        "debug-view", help="Launch the preserved Pygame simulation debugger"
    )
    debug.add_argument("--replay", type=Path)
    debug.add_argument("--fighter", default="naruto")
    debug.add_argument("--opponent", default="omniman")
    debug.add_argument("--seed", type=int, default=42)


def settings(args):
    a, b = map(int, args.aspect.split(":"))
    width = args.width or (1080 if a < b else 1920)
    height = args.height or round(width * b / a / 2) * 2
    return DirectorSettings(
        duration_seconds=args.duration,
        aspect_ratio=args.aspect,
        shot_count=args.shots,
        fps=args.fps,
        width=width,
        height=height,
        visual_style=args.style,
        screen_shake=args.shake,
    )


def progress(stage):
    def report(done, total):
        if done == 1 or done == total or done % 4 == 0:
            print(f"{stage}: {done}/{total}", flush=True)

    return report


def handle(args) -> int:
    command = args.command
    if command == "debug-view":
        from whowouldwin.visual.app import main

        return main(
            ["--replay", str(args.replay)]
            if args.replay
            else [
                "--fighter",
                args.fighter,
                "--opponent",
                args.opponent,
                "--seed",
                str(args.seed),
            ]
        )
    if command == "direct":
        project = direct_episode(
            args.replay_path,
            args.output,
            settings=settings(args),
            selector_settings=SelectorSettings(
                group_window=args.group_window, minimum_score=args.minimum_score
            ),
            visual_directory=args.visual_profiles,
            arena_path=args.arena_visual,
            provider_config=args.provider_config,
            representative=args.representative,
        )
        print(f'Directed: {project}\nNext: wws storyboard "{project}"')
        return 0
    if command == "create-video":
        if not args.mock:
            raise ValueError(
                "Only local mock generation is implemented. Add --mock; no live providers are connected"
            )
        selected_settings = settings(args)
        aliases = {"omni_man": "omniman", "omni-man": "omniman"}
        config = Matchup(
            fighter_a=aliases.get(args.fighter, args.fighter),
            fighter_b=aliases.get(args.opponent, args.opponent),
            seed=args.seed,
        )
        staging = args.output.parent if args.output else Path("outputs")
        staging.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".simulation-", dir=staging
        ) as directory:
            engine = Engine(config, record=True)
            result = engine.run()
            source = save_replay(engine, Path(directory) / "simulation.json")
            project = direct_episode(
                source,
                args.output,
                settings=selected_settings,
                selector_settings=SelectorSettings(
                    group_window=args.group_window, minimum_score=args.minimum_score
                ),
                visual_directory=args.visual_profiles,
                arena_path=args.arena_visual,
                provider_config=args.provider_config,
                representative="single seeded battle; no statistical representative selection claimed",
            )
        print(
            f"Simulation: seed {args.seed}, {result['duration']:.2f}s, winner slot {result['winner']}; source preserved",
            flush=True,
        )
        storyboard_episode(project, progress("Storyboard"))
        render_episode(project, allow_draft=True, progress=progress("Mock clips"))
        output = assemble_episode(project)
        print(
            f'Complete mock video: {output}\nManifest: {project / "manifest.json"}\nPaid API calls: 0. Cost: $0. Draft-preview approval override recorded.'
        )
        return 0
    project = args.project.resolve()
    if command == "storyboard":
        print(storyboard_episode(project, progress("Storyboard")))
    elif command == "approve-shot":
        if not args.all and not args.shot_id:
            raise ValueError(
                "Specify a shot ID or --all after reviewing the storyboard"
            )
        set_shot_status(
            project, "all" if args.all else args.shot_id, ShotStatus(args.status)
        )
        print(f"Status saved: {args.status}")
    elif command == "revise-shot":
        set_shot_status(
            project,
            args.shot_id,
            ShotStatus.NEEDS_REGENERATION,
            motion_prompt=args.motion_prompt,
            keyframe_prompt=args.keyframe_prompt,
        )
        print(
            "Shot version advanced. Run storyboard, review/approve this shot, then render --mock --shot "
            + args.shot_id
        )
    elif command == "render":
        if not args.mock:
            raise ValueError(
                "Only mock providers are implemented; explicitly add --mock"
            )
        paths = render_episode(
            project,
            allow_draft=args.allow_draft,
            shot_id=args.shot,
            progress=progress("Mock clips"),
        )
        print(f"Current clips: {len(paths)}")
    elif command == "assemble":
        print(assemble_episode(project))
    elif command == "episode-status":
        manifest, shots = load_episode(project)
        print(
            f"{manifest.episode_id}: {manifest.stage}\nSeed {manifest.simulation_seed}; {len(shots.shots)} shots; {shots.settings.duration_seconds}s; cost ${manifest.actual_cost_usd:.2f}"
        )
        for shot in shots.shots:
            print(
                f"{shot.shot_id} v{shot.version} {shot.status.value:20} {shot.shot_type.value:18} {shot.duration_seconds:.2f}s"
            )
    return 0
