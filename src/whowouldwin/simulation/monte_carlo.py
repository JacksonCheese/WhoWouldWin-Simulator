from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import os
from time import perf_counter
from whowouldwin.characters.loader import load_character
from whowouldwin.combat.environment import Matchup
from whowouldwin.analytics.metrics import Metrics
from .runner import run_fight

_worker_config = None
_worker_profiles = None


def _initialize(config, profiles):
    global _worker_config, _worker_profiles
    _worker_config, _worker_profiles = config, profiles


def _batch(seeds):
    return [run_fight(_worker_config, seed=s, profiles=_worker_profiles) for s in seeds]


def monte_carlo(config: Matchup, runs: int, *, workers: int = 1, progress=None) -> tuple[dict, Metrics]:
    if runs < 1:
        raise ValueError("runs must be at least 1")
    if workers < 0:
        raise ValueError("workers must be nonnegative (0 means auto)")
    workers = min(workers or (os.cpu_count() or 1), 32, runs)
    if config.seed + runs - 1 > 2**63 - 1:
        raise ValueError("Seed range exceeds signed 64-bit range")
    profiles = (load_character(config.fighter_a), load_character(config.fighter_b))
    metrics = Metrics(profiles)
    start = perf_counter()
    if workers == 1:
        for index in range(runs):
            metrics.add(run_fight(config, seed=config.seed + index, profiles=profiles))
            if progress and ((index + 1) % max(1, runs // 100) == 0 or index + 1 == runs):
                progress(index + 1, runs)
    else:
        seeds = (list(range(config.seed + i, config.seed + min(i + 50, runs))) for i in range(0, runs, 50))
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
                                 initializer=_initialize, initargs=(config, profiles)) as pool:
            for batch in pool.map(_batch, seeds):
                for result in batch:
                    metrics.add(result)
                if progress:
                    progress(len(metrics.durations), runs)
    report = metrics.report()
    elapsed = perf_counter() - start
    report.update(config=config.model_dump(mode="json"), seed=config.seed,
                  seed_policy="seed + run_index; independent of worker count",
                  performance={"wall_seconds": elapsed, "fights_per_second": runs / max(elapsed, 1e-9), "workers": workers})
    return report, metrics
