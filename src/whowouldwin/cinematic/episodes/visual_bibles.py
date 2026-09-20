from pathlib import Path
from .schemas import VisualProfile, ArenaVisualProfile


def data_directory() -> Path:
    installed = Path(__file__).resolve().parents[2] / "data"
    return (
        installed
        if installed.is_dir()
        else Path(__file__).resolve().parents[4] / "data"
    )


def load_visuals(
    ids: dict[str, str], directory: Path | None = None
) -> dict[str, VisualProfile]:
    folder = directory or data_directory() / "visual_bibles"
    result = {
        key: VisualProfile.model_validate_json(
            (folder / f"{profile_id}.json").read_text()
        )
        for key, profile_id in ids.items()
    }
    if any(ids[k] != v.character_id for k, v in result.items()):
        raise ValueError("Visual bible character ID mismatch")
    return result


def load_arena(path: Path | None = None) -> ArenaVisualProfile:
    return ArenaVisualProfile.model_validate_json(
        (path or data_directory() / "arena_visuals/rooftop.json").read_text()
    )
