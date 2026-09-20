from .engine import Engine
from whowouldwin.combat.environment import Matchup


def run_fight(config: Matchup, *, seed: int | None = None, profiles=None) -> dict:
    return Engine(config, seed=seed, profiles=profiles).run()
