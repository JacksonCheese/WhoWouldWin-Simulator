# Cinematic episodes: local mock milestone

For the newer short sequence and opt-in Runway workflow, see [Golden sequence](golden-sequence.md). This guide documents the preserved full-episode mock path.

The simulator determines **what happens**. The cinematic subsystem determines **how recorded events are portrayed**. Generated visuals are not evidence supporting a matchup result. The production target is 15–35 composed shots, roughly 0.5–4 seconds each, edited into a 30–90 second vertical video. This milestone renders labelled local mock animatics and requires no credentials or external API calls.

Pygame remains in `whowouldwin.visual` as a debugger. The previous Unity player and exporter remain available as an [earlier experiment](unity-experiment.md). Neither is used to generate an episode.

## Quick start

```bash
source .venv/bin/activate
python -m pip install -e '.[dev,video]'
wws create-video naruto omniman --seed 69 --mock \
  --aspect 9:16 --duration 60 --shots 24 \
  --output outputs/my-first-episode
```

Open `outputs/my-first-episode/final/episode.mp4`. The default output is 1080×1920 at 30 fps. `--width 360 --fps 15` produces a faster preview; height is inferred to match the aspect. `--aspect 16:9` supports landscape. Dimensions must be even. Every shot is 0.5–4 seconds, so infeasible duration/shot combinations are rejected. `--shake 0` disables impact camera shake. Intro and outro time occupy the first/last shots inside the duration budget.

The `--mock` / `--dry-run` flag is an explicit **draft preview override**, recorded in `manifest.json`. It does not mark shots as approved by a person. `create-video` runs a real battle once, preserves it as `simulation.json`, then coordinates the complete pipeline. The alias `omni_man` is accepted by this convenience command. Existing `simulate` flags and canonical `omniman` ID remain unchanged.

## Staged storyboard review

```bash
wws simulate --fighter naruto --opponent omniman --runs 1 --seed 69 \
  --save-replay replays/episode-source.json --output reports/episode-source --no-charts
wws direct replays/episode-source.json --duration 60 --shots 24 \
  --output outputs/reviewed-episode
wws storyboard outputs/reviewed-episode
# Review storyboard/contact-sheet.png and the individual frames before approving.
wws approve-shot outputs/reviewed-episode shot-001
# Or approve all after reviewing the complete storyboard:
wws approve-shot outputs/reviewed-episode --all
wws render outputs/reviewed-episode --mock
wws assemble outputs/reviewed-episode
wws episode-status outputs/reviewed-episode
```

`render --mock` refuses unapproved shots. A previous draft preview is not human approval. `--allow-draft` permits another explicit mock preview. Rejected or revised shots cannot bypass review with that flag. `RENDERED` is assigned only after a clip is produced; the manifest separately retains its approval proof.

To reject and revise one shot:

```bash
wws approve-shot outputs/reviewed-episode shot-008 --status REJECTED
wws revise-shot outputs/reviewed-episode shot-008 \
  --motion-prompt "Static dramatic composition. Preserve the recorded action, identities and outcome."
wws storyboard outputs/reviewed-episode
wws approve-shot outputs/reviewed-episode shot-008
wws render outputs/reviewed-episode --mock --shot shot-008
wws assemble outputs/reviewed-episode
```

Revision advances only that shot's version, invalidates its current render and final-video record, and retains earlier files for inspection. Other clips remain cached. Re-running a completed mock command resumes matching assets by version and SHA-256. Changed source or directing settings require a new project directory. Direct editing of protected episode JSON is rejected; use the revision command for prompts. Human-edited prompts must still respect source outcomes. Automated prompt-truth validation is future work.

## Episode structure and authority

```text
outputs/<episode>/
  simulation.json       Original checksummed replay, embedded combat profiles and result
  events.json           Normalized events, all state frames, source checksum and outcome
  moments.json          Importance scores, grouped source IDs, summaries and consequences
  shot_list.json        Shots, exact frame counts, camera direction, prompts, statuses
  continuity.json       Continuity attached to each shot
  visual_profiles.json  Snapshotted visual bibles
  arena_visual.json     Snapshotted arena fixture
  manifest.json         Versions, approval proofs, hashes, providers, costs, timestamps/history
  references/           Reserved local reference-asset staging
  storyboard/           Individual versioned PNGs and contact-sheet.png
  keyframes/            Versioned mock keyframe PNGs
  clips/                Versioned H.264 MP4 shot clips
  audio/                mock-sfx.wav and timing.json
  final/                episode.mp4, captions.srt, validation.json, local edit intermediates
```

Old final files may remain on disk after a revision; only the current `final_video` manifest record denotes a valid assembled export. The simulation checksum and separate outcome digest are verified when an episode is loaded. The checksum detects changes, not malicious forgery. Schemas are versioned Pydantic models in `cinematic/episodes/schemas.py`. Machine-readable contracts and real example records are under `docs/examples/cinematic/`.

## Adapter and moment selection

`adapter.adapt_replay()` reads the completed replay. It does not execute the engine. Every original event is retained, in order, with a deterministic `sim-000000` ordinal and normalized `event-000000` ID, scoped by the source replay checksum. Mirrors use distinct entity IDs such as `naruto@0` and `naruto@1`, both mapped to the same combat profile ID.

Damage and explicit health-after-damage are copied exactly. `actor_state_before/after` and target states bracket the previous/end-of-current tick; they are not invented intermediate poses. Fighter positions/velocities come from snapshots. Projectile velocity is unavailable in snapshots. Unknown anatomy, clothing damage and inventory are left absent/empty. `success` describes attack contact: hit/blocked contact is true, miss/dodged/interrupted is false, other events are unknown.

Impact is an explicitly documented heuristic:

```text
impact_score = min(1, damage / target_max_health * 4 + recorded_knockback_force / 80)
```

`CinematicEventSelector` scores damage, first hit, transformations, special attacks, defenses, movement, knockback, near defeat, comeback, resource threshold crossing, health-lead changes and outcome. Repetition reduces importance. Closely related events sharing actor/ability are grouped inside a configurable window; a new attack commitment starts a new group. This is a temporal heuristic, not a claim that the current engine provides action-instance IDs. `--group-window` and `--minimum-score` expose the main thresholds. `SelectorSettings` exposes the remaining limits.

## Direction and continuity

The deterministic `CinematicDirector` implements a `Director` protocol suitable for a later LLM alternative. It preserves faceoff, transformation and final outcome moments, ranks the rest, then allocates an exact integer-frame budget. Overlapping moments are ordered by resolution time so continuity never rewinds. When too few distinct moments exist, it uses additional views of the same source moment, not new attacks. Timeout draws remain draws.

The shot schema supports establishing, wide/medium action, close-up, extreme close-up, over-shoulder, POV, low/high angles, aerial, impact, reaction, transformation, environmental, finisher and victory shots. Deterministic composition rules vary subject count, depth and framing. Prompts express crash zoom, orbit, whip pan, tracking, handheld impact, overhead views and slow-motion impact. Mock clips use pan/zoom/shake stand-ins; they do not implement real generated 3D camera motion.

`ContinuityTracker` reads **every** recorded frame, including omitted combat. It retains location, relative position, exact form and active statuses. Surface scuffs reflect the lowest health fraction seen, and persist through regeneration. This is explicitly a presentation convention; no anatomical wound, torn sleeve or blood is inferred. The data model can hold verified visible injuries, costume damage, items and environmental destruction when a future source supplies them.

Arena state can accumulate explicitly recorded normalized `persistent_destruction` effects. The current adapter never asserts those from an explosion. An explosion only supports a brief blast, not a demolished building. Time of day, lighting and weather come from the separate arena fixture.

## Visual bibles and provider boundary

`data/visual_bibles/*.json` covers Naruto, Omni-Man, Aang and Homelander. These optional descriptions are separate from battle stats and labelled unverified development fixtures. They include body/face/hair/costume descriptions, palette, identity constraints, prompt aliases, form visuals and asset-reference records. `data/arena_visuals/rooftop.json` supplies the stage, materials and lighting. Use `direct --visual-profiles <directory> --arena-visual <file>` for custom fixtures. Missing visual bibles fail clearly rather than inventing an identity.

The default future style prompt describes refined hybrid comic/anime art, realistic fabric/stone/skin textures and expressive stylized faces. Mock silhouettes do not claim to deliver that final art quality.

`StoryboardRenderer.render(shot, context)` returns a frame asset. `ImageProvider.generate_keyframe(request)` and `VideoProvider.generate_video(start_frame, motion_prompt, duration, aspect_ratio, references, options, output)` define provider-neutral boundaries. Their local mock implementations work without credentials. Reference images are represented as assets but automatic ingestion, rights verification, packaging and forwarding to live providers remain future integration work.

Configuration supports `WWS_IMAGE_PROVIDER`, `WWS_VIDEO_PROVIDER` or `--provider-config <json>`. Only `mock` is accepted, with `network_enabled: false`. No Runway, Veo, Seedance, LLM or other live integration is loaded. There is no credential reader, network media request, usage charge or paid fallback. `WWS_FFMPEG` optionally selects an executable; otherwise the video extra supplies FFmpeg.

## Editing and delivery

Mock storyboards are deterministic PNGs with named silhouettes, composition labels, arrows, action descriptions and source times. Mock clips preserve readable labels while applying camera moves to the scene. The editor uses hard cuts, brief intro/outro fades, impact freeze frames, configurable shake, punch-ins and flash frames. Freeze frames are inserted once within each shot's frame budget. Speed ramps and motion blur are deferred rather than approximated unsafely.

`audio/timing.json` records SFX and narration timings. A deterministic synthesized placeholder WAV provides audible cues; no voices, music or external sound assets are fetched. Narration is text/timing metadata, not TTS. `captions.srt` and a selectable MP4 subtitle track are included. Many social uploaders do not preserve soft subtitles; burned-in caption templates are a next milestone. Mock frame labels already remain visible.

FFmpeg creates H.264/yuv420p video, AAC audio, a mov_text subtitle track and fast-start MP4 metadata. The complete export is decoded to verify resolution, frame count and duration. `final/validation.json` ties these measurements to the unmodified battle outcome and zero cost. PNG/planning determinism is tested on the installed runtime; MP4 byte identity across different FFmpeg versions is not promised.

## Validation

```bash
python -m pytest -q
python -m pytest tests/test_episodes.py -q
wws replay outputs/naruto_vs_omniman_mock_demo/simulation.json
wws debug-view --replay outputs/naruto_vs_omniman_mock_demo/simulation.json
```

The original tests include actual Pygame live/recorded launches and a 1,000-fight batch. Added tests cover provenance, grouping, scores, mirrored fighters, exact shot budgets, composition variety, continuity including omitted events/expired forms, all four bibles, deterministic PNGs, local clips, approval/revision/resume, real end-to-end CLI assembly and unchanged seed/event/state results.

## Next milestone before any paid generation

Review multiple mock episodes, refine action readability, ingest verified reference assets, and define render QA and acceptable costs. Then add **one opt-in provider** behind the existing interfaces with human approval, job IDs, cached retries, budget caps, explicit credential configuration and output validation. Provider-generated art must never feed back into combat results. A GUI, web stack and paid APIs are outside this milestone.
