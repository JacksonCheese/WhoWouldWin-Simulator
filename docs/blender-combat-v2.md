# Blender combat motion v2

The motion-quality project is `outputs/blender_combat_v2`. It preserves the exact normalized event source used by `outputs/blender_poc_final`, but compiles a schema-v2 animation plan and a new standalone Blender runtime. The source checksum remains `ff4f81ae01878a8d7869b1320179db778fadc4e8cbc6b0fb5a49c38156402cb5`.

## What changed from `blender_poc_final`

| Area | Proof v1 | Combat v2 |
|---|---|---|
| Body | Separate rigid pieces parented to bones | One armature-modified mesh with explicit blended weights and overlapping joint volumes |
| Skeleton | Basic torso/limb chains | Pelvis, spine, chest, neck/head, clavicles, arms/hands, legs/feet |
| Contact | Pose approximation | Right-hand IK targets the recorded counter-hit point |
| Grounding | Rotated leg poses | Two-foot IK plants anticipation and landing frames |
| Root movement | Mostly start/end interpolation | Target, overshoot and recovery keys with accelerating blitz, curved dodge, launch arc and compressed landing |
| Poses | Small per-action dictionaries | Reusable 22-pose vocabulary with anticipation, contact, follow-through, hit, launch and landing phases |
| Timing | Linear dash and broad pose changes | Short holds, delayed acceleration, three-frame hit-stop and abrupt spacing |
| Camera | Start/end moves with broad noise | Lag/catch tracking, whip timing, impact hold, knockback reacquisition and beat-limited shake |

The v1 artifacts remain untouched and schema-v1 plans remain loadable. The simulator, source event adapter, replay outcome and event IDs did not change.

## Runtime measurements

Blender 4.5.13 LTS successfully built and rendered the v2 scene. The final preview is 360 × 640, 30 fps, 360 decoded frames and 12.0 seconds. On the validated scene:

- the counterpunch wrist reaches its explicit target with approximately `0.00012` Blender-unit error at frame 163;
- Fighter B is only `0.53` units off Fighter A's blitz line when A crosses the former target point at frame 87, producing a near miss rather than contact;
- foot IK influence is zero during launch and one at ground contact, preventing landing controls from leaking into the aerial trajectory;
- the impact pose and camera hold for three frames before follow-through and launch.

The review contact sheet is `outputs/blender_combat_v2/review/motion-contact-sheet.png`; the playable preview is `outputs/blender_combat_v2/renders/preview/fight.mp4`.

## Remaining visual weaknesses

The generic body is still a procedural low-detail mannequin. Its disconnected overlapping volumes deform smoothly enough for motion evaluation but do not have production topology, corrective shapes, fingers, facial acting or muscle compression. Elbows and shoulders can show volume loss at extreme poses. The IK setup uses a practical three-bone reach without authored pole-vector controls, so elbow arcs need human review from alternate cameras.

The choreography reads in the selected edit, but animation curves were generated procedurally rather than hand-polished in Blender's graph editor. The dash smear is whole-body scale exaggeration rather than a true mesh smear. Wall and ground impacts use presentation geometry rather than rigid-body destruction. Workbench preview rendering omits final motion blur, lighting and material cues. Those weaknesses require visual judgment and animator passes before any character-asset milestone.

## Commands

```bash
source .venv/bin/activate
wws render-blender outputs/naruto_vs_omniman_mock_demo \
  --output outputs/blender_combat_v2 --scene-only
wws render-blender outputs/blender_combat_v2 --preview
python -m pytest -q
```

Do not use `--final` for this milestone; preview mode is the intended motion review path.
