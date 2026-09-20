# Shot-pipeline audit

The existing source tree, imports, tests and saved replay were inspected before the new episode subsystem was added. This audit concerns the Python simulator and both existing viewers, including the recent Unity experiment.

| Component | Existing entry / data | Decision |
| --- | --- | --- |
| Combat | `simulation/engine.py`: `Engine.step()`, `run()`, `result()` | Reuse unchanged. Private seeded `random.Random`, no renderer imports. |
| Utility AI / mechanics | `ai/utility_ai.py`, `combat/*` | Reuse unchanged. Cinematic selection never participates in decisions or damage. |
| Profiles | `characters/schema.py`, loader/validator, `data/characters` | Reuse unchanged. Pydantic immutable documents; separate visual bibles hold appearance. |
| Batch runs | `simulation/monte_carlo.py`, `runner.py` | Reuse unchanged. Workers retain seed scheduling and metrics. |
| Events | `simulation/events.py`: type, tick, timestamp, fighter/target slots, action, position, values, metadata | Adapt in the new package. Events have no IDs, so assign stable ordinal IDs within a source replay. |
| Results | `Engine.result()`: seed, winner slot, condition, duration, ticks, finisher, event counts, fighter stats | Copy verbatim to the episode. Never infer the winner from selected shots. |
| Saved replay | `simulation/replay.py`: checksum, embedded profiles/config/result, frames with snapshots and events | Primary integration boundary. Checksum validation occurs before adaptation. |
| Pygame | `visual/app.py` invokes Engine or ReplayPlayer; renderer reads snapshots/events | Preserve paths for compatibility. Add a clearly named debug launcher; no engine-to-viewer dependency exists. |
| CLI | `cli/main.py`: simulate, replay, validate, export-unity | Add commands through a separately registered episode CLI. Existing syntax remains valid. |
| Unity experiment | `cinematic/director.py`, exporter, presentation mappings, `unity/WhoWouldWinVisual` | Retain as an optional earlier experiment. Production milestone uses `cinematic/episodes`; no Unity installation is needed. |
| Tests | 47 engine/profile/debug tests plus 9 existing Unity-export tests | Preserve all 56, add independent episode tests and rendering invariance regression. |

## Coupling and limitations discovered

- There is no simulation import of Pygame, Unity or a cinematic director. No combat decoupling or rewrite is needed.
- The Pygame launcher imports shared CLI matchup helpers. That is one-way application coordination, not combat coupling; moving it would risk existing commands for no benefit.
- Pygame remains a package dependency for compatibility, though the new pipeline never imports or initializes it. Optionalizing installation can be a later packaging-only change.
- Snapshots are taken at tick boundaries. Before/after event states therefore mean previous-tick / end-of-current-tick brackets, not exact intermediate state for each event. A damage event's explicit health value is preserved separately.
- Event IDs are absent. The adapter's deterministic ordinal IDs are scoped by the replay checksum and retain source indices.
- Projectile snapshots omit velocity; fighter velocity is exposed. The adapter leaves unavailable projectile velocity unset rather than inventing it.
- Anatomy-specific injuries, costume tears, inventory, terrain damage, lighting and weather are not simulated. Visual fixtures and explicitly labelled presentational wear are kept separate. An Explosion event does not prove a building was destroyed.
- Existing low-level Unity cinematic JSON is aimed at continuous playback. Reusing it as a shot schema would hide provenance and approval requirements, so the new shot subsystem consumes the authoritative replay directly.

## Reuse boundary

`cinematic.episodes` depends on existing simulation/replay and character loading. Neither `simulation`, `combat`, `ai` nor the combat-profile schema is modified. Generated episodes embed the original `simulation.json`, its checksum and result digest. Unity and Pygame remain available but are not used to create the mock shot video.
