# WhoWouldWin Simulator — Agent Handoff

## Current state

This project is a deterministic fictional-character combat simulator plus a cinematic interpretation pipeline. The simulator determines canonical outcomes; Blender and the cinematic systems only interpret those outcomes visually.

The repository is currently on local Git branch `main` with a clean worktree.

- Current commit: `d648f67 Initial WhoWouldWin Simulator implementation`
- Tests: 128 passed in the latest full run
- Python source files: 79
- Test files: 13
- Starter characters: Naruto, Omni-Man, Aang, Homelander
- Retained Blender scenes: 27
- Retained MP4 review/demo videos: 199
- Repository size after cleanup: about 1.4 GB
- Generated outputs are ignored by Git
- GitHub remote is not configured yet because GitHub authentication is pending

## Latest milestone: first TikTok production slice

`outputs/first_tiktok_production_slice/` is the current presentation milestone. It is an 8.47-second, four-shot, vertical slice built around the approved production-skin hero exchange and corrected Omni-Man sole binding. The canonical event SHA-256 remains `4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861`; protected body/root Action signatures and the frames 82–84 Rasengan hold are unchanged.

The slice contains a simple held establishment, the existing attack/slip approach, the approved Rasengan hero exchange, and an editorial aftermath hold. It adds no complex combat choreography. The locked shot manifest, scene, clean preview, 720×1280 quality preview, 1080×1920 delivery, contact sheet, provenance, validation, and review are stored inside the milestone directory. Classification: **A for controlled slice expansion only**, not full-fight or publication readiness. Add at most one separately reviewed supporting shot at a time.

## Major architecture

```text
Character profiles
  -> deterministic combat engine
  -> structured battle event log
  -> cinematic event adapter
  -> importance selector / cinematic moments
  -> deterministic director / shot list
  -> continuity state
  -> storyboard renderer
  -> mock/provider abstraction
  -> FFmpeg video assembly

The Blender path consumes the same canonical event data:

events -> choreography -> Actions/NLA -> root trajectories -> IK/contact checks -> camera/VFX -> Blender render
```

The simulator must remain independent of cinematic and Blender packages. Never change combat outcomes, event ordering, replay semantics, canonical event hashes, or CharacterPackage contracts as part of visual work.

## What is validated

### Python simulator

- Seeded deterministic simulation and replay.
- Utility-based AI with debug scoring.
- Melee, ranged attacks, projectiles, beams, dodges, blocks, flight, grapples, dashes, knockback, transformations, cooldowns, status effects, regeneration, timeout, KO and draw handling.
- Monte Carlo runs with text, JSON, CSV and chart reports.
- Four starter character profiles with clearly labelled placeholder scaling.
- Structured event logs and replay verification.

Useful commands:

```bash
source .venv/bin/activate
python -m pytest -q
wws validate
wws simulate --fighter naruto --opponent omniman --runs 1 --seed 42 \
  --save-replay replays/fight_001.json --output reports/single
wws simulate --fighter naruto --opponent omniman --runs 10000 --seed 42 \
  --workers 4 --save-interesting --replay-dir replays/10000 \
  --output reports/10000
```

### Cinematic mock pipeline

The local pipeline can convert a saved simulation into moments, shots, storyboards, placeholder clips and a vertical FFmpeg video without paid APIs.

```bash
wws create-video naruto omniman --seed 69 --mock \
  --aspect 9:16 --duration 60 --shots 24 \
  --output outputs/my-first-episode
```

The output is an animatic/placeholder video, not generated character animation. Runway/provider adapters exist as interfaces and are intentionally not used automatically.

### Blender milestones

- V2: generic rigged combat, root motion, contact/collision proxies, camera/VFX architecture.
- V3: reusable Blender Actions/NLA with hybrid authored/procedural motion.
- V4: continuous skinned humanoid and retargeting validation.
- V5: CharacterPackage manifests, rig adapters, import validation, and package-backed fighters.
- First production fight: simplified stylized Naruto vs Omni-Man, city street, signature Rasengan and Omni-Man flight presentation.
- First Production Fight V2: spatial-integrity engineering and mesh/proxy collision validation.
- Combat Motion Lab: isolated review of body motion, roots, contacts and camera angles.
- Hand-authored Hero Exchange: paired 108-frame, 3–4 second exchange with Actions and separate root Actions.
- Latest root revision: corrected Naruto’s excessive 258° turn/glide and Omni-Man’s frame-90 recoil root pop while preserving the canonical event hash.
- Production-skin sole-binding derivative: scoped hero-shot feasibility pass; sole clearance was corrected without changing authored root/body Actions.

Important reports:

- `outputs/first_production_fight_v2/review/v2-certification.md`
- `outputs/first_production_fight_v2/production_review.md`
- `outputs/combat_motion_lab_hand_authored_root_revision/production_review.md`
- `outputs/combat_motion_lab_production_skin_sole_binding/sole-binding-review.md`
- `outputs/blender_combat_v3_astra/animation_director_review.md`

The V2 engineering milestone is closed. The hand-authored root revision was previously Classification B because grounded weight transfer, parry mechanics, heel release and recoil settling still needed human animation judgment. The production-skin sole-binding report is classified A for the scoped hero shot only; it does not approve the entire 15–20 second fight.

## Canonical preservation requirements

Preserve these while doing future work:

- deterministic simulator behavior;
- source event log and event order;
- canonical event SHA-256 when a report specifies it;
- CharacterPackage manifests and rig-adapter contracts;
- 108-frame hero-exchange timeline;
- body Actions and root Actions as separate systems;
- authored choreography as authoritative;
- Rasengan three-frame contact hold at frames 82–84;
- intentional tangent contact and zero unsupported penetration;
- source/provenance records;
- existing production and review outputs unless the user explicitly requests cleanup.

Do not use Mixamo clips as a fake paired performance. Do not use mocap unless an actually synchronized, partner-aware source with licensing metadata is supplied. Do not implement reinforcement learning or autonomous low-level movement. Do not use collision correction to invent choreography or hide weak animation.

## Current visual decision

The project is no longer blocked by simulator or pipeline architecture. The remaining production risk is animation authorship quality:

- whether the paired exchange reads as one intentional performance at normal speed;
- whether support feet visibly load, push, release and plant;
- whether the parry redirects an attack rather than matching an independent pose;
- whether shoulder, elbow, wrist, pelvis and chest timing communicate force;
- whether production skin deformation preserves readable silhouettes;
- whether the Rasengan hand remains physically clear while the marker stays tangent;
- whether recoil and separation feel body-driven instead of root-driven.

Do not call the whole fight production-ready from numerical validation alone.

## Recommended next plan

1. Configure GitHub. Sign in, create a private repository named `whowouldwin-sim`, add it as `origin`, and push `main`. Future validated code changes should be committed and pushed; generated renders, videos, caches, credentials and virtual environments remain ignored.
2. Review the latest production-skin hero-shot scene and all available normal-speed angles at phone scale.
3. If needed, perform one narrowly scoped animation correction pass only on the measured blocker. Do not reopen broad procedural polish.
4. Decide whether the hero exchange passes the no-VFX animation gate. If it passes, move to production-skin deformation review for the approved exchange before expanding the full fight.
5. If it fails, obtain or author a genuinely paired performance. Do not combine independent clips.
6. Only after hero-exchange approval, expand to the full Naruto vs Omni-Man fight, then add city/destruction polish, final lighting, sound, captions and external generative providers.
7. Add CI after GitHub setup: Python tests, character validation, event-hash invariance, and checks that generated artifacts stay out of Git.

## Key paths

```text
src/whowouldwin/              Python engine, AI, simulation, analytics, cinematic code
data/characters/              Starter JSON character profiles
assets/characters/             CharacterPackage fixtures and asset requirements
scripts/                       Blender builders, auditors and render helpers
tests/                         Pytest suite
outputs/                       Ignored Blender/cinematic generated artifacts
replays/                       Ignored saved replay artifacts
reports/                       Ignored simulation reports
README.md                     Full usage and architecture documentation
AGENTS.md                     Commit/push workflow for future agents
```

## Cleanup already performed

The cleanup removed only reproducible or generated material: Unity `Library`, `Builds` and logs; old capture media; Blender raw frame folders; `.blend1` backups; Python caches; pytest cache; packaging artifacts; and `.DS_Store` files. Current source, scene files, final/review videos, reports, packages and tests were preserved.

## GitHub status

Local Git is ready, but no `origin` remote exists yet. GitHub login was the only blocker. Once authenticated, create the remote and run:

```bash
git remote add origin https://github.com/<account>/whowouldwin-sim.git
git push -u origin main
```

Use the actual GitHub account and repository URL; do not invent either value. Keep the repository private unless the owner explicitly requests public visibility.
