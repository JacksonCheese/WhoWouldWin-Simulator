# Blender proof validation

This page records the original rigid-character proof. The preserved comparison and
current skeletal motion validation are in [Blender combat motion v2](blender-combat-v2.md).

Validated on 2026-09-09 with Blender 4.5.13 LTS.

The reusable proof project is [outputs/blender_poc_final](../outputs/blender_poc_final). It retains the source normalized event log, deterministic `blender_plan.json`, standalone `scene.py`, `scene.blend`, manifest and rendered preview.

The preview is [fight.mp4](../outputs/blender_poc_final/renders/preview/fight.mp4): 360 × 640, 30 fps, 360 decoded frames, exactly 12.0 seconds. The Workbench preview completed in roughly 19 seconds after startup. It was visually reviewed at faceoff, dodge, wall collision, counter impact, launch and aftermath.

The plan maps only recorded source events: `event-000055` (`AttackDodged`), `event-000063` (`AttackHit`) and `event-000065` (`Knockback`). Wall fracture, dust, streaks, shockwave and debris carry explicit presentation authority; no terrain or fighter damage is added to the source simulation. Replay verification still reports seed 69, Naruto's KO victory at 22.55 seconds, and finisher `energy_orb`.

The project also includes a one-frame 720 × 1280 Eevee render at the counter impact: [impact.png](../outputs/blender_poc_final/renders/final/impact.png). It validates final-mode material, lighting, flash and debris behavior. A full 1080 × 1920 Eevee video was intentionally not run: the measured 720 × 1280 / 64-sample impact frame took about 109 seconds, making preview iteration the appropriate workflow.

Fixes discovered during live Blender execution:

- switched preview from Eevee to Workbench, reducing a projected multi-minute render to a fast 12-second preview;
- normalized Blender's frame-range-suffixed FFmpeg filename to the stable `fight.mp4` contract;
- replaced unstable per-piece armature deformation with bone-parented low-poly limbs;
- moved skyline geometry behind the play space and retargeted three shots to prevent environmental occlusion;
- kept the environment collision in front of the wall so the counter-hit is readable.

Run `python -m pytest -q` for all simulator, episode, golden and Blender-plan tests. The four Blender-plan tests specifically cover schema integrity, deterministic source selection, camera continuity, self-contained `bpy` script generation, command generation and missing asset handling.
