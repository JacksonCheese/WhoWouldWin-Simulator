from pathlib import Path
from .schemas import VisualProfile, ArenaVisualProfile


def data_directory() -> Path:
    source_checkout = Path(__file__).resolve().parents[4] / "data"
    installed = Path(__file__).resolve().parents[2] / "data"
    # A source checkout can coexist with an installed data directory containing
    # only a subset of assets. Prefer the complete checkout for editable installs.
    if (source_checkout / "visual_bibles").is_dir():
        return source_checkout
    return installed


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
