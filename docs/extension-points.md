# Extension boundaries

These are designs for later versions. No database, web service, research agent or machine-learning runtime is installed. Unity presentation and video capture are now implemented in a separate optional project.

| Future feature | Current boundary and planned change |
| --- | --- |
| Feat database and provenance | Keep `Character` as the validated runtime document. A separate source record should carry citation, feat scope, interpretation, version, confidence, and conversions into gameplay quantities. Compile source records to immutable profiles before simulation. |
| Low / mid / high and uncertainty | Low/expected/high scenario selection already happens once in `Character.stats()`. Future distributions should sample through the engine RNG before tick zero and save the realized values in replay metadata. |
| LLM research agent / web research pipeline | Produce reviewable feat/source records outside simulation. A human or separate validation workflow approves profile revisions; no live research or LLM calls belong in the tick loop. |
| PostgreSQL character storage | Add a repository adapter returning `Character`; retain `load_character` for offline JSON/YAML. Freeze fetched profiles before a batch starts. |
| API and web frontend | An API can own `Engine` sessions, call `step`, and stream the existing snapshots/events. Add explicit backpressure and per-job limits before exposing remote compute. The Python core remains authoritative. |
| Tournaments | Schedule existing `Matchup` batches with documented seed allocation and aggregate their results above `monte_carlo`. |
| Teams / 2v2+ | Replace two-slot assumptions (`1 - slot`) with stable entity/team IDs, a target-selection policy, and team victory rules. This is a planned engine revision, not currently supported functionality. |
| Destructible environments | Extend `World` with terrain entities; collision queries in movement and targeting would share a spatial interface. Emit terrain changes as events and include them in snapshots. |
| Reinforcement-learning fighters | Replace `choose_action` behind a policy interface that receives legal actions and observations. Keep action validation and all combat resolution in the existing engine. Version policy weights and record the selected actions. |
| Unity renderer (implemented) | Python compiles an authoritative replay into cinematic JSON; Unity consumes it through ReplaySampler and presentation systems. Future network playback can reuse this boundary. No independent combat logic belongs in Unity. |
| TikTok/video export (implemented) | Unity captures fixed presentation-time frames at 1080×1920/60fps; Python mixes generic sound hooks and FFmpeg encodes MP4. Future batch scheduling, captions and publication integrations belong above this workflow. |
| Automatic captions | Generate caption segments from structured hits, transformations, KO, and final report metadata. Label gameplay estimates clearly and preserve event timestamps. |

Replay format version 1 stores initial state followed by every tick's state and events. A future format should include migrations or retain a compatible recorded player. A rules-changing release must bump the engine version; seed verification and recorded playback intentionally have different compatibility requirements.
