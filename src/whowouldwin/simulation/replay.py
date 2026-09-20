"""Self-contained replay: embedded profiles + seed, and independent event/state playback."""
import hashlib
import json
import platform
from pathlib import Path
from whowouldwin import __version__
from whowouldwin.characters.schema import Character
from whowouldwin.combat.environment import Matchup
from .engine import Engine

FORMAT_VERSION = 1


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def save_replay(engine: Engine, path: str | Path) -> Path:
    if not engine.record:
        raise ValueError("Replay requires an Engine(record=True)")
    result = engine.result()
    payload = {"format_version": FORMAT_VERSION, "engine_version": __version__, "python_version": platform.python_version(),
               "seed": engine.seed, "config": engine.config.model_dump(mode="json"),
               "characters": [p.model_dump(mode="json") for p in engine.profiles],
               "result": result, "frames": engine.frames}
    payload["checksum"] = digest(payload)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    return path


def load_replay(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format_version") != FORMAT_VERSION:
        raise ValueError("Unsupported replay format")
    checksum = data.pop("checksum", None)
    if digest(data) != checksum:
        raise ValueError("Replay checksum mismatch: file is damaged or edited")
    data["checksum"] = checksum
    if not data["frames"] or not data["frames"][-1]["state"]["done"]:
        raise ValueError("Replay does not contain a completed fight")
    return data


def verify_replay(path: str | Path) -> dict:
    data = load_replay(path)
    if data["engine_version"] != __version__:
        raise ValueError("Engine version differs; use recorded playback instead of seed verification")
    engine = Engine(Matchup.model_validate(data["config"]), seed=data["seed"],
                    profiles=tuple(Character.model_validate(p) for p in data["characters"]), record=True)
    result = engine.run()
    if digest(result) != digest(data["result"]) or digest(engine.frames) != digest(data["frames"]):
        raise ValueError("Seed replay diverged from recorded fight")
    return result


class ReplayPlayer:
    """Renderer adapter; recorded playback does not execute the combat engine."""
    def __init__(self, data: dict):
        self.data = data
        self.index = 0

    @property
    def frame(self) -> dict:
        return self.data["frames"][self.index]

    def step(self) -> dict:
        self.index = min(self.index + 1, len(self.data["frames"]) - 1)
        return self.frame

    def restart(self):
        self.index = 0
