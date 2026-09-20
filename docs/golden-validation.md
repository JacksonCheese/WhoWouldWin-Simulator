# Golden milestone validation — 2026-09-06

## Delivered artifact

`outputs/golden_sequence/final/golden_sequence.mp4`: local mock, H.264, 720 × 1280, 30 fps, 300 decoded frames, 10.0 seconds. Seven current keyframes, seven preserved five-second source clips and seven separately trimmed edit clips. The contact sheet was visually inspected. No real image/video tasks were submitted; the manifest has zero provider jobs and $0.00 confirmed/committed API cost. Human keyframe approval remains unset for the preview.

Source window: seed 69, 21.80–22.55 seconds. Source moments 0039 and 0040 are covered from different perspectives; the same finisher contact IDs recur intentionally. Naruto still wins by KO at 22.55 seconds; final health 19.739260518782757 versus zero.

## Reproducibility

- Source checksum: `ff4f81ae01878a8d7869b1320179db778fadc4e8cbc6b0fb5a49c38156402cb5`
- Outcome digest: `fb3a7975683c9fc6dfafb0ce8ba71e241866a749be826caff70c2058794b3265`
- Recorded-frame digest: `c6309a16bab19fce641583b4489e6ccaef46a446edcd82c112d600f3e1442978`
- Full saved-replay verification passed after cinematic export.
- The engine/combat source hashes in `reports/combat-baseline.sha256` are unchanged. No engine, utility AI, combat profile, batch or normalized adapter implementation was modified.

## Tests and packaging

The full suite contains 100 tests: 84 pre-existing simulator/episode tests and 16 new golden tests. Results are recorded in `reports/golden-milestone-tests.xml`. New tests disable socket connections and use the official Runway SDK with HTTPX MockTransport; SDK request contracts and recovery are tested without credentials or paid service access.

Coverage includes source/shot provenance, contiguous selection, transformation selection, repeated-event coverage, varied frame budgets, serialization, specific visual semantics and prompt limits, local reference approval/tamper checks, exact image approval, one-shot versioning, default mock/no paid fallback, finite spending caps, verified model/duration constraints, SDK image and video payloads, task polling retries, successful task caching, ambiguous submission recovery, explicit failed-task retries, output download recovery, full clip preservation, local trimming and actual FFmpeg final assembly.

Editable installation with `[dev,video,runway]` succeeds; `pip check` reports no broken requirements. A standard wheel builds and includes the new golden modules and both fighters' ability/visual fixtures. Tested CPython 3.13.1, runwayml 5.20.0, httpx 0.28.1. Exact dependencies are in `requirements-lock.txt`.

## Fixes found by validation

- Filtered ability ownership validation to actual ability commitments; status-expiry events can name an opponent's ability and must not demand a mapping on the victim.
- Moved FPS conversion before final frame trimming; clipping duration before conversion dropped a frame on short edits.
- Distinguished launch imagery from anticipation while retaining the pre-contact canonical continuity state.
- Included explicit visual prohibitions in compact prompts; the delivered sequence's longest compiled image prompt is 947 UTF-16 units, below the 1,000-unit contract.
- Distinguished rendered mock state from human approval of the exact keyframe in the quality report.

## Files added

- `src/whowouldwin/cinematic/golden/__init__.py`
- `src/whowouldwin/cinematic/golden/schemas.py`
- `src/whowouldwin/cinematic/golden/director.py`
- `src/whowouldwin/cinematic/golden/prompts.py`
- `src/whowouldwin/cinematic/golden/references.py`
- `src/whowouldwin/cinematic/golden/runway.py`
- `src/whowouldwin/cinematic/golden/project.py`
- `src/whowouldwin/cinematic/golden/cli.py`
- `data/ability_visuals/naruto.json`, `omniman.json`
- `data/golden_visual_bibles/naruto.json`, `omniman.json`
- `tests/test_golden.py`
- `references/README.md` and empty input group directories
- `docs/golden-sequence.md`, `docs/golden-validation.md`
- Generated `outputs/golden_sequence/` project, cost estimate, contact sheet, quality report and video

## Files modified

- `src/whowouldwin/cinematic/episodes/schemas.py`: additive shot fields, 0.3-second minimum for impact inserts, golden settings subtype, opt-in provider metadata and manifest extension.
- `src/whowouldwin/cinematic/episodes/project.py`: route golden rendering through its stricter checkpoint.
- `src/whowouldwin/cinematic/episodes/editor.py`: configurable final-video provenance comment; existing editing logic preserved.
- `src/whowouldwin/cli/main.py`: golden command registration and dispatch.
- `pyproject.toml`, `requirements-lock.txt`: optional official Runway SDK and offline test dependencies, packaged fixture data.
- `README.md`, `docs/visual-pipeline.md`, `.gitignore`: current workflow, historical guide link, local credential/reference exclusions.

## Limits of this validation

Live Runway acceptance, account eligibility, moderation responses, visual quality and identity consistency have not been tested. The paid workflow deliberately awaits user references, credentials and explicit commands. Model pricing is a dated table, not a provider billing lock. The new process lock uses POSIX fcntl. The next validation is a human-reviewed seven-image pass followed by the separately approved ten-second real clip; no wider feature work is needed first.
