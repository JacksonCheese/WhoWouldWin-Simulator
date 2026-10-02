"""Presentation-only direction for the first saved seed-69 episode."""

from pathlib import Path
import hashlib
import shutil

from .schemas import EpisodePlan

EPISODE_ID = "naruto_vs_omniman_seed69_ff4f81ae"
EVENT_SHA = "117633fb263707e0caad247260edfdd006dfeb62eee719a4a16a54a811502306"

# These are the selected replay events, never replacement combat outcomes.
DIRECTIONS = (
    dict(beat="faceoff", start="Naruto crouches on screen left; Omni-Man stands on screen right with a clear lane between them", action="A short anticipatory weight shift only; neither fighter attacks", weight="Naruto loads his rear leg; Omni-Man settles through both boots", feet="Both pairs of feet remain visibly planted", hands="Naruto raises a compact guard; Omni-Man keeps fists close to his ribs", face="Naruto intent and alert; Omni-Man stern", camera="medium-wide three-quarter faceoff, subtle push-in", ability="none", transition="cut on Naruto's guarded inhale into his recorded ranged attack"),
    dict(beat="charged_vortex projectile hit", start="Naruto is separated from Omni-Man by clear open street", action="Naruto launches the recorded charged-vortex projectile, visually a four-bladed Rasenshuriken-like wind shuriken; it hits Omni-Man's torso at range", weight="Naruto pushes from his rear foot into the launch; Omni-Man compresses at the recorded hit", feet="Naruto's lead foot plants; his rear heel releases; Omni-Man's support shifts under recoil", hands="Naruto's open palm follows a short curved release path but never touches Omni-Man; Omni-Man's free arm lags", face="Naruto focused; Omni-Man surprised by force", camera="medium two-character angle, short directional follow of the projectile", ability="one small blue-white four-bladed spinning wind projectile and a local impact ring; this is not a thrown Rasengan; keep bodies separate", transition="hard cut as Omni-Man reaches for the next recorded grapple"),
    dict(beat="grapple dodge", start="Omni-Man reaches from screen right while Naruto holds the left lane", action="Naruto slips outside the recorded grapple; Omni-Man's open hand passes through Naruto's former space without grabbing him", weight="Naruto drops his center over a planted lead foot and drives sideways", feet="Lead foot supports the slip; trailing foot releases and catches; no skating", hands="Omni-Man's single reaching hand follows a curved line; Naruto's arms stay compact and clear", face="Naruto alert; Omni-Man intent on intercepting", camera="medium lateral track keeping the miss lane visible", ability="one restrained afterimage only at Naruto's previous location", transition="cut on the reaching hand's travel into the heavy-strike setup"),
    dict(beat="heavy-strike block", start="Both fighters face each other on their established screen sides", action="Omni-Man's recorded heavy strike meets Naruto's forearm guard at one readable contact point; Naruto blocks and absorbs the recorded guarded damage", weight="Omni-Man drives hip then shoulder; Naruto sinks into his bent support leg", feet="Omni-Man's drive foot pushes; Naruto's lead and rear feet stay grounded through contact", hands="One Omni-Man fist contacts one Naruto forearm; Naruto's other hand protects his center", face="Omni-Man committed; Naruto strained but in control", camera="medium contact angle with both full figures and the guard visible", ability="a tiny white impact tick at the forearm; no second attack", transition="cut on Naruto's guard recoil into the recorded transformation"),
    dict(beat="chakra transformation", start="Naruto regains a low stance with Omni-Man separated on the right", action="Naruto activates the recorded temporary transformation; his costume and body proportions remain unchanged", weight="Naruto loads both legs and rises only slightly through the torso", feet="Both feet visibly plant; no levitation", hands="Hands cup near Naruto's center and then return to guard", face="Naruto focused and steady; Omni-Man watches", camera="medium two-character hold, no spin or new camera side", ability="a thin close-fitting blue aura only; no giant flames or new projectile", transition="hard cut on Omni-Man's charge acceleration"),
    dict(beat="Omni-Man charge hit", start="Omni-Man coils on screen right; Naruto remains left and transformed", action="Omni-Man's recorded high-speed charge travels right-to-left and hits Naruto once", weight="Omni-Man drives from legs into aligned shoulder/torso; Naruto compresses and is displaced leftward", feet="Omni-Man deliberately leaves the road in flight; Naruto's support feet release because the hit launches him", hands="Omni-Man's arms stay in one purposeful charge silhouette; Naruto's arms lag asymmetrically", face="Omni-Man forceful; Naruto shocked", camera="medium tracking shot with rapid but readable directional pan", ability="short air wake and one small contact tick; no added strike", transition="cut on Naruto's recovery into the recorded finishing projectile"),
    dict(beat="energy-orb projectile KO", start="Naruto and Omni-Man are separated by open street, Naruto left and Omni-Man right", action="Naruto fires the recorded generic Energy Orb projectile; it crosses the gap and hits Omni-Man, reducing his health to zero. Never label or depict this projectile as Rasengan", weight="Naruto plants and extends through hip, chest, shoulder and wrist; Omni-Man recoils through pelvis then chest", feet="Naruto's lead foot stays grounded; Omni-Man loses support only after projectile impact", hands="Naruto's physical hand remains well away from Omni-Man; his palm releases one orb; Omni-Man's arms lag the reaction", face="Naruto determined; Omni-Man stunned by the finishing hit", camera="medium three-quarter projectile impact showing launch point, travel gap and target", ability="compact generic blue-white energy pulse with a small travel tail, not Rasengan or Rasenshuriken; a brief local impact ring, no giant flash and no physical hand contact", transition="one brief impact hold then hard cut to the recorded KO aftermath"),
    dict(beat="recorded KO aftermath", start="Naruto is left in a tired guard; Omni-Man is down on the right", action="Hold the recorded Naruto KO victory without another attack or recovery by Omni-Man", weight="Naruto settles down through both legs; Omni-Man remains incapacitated", feet="Naruto's boots stay grounded; Omni-Man's body and cape rest on the road", hands="Naruto lowers his hands without a strike; Omni-Man's arms settle asymmetrically", face="Naruto exhausted but alert; Omni-Man unresponsive", camera="medium-wide two-character aftermath, very slow pull-back", ability="blue traces dissipate; no new energy or damage", transition="clean end hold for manual editorial cut"),
)

NEGATIVE = (
    "No realistic 3D rendering, photorealism, detailed anime shading, style drift, character redesign, extra fighters, "
    "extra limbs, extra fingers, melted faces, folded torsos, rubber anatomy, floating feet, skating, gliding, "
    "random hand flailing, tangled arms, costume changes, background identity drift, camera-axis flip, "
    "unreadable impact effects, giant bloom, text, logos, phone UI, letterbox, unrecorded contact, altered winner, or a thrown Rasengan."
)


def install_curated_assets(project: Path) -> dict:
    """Stage selected generated art without overwriting later human replacements."""
    from .package import write_json

    source = Path(__file__).resolve().parents[4] / "assets/seedance/first_episode"
    if not source.is_dir():
        return {"available": False, "installed": 0}
    installed = 0
    inventory = []
    for image in sorted(source.rglob("*.png")):
        if image.parent.name == "shared_references":
            target = project / "shared_references" / image.name
        elif image.parent.name == "keyframes":
            target = project / "shots" / image.stem / "keyframe.png"
        else:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(image, target)
            installed += 1
        inventory.append({
            "asset": str(target.relative_to(project)),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "source_kind": "selected built-in image-generation artwork",
            "human_visual_approval": "pending",
        })
    write_json(project / "generated_image_inventory.json", {
        "schema_version": 1, "images": inventory, "count": len(inventory),
        "reference_videos_copied": False, "paid_video_provider_calls": 0,
        "note": "Generated graphic development references; manually review identity, rights and motion before publication.",
    })
    return {"available": True, "installed": installed, "count": len(inventory)}


def apply_first_episode_direction(project: Path) -> bool:
    """Update only presentation prompts/checklists for the known replay."""
    from .package import write_json

    plan_path = project / "episode_plan.json"
    if not plan_path.is_file():
        return False
    plan = EpisodePlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    if plan.episode_id != EPISODE_ID:
        return False
    if plan.canonical_event_sha256 != EVENT_SHA or len(plan.shots) != len(DIRECTIONS):
        raise ValueError("The first-episode direction does not match its canonical replay")
    for shot, direction in zip(plan.shots, DIRECTIONS):
        shot.seedance_prompt = (
            f"Duration {shot.duration_seconds:.2f} seconds. Full-frame vertical 9:16, 30 fps editorial. "
            "Simplified flat-color 2D graphic combat: bold distinct silhouettes, clean dark contours, simple faces, "
            "minimal costume folds, orange/black Naruto always screen left and broad red/white caped Omni-Man screen right. "
            f"Exact starting pose: {direction['start']}. One dominant recorded action: {direction['action']}. "
            f"Weight transfer: {direction['weight']}. Foot behavior: {direction['feet']}. "
            f"Hand and arm path: {direction['hands']}. Facial intent: {direction['face']}. "
            f"Camera framing and motion: {direction['camera']}; stay south of the action axis. "
            "Background: same sparse blue-hour street, one center road stripe, two blue-gray facades and one right streetlight. "
            f"Lighting: soft key from screen left and a restrained right rim. Ability behavior: {direction['ability']}. "
            f"End/transition: {direction['transition']}. Preserve the approved character boards, costume colors, body proportions, "
            f"camera side, source beat IDs {', '.join(shot.source_beat_ids)}, and recorded outcome {plan.outcome['condition']}."
        )
        shot.negative_prompt = NEGATIVE + (
            " This recorded dodge or miss must remain a miss."
            if direction["beat"] == "grapple dodge" else ""
        )
        checklist = [
            "Matches only the recorded source beat and outcome", "Naruto left / Omni-Man right and same street landmarks",
            "Weight loads, pushes, contacts or releases intentionally", "All visible feet have plausible support",
            "Hands and arms follow one clear path, with no extra limb/contact", "Characters and impact remain readable at phone size",
            "Graphic 2D identity and simplified color blocking remain stable", "Review both first pose and end transition at normal speed",
        ]
        shot.human_review_checklist = checklist
        folder = project / "shots" / shot.shot_id
        write_json(folder / "shot.json", shot)
        (folder / "seedance_prompt.txt").write_text(shot.seedance_prompt + "\n", encoding="utf-8")
        (folder / "seedance_negative_prompt.txt").write_text(shot.negative_prompt + "\n", encoding="utf-8")
        (folder / "human_review_checklist.md").write_text(
            f"# {shot.shot_id} — {direction['beat']}\n\n" + "\n".join(f"- [ ] {item}" for item in checklist) + "\n",
            encoding="utf-8",
        )
    write_json(plan_path, plan)
    (project / "source-truth-note.md").write_text(
        "# Canonical sequence and requested alternate\n\n"
        "The supplied eight-beat punch → slip → counter → parry → Rasengan hand-contact sequence is **not** the saved seed-69 fight. "
        "The deterministic source instead records Naruto's charged-vortex projectile hit, a dodge of Omni-Man's grapple, "
        "Naruto's heavy-strike block, Naruto's transformation, Omni-Man's charge hit, Naruto's energy-orb projectile KO, "
        "and the aftermath. This package uses those events in their recorded order. The blue spiral is a portrayal of the "
        "recorded energy ability; it is not a new hand-contact Rasengan hit. Rasengan is delivered in the hand, whereas a Rasenshuriken can be thrown. "
        "The charged-vortex projectile gets a Rasenshuriken-like presentation; the final Energy Orb remains a generic placeholder projectile, never called Rasengan. "
        "No simulation event, damage, or winner was changed.\n",
        encoding="utf-8",
    )
    (project / "reference-design-spec.md").write_text(
        "# Simplified graphic design lock\n\n"
        "- **Shape language:** Naruto is short and angular with five-to-eight large blond hair spikes; Omni-Man is tall, broad and caped. Separate limbs with visible negative space.\n"
        "- **Palette:** Naruto orange #F68A2F and charcoal #25252B; Omni-Man red #C62828 and off-white #F4F1EA; energy blue #55C9FF. Blue-gray road and facades stay subordinate.\n"
        "- **Edges:** one clean near-black contour and at most one flat shadow per major body mass. No pores, fabric microtexture or realistic gradients.\n"
        "- **Anatomy:** exaggerated reach and compression are allowed; knees, elbows, wrists and feet must remain understandable. No folded ribcages, rubber arms or duplicated fingers.\n"
        "- **Costume:** headband, blond spikes, orange/black jacket and dark sandals identify Naruto; mustache, dark hair, red/white suit and cape identify Omni-Man. Keep patterns stable.\n"
        "- **Face:** eyes, eyebrows, mouth and Naruto cheek marks only. Emotion comes mainly from brows, head tilt and body pose.\n"
        "- **Motion:** short anticipation, purposeful hip-to-shoulder action, clear support-foot release, visible hit or near miss, then recovery. Do not interpolate hands at random.\n"
        "- **Ability distinction:** Rasengan stays in Naruto's hand until body contact. A thrown Rasenshuriken-like wind shuriken may portray `charged_vortex`; `energy_orb` is a generic fictional projectile and is never called Rasengan.\n"
        "- **Forbidden drift:** different hair colors, extra weapons, costume swaps, new injuries, duplicated bodies, phone UI, 3D look or unrecorded hits.\n"
        "- **Seedance references:** supply front, side and three-quarter art for each fighter; use the same style and background boards in every shot. Compare faces, hair, capes and color blocks after each render.\n\n"
        "These are generated development references; a human must approve their appearance and intended use before publication.\n",
        encoding="utf-8",
    )
    guide = [
        "# Manual Seedance upload — eight recorded shots", "",
        "1. Run `wws seedance-stage-refs <project>` and `wws validate-seedance <project>`. Inspect `source-truth-note.md` and every generated keyframe before using them.",
        "2. For each shot in the table, upload `shots/shot_###/keyframe.png` as the start image. Include the six staged boards `naruto_front.png`, `naruto_side.png`, `naruto_three_quarter.png`, `omniman_front.png`, `omniman_side.png`, `omniman_three_quarter.png` from that shot's `character_references/`, plus `style_references/approved_style.png` and the ability image named in the table when present. These files are also listed in each `upload_manifest.json`. Optional end frames should be used only after continuity review.",
        "The shared `rasengan-simple.png` board is for a future hand-contact attack. Do not upload it for the recorded charged-vortex or Energy Orb projectile shots.",
        "3. Paste `seedance_prompt.txt` and `seedance_negative_prompt.txt` from the same shot folder verbatim. Set 9:16 aspect ratio and the listed duration. Use a steady image-to-video mode with the lowest practical motion strength that preserves the described action; exact Seedance setting names are unverified locally.",
        "4. Render one shot at a time. Review at normal speed on a phone: identity, limb count, support feet, action direction, hit/miss, effect scale, landmarks, and the ending pose. Reject and regenerate if the motion adds a hit, swaps identity, skates, tangles limbs, changes costume, hides the impact, or flips the camera axis.",
        "5. Match the ending pose to the next shot's `continuity_start.json`. Keep screen left/right and lighting stable. Hard cuts on motion are preferred; do not rely on an unapproved generated bridge.",
        "6. Place approved clips in `clips/shot_###.mp4`. In `clips.txt`, write one line per clip in order, for example `file 'clips/shot_001.mp4'` through `file 'clips/shot_008.mp4'`. After normalizing clips to the same codec/frame rate if needed, assemble at 1080×1920 / 30 fps with `ffmpeg -f concat -safe 0 -i clips.txt -vf scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30 -c:v libx264 -pix_fmt yuv420p final.mp4`. Review every cut before sharing.",
        "", "| Shot | Recorded beat | Seconds | Start image | Ability image | Next transition |", "|---|---|---:|---|---|---|",
    ]
    for shot, direction in zip(plan.shots, DIRECTIONS):
        ability = [name for name in shot.required_reference_images if name.startswith("ability_references/")]
        ability_cell = f"`shots/{shot.shot_id}/{ability[0]}`" if ability else "none"
        guide.append(f"| {shot.shot_id} | {direction['beat']} | {shot.duration_seconds:.2f} | `shots/{shot.shot_id}/keyframe.png` | {ability_cell} | {direction['transition']} |")
    guide += ["", "No Seedance/API call has been made. Generated stills are development art, not approved animation."]
    (project / "seedance-manual-upload-guide.md").write_text("\n".join(guide) + "\n", encoding="utf-8")
    return True
