# Blender assets

The proof scene creates two generic rigged humanoids procedurally and needs no external model.

Future character assets belong under `assets/blender/characters/<character-id>/`. A character binding can reference a local `.blend`, `.glb`, or future rig-adapter file through `model_path`; the planner validates the path before Blender is launched. Keep custom action clips under `assets/blender/actions/<character-id>/` and map them through `action_overrides` using the generic action names in `cinematic/blender_backend/schemas.py`.

The current runtime deliberately does not auto-import third-party character meshes or retarget their animation. A future character rig adapter must explicitly map its controls to the generic action contract, preserving the simulator-to-choreography boundary.
