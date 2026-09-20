> Historical Unity experiment. The current production direction is the shot pipeline in [visual-pipeline.md](visual-pipeline.md). This guide is retained for compatibility; Unity is not required by the mock episode workflow.

# Cinematic visual pipeline

The Python combat engine remains the authority. The new presentation pipeline reads a completed, checksum-validated replay; it does not execute or modify a fight.

```text
simulation/replay.py: authoritative replay
                 ↓
cinematic/director.py: moment detection, choreography and time mapping
                 ↓
cinematic/exporter.py: compact cinematic_replay.json
                 ↓
Unity ReplayController + ReplaySampler
                 ↓
PoseMachine / CharacterActor / FightCameraDirector / CombatVfxDirector
                 ↓
URP 2D frame → deterministic image sequence → H.264/AAC MP4
```

## Requirements and opening the project

The project targets **Unity 6000.5.8f1**, using URP 17.5.0 with the **2D Renderer**, 2D Animation 15.1.0, PSD Importer 14.0.0 and Unity UI. The exact package dependencies and resolved lockfile live in `unity/WhoWouldWinVisual/Packages`. URP is bundled with this editor. No Cinemachine, Recorder, web, database, or research service is required. The custom camera supports deterministic seeking and portrait blocking directly.

The bundled high-fidelity art was created using the built-in image-generation tool, then sliced inside Unity without changing the original PNG pixels. Source atlases are in `Assets/Resources/Art/Refined`; exact prompts are in `docs/art-generation-prompts.json`. `RefinedArtInstaller` restores the named sprite regions and bundled profile bindings. The generated art is a development proxy set, not a canonical licensed production pack.

In Unity Hub, choose **Add project from disk** and select `unity/WhoWouldWinVisual`. Open `Assets/Scenes/CinematicArena.unity` and press Play. The sample upset replay starts automatically. Use **WhoWouldWin → Setup or refresh cinematic project** after adding a presentation mapping. The setup preserves imported custom profile art assignments. The refreshed bundled art can also be rebuilt with **WhoWouldWin → Refresh bundled refined art**.

To set up or rebuild from the terminal on this machine:

```bash
UNITY="/Applications/Unity/Hub/Editor/6000.5.8f1/Unity.app/Contents/MacOS/Unity"
"$UNITY" -batchmode -nographics \
  -projectPath "$PWD/unity/WhoWouldWinVisual" \
  -executeMethod WhoWouldWin.Editor.ProjectBuilder.BuildMac \
  -quit -logFile "$PWD/reports/unity-build.log"
```

Run this from the `whowouldwin-sim` directory with the Unity Editor closed for this project. The macOS build is written to `unity/WhoWouldWinVisual/Builds/WhoWouldWinCinematic.app`. Other desktop platforms can be built through Unity's Build Profiles with the same scene; they have not been validated on this machine.

## Exporting Python replays

```bash
source .venv/bin/activate
python -m whowouldwin.cli.main export-unity \
  replays/10000/upset.json --output unity_replays/upset.json
```

Export does not rerun the engine. The seed, original result digest, source checksum, original event indices and damage history remain in the output. This means an older, intact authoritative recording can be directed even if the current combat engine later changes.

For the Unity replay browser, copy the exported JSON into `unity/WhoWouldWinVisual/Assets/StreamingAssets/Replays/`. External files can also be passed to the built player:

```bash
"unity/WhoWouldWinVisual/Builds/WhoWouldWinCinematic.app/Contents/MacOS/WhoWouldWin Cinematic" \
  -replay "$PWD/unity_replays/upset.json"
```

Three directed examples are included: `upset`, `closest`, and `dominant`.

## What the exporter contains

The format uses arrays and simple objects suitable for `UnityEngine.JsonUtility`; Unity does not deserialize the original per-tick AI diagnostics.

| Field | Meaning |
| --- | --- |
| `metadata` | Seed, source checksum, engine/director versions, simulation and presentation durations, outcome and damage digests |
| `fighters` | Identity, maximum resources, visual mappings, movement keys and resource timeline |
| `authoritativeTimeline` | Relevant original events, with unchanged source indices and simulation timestamps |
| `damageTimeline` | Every original damage application and exact remaining health |
| `timeMap` | Contiguous presentation-time segments mapping to combat time |
| `cues` | Presentation-only choreography primitives linked to original events |
| `moments` | Ranked transformations, dodges, impacts, low-health moments and finishers |
| `projectiles` | Travel keyframes, original spawn/expiry times, and hit/miss/dodge/block outcome |
| `finalOutcome` | Original winner, condition, finisher, duration and remaining health |

Health and resource samples are copied at every source tick, including regeneration. The viewer **step-samples health** instead of interpolating damage. Motion is reduced only in nearly linear spans, retaining action boundaries, flight/form/control changes and a maximum 0.15-second key spacing. Unity uses bounded Hermite interpolation and a small deterministic smoothing filter for visual displacement.

The Python director generates exactly the same JSON for the same source and visual mapping data. It inserts a short introduction, impact holds, selected slow-motion windows and an ending. `timeMap` remains monotonic. During a hit-stop, combat time and actor animation are held while impact effects finish expanding. Unity never sets global simulation timescale or computes damage.

An instantaneous projectile arrival in the source is given a short visual release/travel interval immediately before its authoritative impact. Its original spawn timestamp is retained separately. Dodged/missed shots continue visibly past the avoidance point. These timing and staging adjustments convey an existing outcome; they do not add a damage event.

## Choreography and animation

Ability bindings live separately from combat profiles in `data/presentation/*.json`. Each maps an existing ability ID to a state, choreography primitive, VFX category and sound hook. Export fails on missing, duplicate, obsolete or invalid mappings.

The director groups adjacent attacks into combo variants, marks near-simultaneous compatible releases for non-damaging clashes, distinguishes impact intensity by damage fraction/knockback/finishing status, and adds presentation cues for landing, flight, clones, guard, dodge, recovery and transformation.

`PoseMachine` tracks locomotion, combat, reaction, special and transformation states. Reaction priorities interrupt the visible pose coherently. Procedural proxies blend their joint poses across cue boundaries; their animation is sampled from the timeline rather than restarted every simulation tick. The default Naruto and Omni-Man visuals are generated layered ninja and flying-hero proxies: realistically textured cloth, leather and skin with expressive stylized faces. Separate impact expressions, an articulated torso and limbs, hands, boots and cape replace the earlier flat vector parts. Those procedural parts remain as a fallback. They intentionally do not claim to be canonical Naruto/Omni-Man artwork.

User sprite sheets and skeletal prefabs use an **Animator with a manually sampled Playables mixer**. The same priority-ordered presentation layers select and blend their clips. Anticipation samples the first 35% of an attack clip; release continues through the remaining 65%, so the clip does not restart at contact. Set the impact frame around 35% of the supplied clip duration, or adjust the central phase mapping for an art pack. This supports deterministic pause, seek and restart without distributing `Animator.Play` calls through combat code.

The renderer supports grounded run/sprint, jump/fall, hover/flight movement, windups, punches/kicks, charged strikes, casts, guard, dodge, recoil, airborne knockback, recovery, transformation and defeat. The final defeated body settles into a persistent downed pose.

## Portrait framing

Portrait is the default and uses a 1080 × 1920 UI reference. The camera computes a two-fighter shot using portrait aspect and safe margins; it does not crop a landscape image. Very large world-space separations are compressed smoothly into a readable cinematic stage. Original motion keys are still retained in the replay. The staging preserves fighter order and elevation, while projectile positions use the same projection. This is spatial choreography, not a replacement combat simulation.

The camera follows the action midpoint and elevation, zooms within limits that retain both bodies, anticipates major attacks, and applies deterministic, rapidly decaying impact shakes. A painted city atlas and a separate weathered rooftop slice use parallax. Their material detail and cool atmosphere keep the brighter textured fighters readable. Heavy attacks add stronger recoil, particles, expanding shockwaves, streaks, dust and flash than ordinary hits.

## Controls and browser

| Control | Action |
| --- | --- |
| B or REPLAYS button | Open replay browser |
| Space | Pause / resume |
| R | Restart |
| Right arrow | Advance one presentation frame at 60 fps |
| 0 / 1 / 2 / 4 | 0.25× / 1× / 2× / 4× playback |
| H | Hide/show cinematic HUD |
| D | Animation-state and clock debug overlay |
| V | Switch portrait/landscape framing |

The replay browser provides file selection, Play, Pause, Restart, scrubbing, speed, HUD/debug toggles, orientation, and Record. It lists exported JSON files in StreamingAssets. It never controls fighter decisions.

## Replacing character art

Only import artwork you own or have permission to use. The application does not download character sprites or voices. Open **WhoWouldWin → Import character art**, then select the corresponding `Assets/Resources/Profiles/naruto.asset` or `omniman.asset`.

### Option 1: sprite sheet

1. Put a transparent PNG and a JSON sheet manifest together under `Assets/UserArt/<character>/`.
2. Use a uniform cell size. Every cell should use the same canvas and ground/foot alignment, with the character facing **right** in source art. Use transparent padding for attacks and airborne poses. The importer uses a bottom-center pivot.
3. Use one manifest entry for every required state listed below. Multiple states may explicitly share the same frame range when your art set has fewer animations.
4. Select the manifest TextAsset and the character visual profile in the importer window. Click **Import sprite sheet + animation mappings**.
5. The importer slices the sheet, creates actual sprite-animation clips, an Animator controller and prefab, and assigns all state bindings. Press **Validate all state and ability mappings**.
6. Preview the same replay and adjust the profile's overall scale so the character is around 3.5 Unity units tall. `pixelsPerUnit` defines the imported art's size before that profile scale.

Manifest structure (add every required state):

```json
{
  "characterId": "naruto",
  "texture": "naruto.png",
  "cellWidth": 256,
  "cellHeight": 256,
  "pixelsPerUnit": 72,
  "animations": [
    {"state": "Idle", "row": 0, "start": 0, "count": 8, "fps": 10, "loop": true},
    {"state": "CombatIdle", "row": 0, "start": 0, "count": 8, "fps": 10, "loop": true},
    {"state": "Run", "row": 1, "start": 0, "count": 8, "fps": 14, "loop": true}
  ]
}
```

Rows are counted from the **top**, starting at zero. `start` is the first column. Out-of-bounds frame ranges are rejected. A complete reusable manifest template is in `docs/sprite-sheet-template.json`.

Required states:

```text
Idle, CombatIdle, Run, Sprint, Dash, Jump, Fall, FlightIdle, FlightMove,
LightAttack, HeavyAttack, SpecialAttack, RangedAttack, Block, Dodge,
HitLight, HitHeavy, Knockback, Knockdown, Recovery, Transformation, Defeat
```

Character-specific ability bindings can select any of these states. Add new states deliberately in the shared vocabulary and central pose/clip selection when a new mechanic needs them. Existing melee chains also carry a combo variant index for proxy jab/cross/kick staging; additional sheet combo clips are an extension point.

### Option 2: layered sprites

Supply transparent PNG files named `head`, `torso`, `hips`, `upperarm`, `forearm`, `hand`, `thigh`, `shin`, and `foot`; `cape`, `neck` and `head_hurt` are optional. The bundled refined atlases include a separate impact face; the rig switches expressions during hit reactions. Use the included proxy part canvases as alignment guides. The importer builds a new articulated prefab from the selected layers. Per-layer rotation lets a side-facing fist texture align with the limb rig. Both sides reuse limb art and the root mirrors to face the opponent. This option is the quickest route to replacing the proxies while retaining all procedural poses.

Part proportions and joint placement are centralized in `ProxyRig.cs`; the profile exposes per-part sprite overrides and overall scale. Characters with different anatomy should use a supplied skeletal prefab or adapt the rig builder, rather than distorting arbitrary art into these proportions.

### Option 3: Unity 2D skeletal / layered prefab

Use the installed 2D Animation/PSD Importer workflow to create a rigged prefab with SpriteSkin, bones, SpriteRenderers and an Animator. Select the prefab in the importer and choose **Use skeletal / Animator prefab**. Assign each required state's AnimationClip in the visual profile Inspector, using clip paths relative to that prefab's Animator root. Keep root translation out of animation clips: stage motion belongs to `CharacterActor`. Avoid root-motion animation and leave the visual origin at the feet.

The replay controller supplies facing, motion, action, reaction and form context. The manual animation graph samples supplied clips; SpriteSkin performs deformation. A production skeletal rig itself must be authored from your supplied art. No fabricated bone weights for unseen canonical artwork are included.

### What to supply for canonical Naruto and Omni-Man

- **Naruto:** a licensed/rightfully usable Naruto sheet or layered rig, including recognizable head/hair/headband/outfit; ninja locomotion and evasive poses; melee combo, projectile/charged attack, clone-cast, transformation and hit/defeat animations. Clones reuse the fighter art. An alternate transformation look is optional but recommended.
- **Omni-Man:** a licensed/rightfully usable Omni-Man sheet or layered rig with recognizable face/mustache/hair, suit and cape; hover and flight poses, acceleration/braking, heavy punches, grapple/charge, aerial recoil and defeat animations.
- For both: permission/license information, transparent source files, frame layout/pivots, and any authorized VFX/SFX you want to replace. Voice clips are optional and are not required by the architecture.

## VFX and audio configuration

`CharacterVisualProfile` maps abilities and sound hooks without modifying combat code. `CombatVfxDirector` dispatches reusable cue categories; `EffectPool`, `ImpactParticles` and `GhostPool` reuse objects. Effect position, phase and seeds come from the cinematic timeline. Scrubbing recomputes their state instead of accumulating old emissions.

Effect sprites live under `Assets/Resources/Art/fx`. The included additive sprite shader supports energy glow, rings, slashes, sparks and dust. The effect system adds event-driven streaks, afterimages, clone duplicates, shockwaves, landing dust, block sparks and impact particles. Form auras and color treatment persist for the recorded transformation interval.

Generic synthesized sound hooks are in `Assets/Resources/Audio`: punch, heavy, dash, projectile, explosion, charge, block, transform, ko. Replace them with properly licensed clips. Per-profile AudioClip overrides affect live playback. Offline encoding uses the named WAV files in Resources/Audio; keep those replacements mono PCM16 at 22,050 Hz or extend the offline mixer. No character voices or downloaded copyrighted sound recordings are bundled.

## Recording 9:16 video

The included recorder exports deterministic PNG frames and a JSON capture manifest from the actual Unity camera. It supports both editor Play Mode and the standalone player. Browser **Record** defaults to 1080 × 1920 at 60 fps and writes to the application's persistent data folder; the player log and browser status identify the directory. The replay starts from frame zero and playback speed does not change the recording schedule. The browser and debug controls are excluded from capture. In Editor batch tests, the recorder uses a URP render request because Unity does not dispatch `WaitForEndOfFrame` there. Hiding the HUD removes names/health too.

The automated workflow renders, synthesizes an event-aligned soundtrack, and encodes a playable H.264/AAC MP4:

```bash
python -m pip install -e '.[video]'
python scripts/capture_unity.py \
  --replay unity_replays/upset.json \
  --output captures/upset-portrait.mp4
```

It builds the macOS player if needed. Add `--build` to rebuild after Unity code changes. Use `--hide-hud` for clean footage. Full resolution and frame rate default to **1080 × 1920, 60 fps**. Choose a new output basename for each run; the script refuses to mix new frames with an existing capture and stops on player exceptions or stalled rendering. PNG frames, a capture manifest, log and WAV soundtrack remain beside the MP4 in a directory sharing its basename.

For a short inspection render:

```bash
python scripts/capture_unity.py --replay unity_replays/upset.json \
  --output captures/preview.mp4 --start 3.8 --frames 120 --width 540 --height 960
```

For landscape, pass `--width 1920 --height 1080`. Recording follows a fixed presentation-frame schedule, not wall-clock timing. It can render slower or faster than real time without dropping timeline frames. Image sequences are intentionally retained and can use substantial disk space. The last frame holds the exact final outcome; duration is rounded up to a whole output frame.

If you already captured frames using the browser:

```bash
python scripts/encode_capture.py /path/to/captured/frames --output captures/fight.mp4
```

`imageio-ffmpeg` supplies an FFmpeg binary for encoding. Use `--frames-only` when you want just the PNG/WAV intermediate. Capture uses a graphical Unity player, so it needs a graphics-capable desktop session. Build and export can run without a graphics device; `-nographics` must not be applied to capture.

## Tests and boundaries

Run the Python suite with `python -m pytest -q`. `tests/test_cinematic.py` checks export determinism, exact damage/resource histories, outcome preservation, ordering, clock continuity, valid mappings, projectile travel and required choreography.

Unity tests are in `Assets/Tests/EditMode` and `Assets/Tests/PlayMode`. EditMode tests validate the bridge/time map, mappings, bounded seeking and actual sheet slicing/animation generation. PlayMode tests run the arena, check sprite bounds against the camera, operate the replay browser, seek across the fight and capture a small complete image sequence with real rendered pixels. Use Unity's Test Runner or:

```bash
"$UNITY" -batchmode -nographics -projectPath "$PWD/unity/WhoWouldWinVisual" \
  -runTests -testPlatform EditMode -testResults "$PWD/reports/unity-editmode.xml"
"$UNITY" -batchmode -projectPath "$PWD/unity/WhoWouldWinVisual" \
  -runTests -testPlatform PlayMode -testResults "$PWD/reports/unity-playmode.xml"
```

Remaining production work includes canonical licensed art, richer hand-authored attack choreography, custom skeletal rigs, stronger production sound, and more film-like environmental interaction. Current clones and clashes are presentation-only. Portrait distance compression deliberately prioritizes phone readability over literal meter-for-meter spatial display. The statistical engine and its replay data retain the original coordinates and outcomes.
