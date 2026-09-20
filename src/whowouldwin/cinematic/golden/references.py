"""Local reference-pack validation and deterministic multi-view packing (no scraping)."""

from pathlib import Path
import shutil
from PIL import Image, ImageOps, ImageDraw
from whowouldwin.simulation.replay import digest
from whowouldwin.cinematic.episodes.project import file_hash, record_asset, safe_path
from whowouldwin.cinematic.episodes.schemas import AssetReference

EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def inspect_pack(directory, characters):
    directory = Path(directory).resolve()
    files = {}
    missing = []
    for group in [*characters, "style", "arena"]:
        folder = directory / group
        images = sorted(
            p
            for p in folder.glob("*")
            if p.suffix.lower() in EXTENSIONS and p.is_file()
        )
        if group in characters:
            for name in ["front", "three-quarter"]:
                if not any(p.stem == name for p in images):
                    missing.append(f"{group}/{name}.png (or .jpg/.webp)")
        elif not images:
            missing.append(f"{group}/<image>.png")
        if len(images) > 4:
            raise ValueError(f"{group}: use at most four consistent reference views")
        for path in images:
            if not path.resolve().is_relative_to(directory):
                raise ValueError("Reference symlink escapes the supplied pack")
            with Image.open(path) as image:
                if image.width < 256 or image.height < 256:
                    raise ValueError(
                        f"Reference {group}/{path.name} must be at least 256x256"
                    )
                if image.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError(f"Unsupported reference image: {path.name}")
                image.verify()
            files[f"{group}/{path.name}"] = path
    if missing:
        raise ValueError("Missing local references: " + ", ".join(missing))
    if sum(key.startswith(("style/", "arena/")) for key in files) > 4:
        raise ValueError("Use at most four style and arena images combined")
    return files


def board(paths, output):
    canvas = Image.new("RGB", (1536, 1536), "#e9e6df")
    draw = ImageDraw.Draw(canvas)
    columns = 2 if len(paths) > 1 else 1
    rows = (len(paths) + columns - 1) // columns
    tw, th = 1536 // columns, 1536 // rows
    for i, (label, path) in enumerate(paths):
        with Image.open(path) as source:
            im = ImageOps.exif_transpose(source).convert("RGB")
            im = ImageOps.contain(im, (tw - 32, th - 64))
        x = i % columns * tw
        y = i // columns * th
        canvas.paste(
            im, (x + (tw - im.width) // 2, y + 40 + (th - 48 - im.height) // 2)
        )
        draw.text((x + 16, y + 12), label, fill="#182433")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "JPEG", quality=90)


def import_pack(project, manifest, state, directory, characters, *, approve=False):
    files = inspect_pack(directory, characters)
    incoming = digest({key: file_hash(path) for key, path in files.items()})
    if state.reference_digest and incoming != state.reference_digest:
        raise ValueError(
            "This sequence already has a different reference pack; create a new golden sequence to preserve approvals and paid provenance"
        )
    for key, path in files.items():
        target = project / "references" / key
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.resolve() != target.resolve():
            shutil.copyfile(path, target)
        state.reference_files[target.relative_to(project).as_posix()] = file_hash(
            target
        )
        record_asset(project, manifest, "reference:" + key, target)
    for fighter in characters:
        rows = [
            (key, project / "references" / key)
            for key in files
            if key.startswith(fighter + "/")
        ]
        target = project / "references/packed" / f"{fighter}.jpg"
        board(rows, target)
        state.reference_files[target.relative_to(project).as_posix()] = file_hash(
            target
        )
        record_asset(project, manifest, "reference-board:" + fighter, target)
    # Gen-4 accepts three inputs: two identity boards and one style/arena board.
    rows = [
        (key, project / "references" / key)
        for key in files
        if key.startswith(("style/", "arena/"))
    ]
    if len(rows) > 4:
        raise ValueError("Use at most four style and arena images combined")
    target = project / "references/packed/look.jpg"
    board(rows, target)
    state.reference_files[target.relative_to(project).as_posix()] = file_hash(target)
    record_asset(project, manifest, "reference-board:look", target)
    state.reference_digest = incoming
    if approve:
        state.approved_reference_digest = incoming


def for_shot(project, state, shot):
    if not state.reference_digest:
        raise ValueError(
            "Supply local references with golden-references before real image generation"
        )
    if state.approved_reference_digest != state.reference_digest:
        raise ValueError(
            "Review the packed reference boards, then golden-references --approve"
        )
    for key, expected in state.reference_files.items():
        if (
            not safe_path(project, key).is_file()
            or file_hash(safe_path(project, key)) != expected
        ):
            raise ValueError(
                f"Reference changed: {key}; approved references must remain immutable"
            )
    result = []
    for tag in [*shot.subjects, "look"]:
        path = project / "references/packed" / f"{tag}.jpg"
        if not path.is_file():
            raise ValueError(f"Missing packed reference for {tag}")
        result.append(
            AssetReference(
                asset_id=tag, path=str(path), role="approved_local_reference"
            )
        )
    return tuple(result)
