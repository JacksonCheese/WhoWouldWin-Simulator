# Cinematic mock milestone validation

Validated locally on 2026-09-05 with CPython 3.13.1, Pygame-CE 2.5.8, Pillow 12.3.0, imageio-ffmpeg 0.6.0 and its bundled FFmpeg. No external generative API was integrated or called in this milestone.

## Results

| Check | Result |
| --- | --- |
| Before additions | All 56 existing Python tests passed |
| Final complete suite | **84 passed in 39.74 seconds**, zero failures/errors/skips |
| Existing coverage retained | All 56 tests, including 1,000 Monte Carlo fights and real Pygame live/replay headless launches |
| Added coverage | 28 episode tests, including real CLI → FFmpeg assembly, local clip decoding, source invariance and review/revision |
| Install | Editable `.[dev,video]` installation succeeded; `wws` console entry works |
| Wheel | Build succeeded; isolated wheel import loaded all four visual bibles, arena and combat data outside the repository |
| Dependency health | `pip check`: no broken requirements |
| Four combat profiles | `wws validate`: aang, homelander, naruto, omniman |
| Core files | Engine and every combat module matched the pre-existing SHA-256 baseline |
| Replay regression | New demo outcome and every recorded event/state match the pre-existing seed-69 upset replay exactly |
| Media | Complete MP4 decoded: 1080×1920, 30 fps, 1,800 frames, exactly 60 seconds |
| Review | Contact sheet and extracted faceoff, transformation, finisher and winner frames inspected |
| Paid calls / cost | 0 / $0 |

The final test record is `reports/cinematic-milestone-tests.xml`; the initial baseline is `reports/shot-pipeline-baseline.xml`. The final suite includes parameterized continuity checks for all four requested starter pairings. An additional exploratory check directed 40 real battles; it exposed overlapping-moment time reversals, which were fixed and covered with regression tests. No character values were adjusted.

## Delivered demonstration

From the repository root:

```text
outputs/naruto_vs_omniman_mock_demo/final/episode.mp4
outputs/naruto_vs_omniman_mock_demo/storyboard/contact-sheet.png
outputs/naruto_vs_omniman_mock_demo/final/validation.json
outputs/naruto_vs_omniman_mock_demo/manifest.json
```

The video is a **local mock animatic**, not AI-generated footage. It contains 24 shots, uses 14 shot types, and expands a 22.55-second real simulation into a 60-second edit. Individual shots range from 2.17 to 3.03 seconds. It includes hard cuts, restrained intro/outro fades, impact holds/flashes/shake, camera moves over storyboards, local sound cues, narration timing, SRT captions and a selectable subtitle stream. The file is 79,523,980 bytes.

The original battle emitted 379 events, from which 28 moments were selected. Naruto wins by KO with `energy_orb`; Naruto retains 19.739260518782757 health and Omni-Man has zero health. These are development placeholder gameplay results, not canonical powerscaling claims. The saved source replay is embedded intact.

Every rendered shot in this demonstration records **explicit mock draft override**. None is misrepresented as having human approval. Staged rendering requires approval, unless the user explicitly requests a mock preview. Rejected/revised shots still require fresh review.

## Exact reproduction commands

```bash
cd "/Users/jacksonjue/Documents/Codex/2026-09-04/you-are-building-a-complete-working-2/whowouldwin-sim"
source .venv/bin/activate
python -m pip install -e '.[dev,video]'
wws create-video naruto omniman --seed 69 --mock \
  --aspect 9:16 --duration 60 --shots 24 --output outputs/my-first-episode
wws replay outputs/my-first-episode/simulation.json
python -m pytest -q
```

See [the pipeline guide](visual-pipeline.md) for staged approval, rejection and single-shot regeneration. Running the same settings again resumes existing assets. Use a fresh output directory when changing settings.

## Added and modified files

New Python files in `src/whowouldwin/cinematic/episodes/`:

- `__init__.py`: subsystem boundary.
- `schemas.py`: normalized events, moments, visual bibles, continuity, shots, provider settings and manifests.
- `adapter.py`: completed replay → normalized event/state log.
- `selector.py`: explainable importance scores and temporal grouping.
- `director.py`: deterministic shot planning, camera compositions and integer frame allocation.
- `continuity.py`: all-frame form/health/position/effect tracking and explicit arena-state accumulation.
- `visual_bibles.py`: separate visual/arena fixture loading.
- `prompts.py`: deterministic text composition with source-preservation constraints.
- `storyboard.py`: local PNG frames, blocking silhouettes and contact sheet.
- `providers.py`: image/video contracts, local mock producers and FFmpeg invocation.
- `editor.py`: editorial effects, captions, sound/narration timings and MP4 assembly/validation.
- `project.py`: checksummed episodes, approvals, shot revisions, cached assets and audit history.
- `cli.py`: additive episode commands and Pygame debug launcher.

Additional new files:

- `data/visual_bibles/{naruto,omniman,aang,homelander}.json`.
- `data/arena_visuals/rooftop.json`.
- `tests/test_episodes.py`.
- `docs/cinematic-audit.md`, `docs/cinematic-validation.md`, `docs/unity-experiment.md`.
- `docs/examples/cinematic/{event,moment,shot-list}.json` and six JSON schema files.
- The generated episode directory and test reports listed above.

Modified files:

- `src/whowouldwin/cli/main.py`: register/dispatch new commands; existing commands retained.
- `pyproject.toml`: add `wws`, explicit local video-extra requirements and visual-bible package data.
- `README.md`, `docs/visual-pipeline.md`: new primary production workflow and architecture.
- `.gitignore`: exclude generated `outputs/` assets.

Unchanged in this milestone: `combat`, `ai`, `characters`, `simulation`, `analytics`, battle data, the Pygame implementation, all 56 original Python tests and the earlier Unity experiment. There was no need to rewrite or decouple combat rules.

## Example JSON

Complete, schema-valid records are in [event.json](examples/cinematic/event.json), [moment.json](examples/cinematic/moment.json) and [shot-list.json](examples/cinematic/shot-list.json). These abbreviated excerpts show the same decisive attack:

```json
{
  "event_id": "event-000376",
  "simulation_time": 22.55,
  "actor_id": "naruto",
  "target_ids": ["omniman"],
  "event_type": "DamageApplied",
  "ability_id": "energy_orb",
  "damage": 26.034868027988466,
  "health_after_damage": 0,
  "source_event_ids": ["sim-000376"]
}
```

```json
{
  "moment_id": "moment-0040",
  "source_event_ids": ["event-000368", "event-000372", "event-000375", "event-000376"],
  "start_time": 22.35,
  "end_time": 22.55,
  "importance_score": 3.273312,
  "moment_type": "finisher",
  "participants": ["naruto", "omniman"],
  "summary": "Naruto lands energy orb, reducing Omni-Man to zero health."
}
```

```json
{
  "schema_version": 1,
  "matchup": "Naruto vs Omni-Man",
  "shots": [{
    "shot_id": "shot-023",
    "sequence_index": 22,
    "source_moment_ids": ["moment-0040"],
    "duration_seconds": 3.033333333333333,
    "frame_count": 91,
    "shot_type": "FINISHER",
    "camera_angle": "dynamic oblique",
    "camera_motion": "slow-motion impact",
    "subjects": ["naruto", "omniman"]
  }]
}
```

## Architectural findings and remaining work

The simulator already exposed a suitable replay boundary; it imports no renderer. Existing Pygame application code imports CLI configuration helpers, but combat is not coupled to Pygame. Events lacked IDs, and snapshots only bracket tick state; deterministic source ordinals and explicit derivation notes address that without modifying the engine. The old Unity timeline was unsuitable for shot approval/provenance, so it remains separate.

Mocks only approximate camera motion over labelled frames. Reference assets are represented in schemas but still need ingestion, integrity/rights verification and live-provider forwarding. Anatomy, exact costume tears and structural destruction are not exposed by current simulation output. Human prompt revisions are trusted presentation input; automated truth/continuity checks against provider output are not yet implemented. Narration is timing/text only, subtitles are soft, and sophisticated speed ramps/motion blur are deferred. Video bytes may vary with FFmpeg versions; source outcomes and shot plans remain deterministic.

Recommended next milestone: review several mock episodes and prepare the first **opt-in** generative adapter. The next five improvements are editorial review tooling, verified reference packaging, approved-shot provider jobs with budgets/retries, generated-output continuity QA, and final sound/narration/burned-caption polish. No real provider should be invoked until separately authorized.
