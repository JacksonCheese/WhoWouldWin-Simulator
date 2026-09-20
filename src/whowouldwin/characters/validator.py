from pathlib import Path
from .loader import data_directory, load_character


def validate_directory(directory: Path | None = None) -> list[str]:
    paths = sorted(p for p in (directory or data_directory()).iterdir() if p.suffix in {".json", ".yaml", ".yml"})
    if not paths:
        raise ValueError("No character profiles found")
    profiles = [load_character(str(path)) for path in paths]
    ids = [c.identity.id for c in profiles]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate character ids")
    return ids
