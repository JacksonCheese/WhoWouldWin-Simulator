# WhoWouldWin production character assets

Each production character lives in its own package:

```text
assets/characters/<character_id>/
├── manifest.json
├── model/
├── rig_adapter.json
├── materials/
├── animations/
├── abilities/
├── vfx/
├── audio/
└── metadata/
```

The deterministic simulator never reads this directory. Character packages control presentation only: model import, rig mapping, animation selection, material/VFX lookup, attachments, and sound hooks.

## Asset to supply for the first production integration

Supply a legally documented `.blend`, `.fbx`, `.glb`, or `.gltf` humanoid with:

- a single continuously skinned body at approximately human scale;
- a neutral A-pose or T-pose;
- an armature containing a root, pelvis, spine, chest, neck, head, paired clavicles, upper arms, forearms, hands, thighs, shins, and feet;
- clean shoulder, elbow, hip, knee, wrist, and ankle edge flow;
- artist-authored skin weights;
- Armature modifiers preserved on every body mesh;
- unapplied or clearly documented armature/object transforms;
- forward and up axes identified in the manifest;
- toe, finger, and twist bones when available;
- corrective shape keys preserved when available;
- a text file identifying creator, source URL, license, modification rights, and attribution requirements.

Hair, face controls, clothing detail, and textures are optional for the first deformation gate. Do not supply ripped game assets or models whose redistribution and derivative-render rights are unclear.

Place the model inside `model/`, update `manifest.json`, then run:

```bash
wws validate-character assets/characters/<character_id>
wws suggest-rig-map assets/characters/<character_id> \
  --output assets/characters/<character_id>/rig_adapter.proposed.json
```

Review every proposed mapping. Copy approved values into `rig_adapter.json`; the proposal is never treated as authoritative automatically.

## Animation assets

Reusable animation files may use the same four formats. Each clip declaration records its action class, source armature, embedded Blender Action name when applicable, phase markers, and root-motion policy. Production body animation stays primary. The WWS trajectory system replaces or adapts world-space root movement, while timing, contact IK, mirroring, reaction direction, and cameras remain procedural.

The first useful external motion set should cover dash, heavy cross, hook, kick, dodge, heavy hit, launch, airborne tumble, hard landing, skid, and recovery. Include the license alongside the files in `metadata/`.

The `v4_evaluation_a` and `v4_evaluation_b` packages are development fixtures. They reference the existing V4 scene outside their package directories and exist only to validate the package pipeline.

