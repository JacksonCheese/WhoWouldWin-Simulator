import json
from pathlib import Path
import yaml
from .schema import Character

ROOT = Path(__file__).resolve().parents[3]


def data_directory() -> Path:
    local = ROOT / "data" / "characters"
    return local if local.is_dir() else Path(__file__).resolve().parents[1] / "data" / "characters"


def load_character(name: str, directory: Path | None = None) -> Character:
    path = Path(name)
    if not path.is_file():
        directory = directory or data_directory()
        path = directory / f"{name}.json"
    raw = path.read_text(encoding="utf-8")
    return Character.model_validate(yaml.safe_load(raw) if path.suffix in {".yaml", ".yml"} else json.loads(raw))
