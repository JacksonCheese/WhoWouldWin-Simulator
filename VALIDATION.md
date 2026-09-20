# Validation record

Validated on 2026-09-05, macOS, CPython 3.13.1, Pygame-CE 2.5.8. All results below use **development placeholder scaling**, not researched fictional-character feats.

## Automated tests

Final `python -m pytest -q --durations=5`: **47 passed in 34.44 seconds**. This includes a full 1,000-fight Monte Carlo smoke test, serial/parallel seed parity, event-by-event and frame-by-frame replay verification, CLI reports and chart generation, both live and replay Pygame modes using SDL's dummy display, and pause/step/restart/debug key handling in both visual modes.

Four starter profiles validate. Startup timing, resource spending/cooldowns, bounds/finite states, movement, jumping/flight, projectiles, blocks/dodges, grapples, knockback, status expiry/immunity, forms, regeneration, KO/death/incapacitation, simultaneous KO, and timeout handling have focused checks. Incapacitation is checked at both 3.00-second and 2.99-second boundaries.

## Installation, replays and desktop launch

- Editable installation completed successfully.
- Built `dist/whowouldwin_sim-0.1.0-py3-none-any.whl` and installed it into an isolated target directory. From outside the repository, the installed wheel validated all four bundled profiles and reproduced the source replay result.
- Verified **all 32 delivered replay files**, including their full event/state histories. Paths are listed in `reports/replay_verification.json`.
- Launched the real macOS Pygame window using seed 12345 and 4× playback. The fight completed at tick 376 (18.80 simulated seconds), with Naruto winning by KO. The viewer rendered 278 display frames. Its saved recording also passed seed verification.
- Visually inspected the desktop screenshot, an in-progress fight showing flight and projectiles, and generated finishing-method charts. Screenshots are in `reports/visual-native.png` and `reports/visual-in-progress.png`.

## Full-duration matchup checks

Command: `python scripts/validate_matchups.py`. Each pairing uses seeds 42–1041, expected scaling, 0.05-second ticks, a 120 × 40 arena, and a 180-second timeout.

| Pairing | Fighter A wins | Fighter B wins | Draws | Median | Mean | Duration range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Naruto vs Omni-Man | 39 (3.9%) | 960 (96.0%) | 1 (0.1%) | 15.45 s | 15.83 s | 7.55–31.95 s |
| Aang vs Homelander | 242 (24.2%) | 755 (75.5%) | 3 (0.3%) | 27.30 s | 27.36 s | 15.00–45.80 s |
| Naruto vs Aang | 594 (59.4%) | 405 (40.5%) | 1 (0.1%) | 27.58 s | 28.28 s | 12.30–53.75 s |
| Omni-Man vs Homelander | 999 (99.9%) | 1 (0.1%) | 0 | 12.60 s | 12.78 s | 8.75–18.15 s |

All five draws were mutual KOs; there were no timeouts. Both fighters dealt damage in every pairing's aggregates. All attacking starter abilities recorded hits in the appropriate batches; projectile hit rates ranged from approximately 51% to 84% per committed use. Attack misses, dodges, blocks, flight, jumps, knockback, status expiry and transformations occurred. No character values were adjusted to force evenly split results.

For Naruto vs Omni-Man, the 1,000-fight event totals include 16,999 hits, 2,293 dodges, 1,919 blocks, 1,275 flight starts, 984 transformations, 15,998 knockbacks, and 1,825 interrupted actions. Full telemetry is in `reports/validation_summary.json`; detailed per-matchup reports and charts are in `reports/`.

## 10,000-fight run

```bash
python -m whowouldwin.cli.main simulate \
  --fighter naruto --opponent omniman --runs 10000 --seed 42 \
  --workers 4 --save-interesting \
  --replay-dir replays/10000 --output reports/10000 --quiet
```

- Naruto: 390 wins, **3.90%**.
- Omni-Man: 9,603 wins, **96.03%**.
- Draws: 7, **0.07%**.
- Median: **15.45 seconds**; mean: **15.85 seconds**.
- Shortest: 6.00 seconds; longest: 36.85 seconds.
- Simulation batch: **106.95 seconds**, approximately 93.5 fights/second. Report/chart and replay I/O are outside this timer.
- Most common Naruto finisher: Energy Orb, 54.1% of his wins.
- Most common Omni-Man finisher: Heavy Strike, 34.5% of his wins.

`reports/10000` contains the full report and three chart images. `replays/10000` contains closest, fastest, longest, dominant and upset recordings. Every saved representative is regenerated from its seed and compared against its original Monte Carlo result before saving.

## Corrections made during implementation

- Normalized validated defaults so reloaded profiles preserve JSON number types during strict replay checks.
- Corrected a one-tick early release of newly committed attacks and added a timing regression test.
- Corrected floating-point threshold handling for incapacitation and preserved the finishing action when its status expires at the victory threshold.
- Prevented stun chaining through duration caps and post-stun immunity; grounded recovery and bounded flight are covered by tests.
- Changed the CSV integration check to parse its contents instead of expecting an arbitrary minimum file length.

The results are reproducible gameplay experiments. They must not be published as canonical character matchup probabilities.
