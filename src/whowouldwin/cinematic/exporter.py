import json
from pathlib import Path
from whowouldwin.simulation.replay import load_replay, digest
from .director import compile_cinematic


def export_unity(source: str | Path, output: str | Path, *, profile_directory=None) -> dict:
    replay = load_replay(source)
    cinematic = compile_cinematic(replay, profile_directory=profile_directory)
    cinematic["checksum"] = digest(cinematic)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(cinematic, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    return cinematic
