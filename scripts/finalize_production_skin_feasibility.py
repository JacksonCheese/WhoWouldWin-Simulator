"""Create media provenance and the honest production-skin feasibility report."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/combat_motion_lab_production_skin_feasibility"
REVIEW = OUTPUT / "review"
VIDEOS = {
    "clean_preview": OUTPUT / "renders/preview/production-skin-clean.mp4",
    "quality_preview": OUTPUT / "renders/quality-preview/production-skin-quality.mp4",
    "contact_closeup": OUTPUT / "renders/contact-closeup/contact-deformation.mp4",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path: Path):
    output = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration",
        "-show_entries", "format=duration", "-of", "json", str(path),
    ])
    return json.loads(output)


def main():
    build = json.loads((REVIEW / "build-provenance.json").read_text())
    technical = json.loads((REVIEW / "technical-audit.json").read_text())
    media = {
        name: {"path": str(path), "sha256": sha256(path), "probe": probe(path)}
        for name, path in VIDEOS.items()
    }
    expected = {
        "clean_preview": (360, 640, 53),
        "quality_preview": (720, 1280, 53),
        "contact_closeup": (360, 640, 17),
    }
    for name, (width, height, frames) in expected.items():
        stream = media[name]["probe"]["streams"][0]
        assert (stream["width"], stream["height"], int(stream["nb_frames"])) == (width, height, frames)
        assert stream["r_frame_rate"] == "30/1"
    assert build["derived_scene_sha256"] == technical["derived_scene_sha256"] == sha256(OUTPUT / "scene.blend")
    assert technical["canonical_events_sha256"] == "4240f6768af86ccecf43d79136bbf5d56200b2358003bc38a9aa338ca4afe861"
    provenance = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "B",
        "decision": "The shot is readable but requires one targeted animation pass before expansion.",
        "scene_sha256": technical["derived_scene_sha256"],
        "baseline_scene_sha256": technical["source_scene_sha256"],
        "canonical_events_sha256": technical["canonical_events_sha256"],
        "body_root_actions_identical": all(item["identical"] for item in technical["action_signatures"].values()),
        "videos": media,
        "contact_sheets": {
            name: {"path": str(REVIEW / name), "sha256": sha256(REVIEW / name)}
            for name in ("quality-contact-sheet.png", "deformation-contact-sheet.png")
        },
        "full_fight_started": False,
        "production_approval_claimed": False,
    }
    (REVIEW / "media-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")

    report = f"""# Production-skin feasibility review

## Decision

**B. The shot is readable but requires one targeted animation pass before expansion.**

The production skins materially improve recognition, silhouette separation and phone-scale understanding. They do not make the existing motion production-ready. Full-fight work remains paused.

## Scope and preservation

This is a standalone derivative of `combat_motion_lab_hand_authored_root_revision`. The source scene remains untouched. The 108-frame timeline, event order, canonical event bytes, body/root Action separation and all four paired body/root Actions are unchanged. Their serialized F-curve signatures match the baseline exactly.

Canonical event SHA-256: `{technical['canonical_events_sha256']}`

Baseline scene SHA-256: `{technical['source_scene_sha256']}`

Feasibility scene SHA-256: `{technical['derived_scene_sha256']}`

The live test uses the existing Naruto and Omni-Man CharacterPackage bodies and accessories already present in the baseline: continuous skinned bodies, Naruto hair/headband and orange-black palette, Omni-Man hair/mustache/cape and red-white palette, plus the existing practical hand overlays. Package manifests, rig adapters and model-library hashes are recorded in `build-provenance.json`.

Presentation additions are limited to separate hand-preset Actions, conservative cape secondary keys, restrained Rasengan geometry/light, three 9:16 cameras, key/fill/rim lighting and a minimal floor/backdrop. No simulator, body Action, root Action, contact timing, collision result or renderer architecture was modified.

The edited preview uses source frames 1–22, 68–84 and 85–98. The omitted parry section is still available in the baseline; it is not represented as improved.

## Evaluation

### Character and silhouette readability

Naruto and Omni-Man are immediately distinguishable at 360×640. Costume color, Naruto's hair/headband and Omni-Man's mass/cape make action direction easier to parse than the debug bodies. The opening attack/slip reads without labels. The simple heads and hair are sufficient for this feasibility question but remain previs assets.

### Shoulder and elbow deformation

The continuous meshes and corrective-smoothing modifiers avoid catastrophic shoulder collapse or visible torso folding in the selected shots. The limitation is mechanical articulation: shoulder-girdle motion remains shallow and the arms still read as long hinge chains. Naruto's right elbow reaches **179.66°** at frames 82–84, creating a locked-arm contact silhouette. Omni-Man's recoil shoulders separate cleanly, but his ribcage does not compress or lag enough to sell the impact.

### Wrist and hand readability

Visible palms and fingers are a material improvement over mitten/proxy hands. They expose the next blocker: the fingers are oversized and the palm/wrist relationship is too rigid for a convincing Rasengan grip. At frame 82 the hand overlay's nearest sampled vertex is **{technical['contact_frame_82']['hand_overlay_to_omniman_vertex_distance']:.6f}** scene units from Omni-Man's body, while the authoritative physical hand proxy remains **{technical['contact_frame_82']['rasengan_physical_hand_proxy_gap']:.6f}** units clear. The Rasengan marker is approximately tangent with a **{technical['contact_frame_82']['rasengan_marker_surface_gap']:.6f}** surface gap. No skin evidence justifies moving the roots closer.

The energy rings are deliberately small enough to leave the hand/chest relationship visible. The faceted core remains a previs object and sometimes overlaps Naruto's face in perspective; it should be replaced or offset only after the hand arc is corrected.

### Torso and recoil

There is no new torso fold in the selected stills. The corrected progressive recoil remains intact and frame 90 no longer pops. The production silhouette shows that Omni-Man remains too upright through 85–98. The required targeted pass should add contact compression, pelvis lead, ribcage delay, asymmetric shoulder/arm lag and a more grounded catch without changing the validated root curve.

### Feet and sole contact

The skin makes the known floor problem unmistakable. Evaluated body minimum Z ranges from roughly 0.048 to 0.196 scene units in sampled selected frames; both fighters visibly hover in portions of the Rasengan and recoil shots. This agrees with the baseline finding that stationary ankle targets can coexist with sole gaps. Maximum declared support drift still passes at **{technical['baseline_support']['maximum_world_drift']:.6f}** against a **{technical['baseline_support']['threshold']:.3f}** threshold, proving only stability—not grounded weight.

The quality framing emphasizes upper-body contact but does not erase the defect: the clean preview and audit preserve full-body evidence. A targeted pass must lower/roll the feet or adjust the skin-to-rig foot offset while preserving the approved root trajectories and contact timing.

### Contact and cape clearance

The baseline still has zero unsupported proxy penetrations above its existing tolerance. The three recorded proxy overlaps remain intentional parry contacts. The sampled cape-to-body vertex distance at frame 82 is **{technical['contact_frame_82']['cape_to_body_vertex_distance']:.6f}** units; there is no major cape/body collision in the hero hold. The cape motion is readable secondary action but remains a rigid authored panel rather than finished cloth.

### Phone-scale camera assessment

The three-shot edit improves comprehension: a full-body setup establishes the miss, a medium three-quarter shot makes the Rasengan entry/contact legible, and a wider tracking shot shows progressive separation. It does not solve the animation. Both fighters clip the horizontal framing at some sampled extremes, and the recoil camera loses too much of each body by frame 98. This is a camera refinement issue, not evidence that the motion passed. No camera shake or heavy VFX was used.

## Targeted pass required before expansion

1. Frames 68–80: lower Naruto's center of mass into the rear-leg drive; make heel release and trailing-leg recovery visible while preserving the approved root path.
2. Frames 79–84: replace the locked 179.66° elbow with a slightly flexed, shoulder-supported contact line; orient the wrist/palm around the Rasengan without changing its tangent marker or hand clearance.
3. Frames 82–88: add visible Omni-Man torso compression, pelvis-first release and one-frame ribcage delay. Preserve the exact three-frame hold and the corrected recoil root Action.
4. Frames 85–98: resolve skin/sole height and grounded catch; strengthen asymmetric limb lag and recovery without introducing a new root discontinuity.
5. Camera: keep the medium contact composition, then widen/reacquire both bodies before frame 98. Do not use the crop to claim the sole problem is solved.
6. Hands: refine the production hand scale and cupped pose. The current controls are adequate for a focused revision; the absence of twist/scapula/toe deformation should be documented during the pass rather than disguised.

## Review method and limits

All final selected frames were inspected in contact sheets, and representative full-resolution frames 18, 76, 80, 82, 84, 86, 92 and 98 plus the frame-82 deformation close-up were inspected individually. Media files are verified at 30 fps with 53 frames for each edited preview and 17 frames for the contact close-up. The available inspection interface exposes ordered still frames rather than continuous video playback, so continuous normal-speed human approval is not claimed.

Technical validation establishes provenance, unchanged animation Actions, clearances and media integrity. It does not establish cinematic approval.

## Deliverables

- `scene.blend` — standalone production-skin feasibility scene.
- `renders/preview/production-skin-clean.mp4` — 360×640 clean preview.
- `renders/quality-preview/production-skin-quality.mp4` — 720×1280 Eevee preview.
- `renders/contact-closeup/contact-deformation.mp4` — no-motion-blur contact/deformation close-up.
- `review/technical-audit.json` — Action identity, contact, screen-bound and foot metrics.
- `review/build-provenance.json` and `review/media-provenance.json` — package/build/render identities.
- `review/quality-contact-sheet.png` and `review/deformation-contact-sheet.png` — ordered visual evidence.

## Copy-paste status

The limited production-skin feasibility test is complete with Classification B. Existing Naruto and Omni-Man package assets materially improve recognizability, silhouette separation and Rasengan readability at phone scale, so the production-skin approach is viable. They do not make the exchange production-ready. The exact remaining blockers are the locked Rasengan elbow and rigid wrist/palm, visible sole gaps despite stable IK targets, insufficient victim compression and upright recoil recovery, plus a recoil camera that loses both bodies near frame 98. The canonical event hash, all paired body/root Action keys and the 108-frame baseline are unchanged. One targeted animation/skin pass is required before expansion; the full fight should remain paused.
"""
    (REVIEW / "production-skin-review.md").write_text(report)
    (OUTPUT / "production-skin-review.md").write_text(report)

    gate = {
        "classification": "B",
        "decision": "The shot is readable but requires one targeted animation pass before expansion.",
        "production_skin_materially_improves_readability": True,
        "production_animation_approved": False,
        "focused_astra_animation_camera_pass_allowed": False,
        "full_fight_allowed": False,
        "technical_invariants": {
            "event_hash_preserved": True,
            "timeline_preserved": True,
            "body_root_actions_identical": provenance["body_root_actions_identical"],
            "unsupported_proxy_penetrations": technical["baseline_collision"]["unsupported_issue_count"],
        },
        "exact_blockers": [
            "Naruto right elbow locks at 179.66 degrees during contact.",
            "Wrist/palm and simplified fingers do not form a convincing Rasengan grip.",
            "Visible sole gaps remain despite numerically stable support targets.",
            "Omni-Man lacks enough torso compression and grounded catch during recoil.",
            "Recoil camera loses too much of both silhouettes near frame 98.",
        ],
    }
    (REVIEW / "production-animation-gate.json").write_text(json.dumps(gate, indent=2) + "\n")
    print("PRODUCTION_SKIN_FEASIBILITY_FINALIZED", provenance["scene_sha256"], "classification B")


if __name__ == "__main__":
    main()
