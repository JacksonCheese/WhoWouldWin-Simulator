"""CLI for deterministic Blender planning and rendering."""

from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from .project import command_preview, create_project, render_project

COMMANDS = {
    "blender-plan", "render-blender", "render-motion-debug", "render-motion-review"
}


def register_commands(subs):
    plan = subs.add_parser(
        "blender-plan",
        help="Compile an event log/replay/episode into a generic 3D proof sequence",
    )
    plan.add_argument("source", type=Path)
    plan.add_argument("--output", type=Path, default=Path("outputs/blender_poc"))
    plan.add_argument(
        "--hybrid", action="store_true", help="Use authored Blender Actions and NLA"
    )
    plan.add_argument("--character-a-package", type=Path)
    plan.add_argument("--character-b-package", type=Path)
    render = subs.add_parser(
        "render-blender",
        help="Build and optionally render the deterministic Blender proof scene",
    )
    render.add_argument("source", type=Path)
    render.add_argument("--output", type=Path, default=Path("outputs/blender_poc"))
    mode = render.add_mutually_exclusive_group()
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--final", action="store_true")
    render.add_argument("--scene-only", action="store_true")
    render.add_argument(
        "--hybrid", action="store_true", help="Use authored Blender Actions and NLA"
    )
    render.add_argument("--blender", type=Path)
    render.add_argument("--character-a-package", type=Path)
    render.add_argument("--character-b-package", type=Path)
    debug = subs.add_parser(
        "render-motion-debug",
        help="Rebuild and render the top-down Combat Motion Lab diagnostic",
    )
    debug.add_argument("--blender", type=Path)
    debug.add_argument("--force", action="store_true")
    debug.add_argument("--scene-only", action="store_true")
    review = subs.add_parser(
        "render-motion-review",
        help="Render and assemble all five Combat Motion Lab review angles",
    )
    review.add_argument("--blender", type=Path)
    review.add_argument("--force", action="store_true")
    review.add_argument("--rebuild", action="store_true")


def _packages(args):
    return {
        slot: value
        for slot, value in (
            ("fighter_a", args.character_a_package),
            ("fighter_b", args.character_b_package),
        )
        if value is not None
    }


def handle(args):
    if args.command in {"render-motion-debug", "render-motion-review"}:
        return _handle_motion_lab(args)
    if args.command == "blender-plan":
        project = create_project(
            args.source,
            args.output,
            hybrid=args.hybrid,
            character_packages=_packages(args),
        )
        print(f"Blender plan: {project}")
        print("Command: " + shlex.join(command_preview(project)))
        return 0
    source = args.source.resolve()
    project = (
        source
        if (source / "blender_manifest.json").is_file()
        else create_project(
            source,
            args.output,
            hybrid=args.hybrid,
            character_packages=_packages(args),
        )
    )
    mode = "final" if args.final else "preview"
    result = render_project(
        project,
        mode=mode,
        blender=args.blender,
        render=not args.scene_only,
    )
    print(f"Blender {'scene' if args.scene_only else mode}: {result}")
    return 0


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _blender(executable: Path | None) -> Path:
    if executable:
        return executable.expanduser().resolve()
    discovered = shutil.which("blender")
    if discovered:
        return Path(discovered)
    mac = Path("/Applications/Blender.app/Contents/MacOS/Blender")
    if mac.is_file():
        return mac
    raise RuntimeError("Blender was not found; pass --blender /path/to/blender")


def _handle_motion_lab(args) -> int:
    root = _project_root()
    output = root / "outputs/combat_motion_lab"
    blender = _blender(args.blender)
    rebuild = args.command == "render-motion-debug" or args.rebuild
    if rebuild:
        source = root / "outputs/first_production_fight_astra_final/scene.blend"
        subprocess.run(
            [str(blender), "-b", str(source), "--python-exit-code", "1", "--python",
             str(root / "scripts/blender_combat_motion_lab.py")],
            cwd=root, check=True,
        )
    if getattr(args, "scene_only", False):
        print(f"Motion Lab scene: {output / 'scene.blend'}")
        return 0
    view = "top-debug" if args.command == "render-motion-debug" else "all"
    render = [sys.executable, str(root / "scripts/run_combat_motion_lab_renders.py"),
              "--view", view, "--blender", str(blender)]
    if args.force:
        render.append("--force")
    subprocess.run(render, cwd=root, check=True)
    subprocess.run(
        [sys.executable, str(root / "scripts/assemble_combat_motion_lab.py"), "--view", view],
        cwd=root, check=True,
    )
    print(f"Motion Lab review: {output}")
    return 0
