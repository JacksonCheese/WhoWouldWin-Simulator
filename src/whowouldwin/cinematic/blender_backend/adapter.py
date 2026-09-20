"""Convert an existing event log into a compact, deterministic 3D proof sequence."""

from whowouldwin.cinematic.episodes.schemas import EventLog
from whowouldwin.simulation.replay import digest

from .action_library import (
    CLIP_NAMES,
    choose_reaction,
    default_clip_for_action,
    identity_bone_map,
)
from .schemas import (
    AnimationClipBinding,
    BlenderRenderSettings,
    BlenderSequencePlan,
    CameraShot,
    CharacterBinding,
    CombatInstruction,
    ClipVariation,
    HumanoidRigAdapter,
    ReactionSpec,
    TimeWarpSettings,
    VFXInstruction,
    Vector3,
)

ACTION_PRIMITIVES = (
    "idle",
    "combat_stance",
    "dash",
    "sprint",
    "jump",
    "aerial_movement",
    "punch",
    "heavy_punch",
    "kick",
    "dodge",
    "block",
    "hit_reaction",
    "knockback",
    "launch",
    "fall",
    "landing",
    "recovery",
    "wall_impact",
)

POSE_PRIMITIVES = (
    "idle",
    "combat_stance",
    "dash_start",
    "dash_travel",
    "dash_stop",
    "punch_anticipation",
    "punch_contact",
    "punch_followthrough",
    "heavy_punch",
    "kick",
    "dodge_left",
    "dodge_right",
    "air_dodge",
    "block",
    "hit_light",
    "hit_heavy",
    "launch",
    "airborne_knockback",
    "wall_impact",
    "ground_impact",
    "landing",
    "recovery",
)


def v(x, y, z):
    return Vector3(x=x, y=y, z=z)


def _source_pair(log: EventLog):
    """Pick a recorded dodge followed by a counter-hit from its defender."""
    events = log.events
    for index, dodge in enumerate(events):
        if (
            dodge.event_type != "AttackDodged"
            or not dodge.actor_id
            or not dodge.target_ids
        ):
            continue
        attacker = dodge.actor_id
        defender = dodge.target_ids[0]
        for hit in events[index + 1 :]:
            if hit.simulation_time - dodge.simulation_time > 2:
                break
            if (
                hit.event_type == "AttackHit"
                and hit.actor_id == defender
                and hit.target_ids == [attacker]
            ):
                knockback = next(
                    (
                        e
                        for e in events
                        if e.event_type == "Knockback"
                        and e.actor_id == defender
                        and e.target_ids == [attacker]
                        and e.ability_id == hit.ability_id
                        and abs(e.simulation_time - hit.simulation_time) < 1e-6
                    ),
                    None,
                )
                if knockback:
                    return dodge, hit, knockback
    raise ValueError(
        "A Blender proof needs a recorded dodge followed within two seconds by the defender's hit and knockback"
    )


def build_prototype_plan(
    log: EventLog,
    *,
    source_event_log: str = "events.json",
    settings: BlenderRenderSettings | None = None,
) -> BlenderSequencePlan:
    """Create a 12-second edit from three canonical source events.

    Spatial distances are presentation-space remapping. The wall fracture is labelled
    presentation-only because terrain damage is not simulated. No extra fighter hit or
    change to the source outcome is introduced.
    """
    settings = settings or BlenderRenderSettings()
    if settings.fps != 30 or settings.duration_seconds != 12:
        raise ValueError(
            "Prototype choreography currently targets exactly 12 seconds at 30 fps"
        )
    dodge, hit, knockback = _source_pair(log)
    attacker = dodge.actor_id
    defender = dodge.target_ids[0]
    dodge_ids = [dodge.event_id]
    hit_ids = [hit.event_id]
    knockback_ids = [knockback.event_id]
    a0, wall = v(-4.8, 0, 0), v(4.9, 0, 0)
    b0, bside, bcounter = v(2.4, 0, 0), v(2.4, -2.3, 0), v(3.7, -0.35, 0)
    landing = v(-3.0, 1.3, 0)
    actions = [
        CombatInstruction(
            instruction_id="action-001",
            action="combat_stance",
            actor="fighter_a",
            target="fighter_b",
            start_frame=1,
            end_frame=54,
            start_position=a0,
            target_position=a0,
            outcome="staged",
            intensity=0.35,
            source_event_ids=[],
            presentation_notes=[
                "Opening pose derived from participants, not a combat event."
            ],
        ),
        CombatInstruction(
            instruction_id="action-002",
            action="combat_stance",
            actor="fighter_b",
            target="fighter_a",
            start_frame=1,
            end_frame=54,
            start_position=b0,
            target_position=b0,
            outcome="staged",
            intensity=0.35,
            source_event_ids=[],
        ),
        CombatInstruction(
            instruction_id="action-003",
            action="dash",
            actor="fighter_a",
            target="fighter_b",
            start_frame=55,
            end_frame=100,
            start_position=a0,
            target_position=b0,
            trajectory="accelerating_blitz",
            overshoot_position=wall,
            recovery_position=wall,
            outcome="evaded",
            intensity=0.96,
            source_event_ids=dodge_ids,
            source_simulation_time=dodge.simulation_time,
            presentation_notes=[
                f"Recorded {dodge.ability_id} attempt was dodged.",
                "Rapid root motion and overshoot portray the same failed attack.",
            ],
        ),
        CombatInstruction(
            instruction_id="action-004",
            action="dodge",
            actor="fighter_b",
            target="fighter_a",
            start_frame=73,
            end_frame=108,
            start_position=b0,
            target_position=bside,
            trajectory="curved_approach",
            overshoot_position=v(2.2, -2.65, 0.1),
            recovery_position=bside,
            outcome="evaded",
            intensity=0.92,
            source_event_ids=dodge_ids,
            source_simulation_time=dodge.simulation_time,
        ),
        CombatInstruction(
            instruction_id="action-005",
            action="heavy_punch",
            actor="fighter_b",
            target="fighter_a",
            start_frame=128,
            end_frame=177,
            start_position=bside,
            target_position=bcounter,
            trajectory="accelerating_blitz",
            overshoot_position=v(3.92, -0.2, 0),
            recovery_position=bcounter,
            contact_position=v(4.67, -0.08, 1.47),
            outcome="hit",
            intensity=0.94,
            source_event_ids=hit_ids,
            source_simulation_time=hit.simulation_time,
            presentation_notes=[
                f"Generic heavy punch maps recorded {hit.ability_id}; character overrides may replace it later."
            ],
        ),
        CombatInstruction(
            instruction_id="action-006",
            action="hit_reaction",
            actor="fighter_a",
            target="fighter_b",
            start_frame=161,
            end_frame=178,
            start_position=wall,
            target_position=wall,
            trajectory="wall_impact",
            outcome="hit",
            intensity=0.94,
            source_event_ids=hit_ids,
            source_simulation_time=hit.simulation_time,
        ),
        CombatInstruction(
            instruction_id="action-007",
            action="launch",
            actor="fighter_a",
            target="fighter_b",
            start_frame=178,
            end_frame=238,
            start_position=wall,
            target_position=v(-2.8, 1.3, 4.8),
            trajectory="launch_trajectory",
            overshoot_position=v(0.5, 0.65, 5.5),
            outcome="launched",
            intensity=0.98,
            source_event_ids=knockback_ids,
            source_simulation_time=knockback.simulation_time,
        ),
        CombatInstruction(
            instruction_id="action-008",
            action="aerial_movement",
            actor="fighter_a",
            target="fighter_b",
            start_frame=238,
            end_frame=258,
            start_position=v(-2.8, 1.3, 4.8),
            target_position=v(-3.2, 1.3, 1.0),
            trajectory="aerial_arc",
            overshoot_position=v(-3.3, 1.5, 5.15),
            outcome="recovered",
            intensity=0.82,
            source_event_ids=knockback_ids,
            source_simulation_time=knockback.simulation_time,
            presentation_notes=[
                "Aerial rotation is a visual extension of recorded knockback."
            ],
        ),
        CombatInstruction(
            instruction_id="action-009",
            action="landing",
            actor="fighter_a",
            target="fighter_b",
            start_frame=258,
            end_frame=285,
            start_position=v(-3.2, 1.3, 1.0),
            target_position=landing,
            trajectory="recovery_landing",
            overshoot_position=v(-3.15, 1.3, -0.38),
            recovery_position=landing,
            outcome="recovered",
            intensity=0.8,
            source_event_ids=knockback_ids,
            source_simulation_time=knockback.simulation_time,
        ),
        CombatInstruction(
            instruction_id="action-010",
            action="recovery",
            actor="fighter_a",
            target="fighter_b",
            start_frame=286,
            end_frame=360,
            start_position=landing,
            target_position=landing,
            outcome="recovered",
            intensity=0.35,
            source_event_ids=knockback_ids,
            source_simulation_time=knockback.simulation_time,
        ),
        CombatInstruction(
            instruction_id="action-011",
            action="combat_stance",
            actor="fighter_b",
            target="fighter_a",
            start_frame=178,
            end_frame=360,
            start_position=bcounter,
            target_position=bcounter,
            outcome="staged",
            intensity=0.5,
            source_event_ids=[],
        ),
    ]
    shots = [
        CameraShot(
            shot_id="bshot-001",
            start_frame=1,
            end_frame=54,
            behavior="wide_establishing",
            location_start=v(-1, -22, 5.5),
            location_end=v(-1, -20, 4.8),
            target_start=v(-1, 0, 1.3),
            target_end=v(-1, 0, 1.3),
            lens_mm=30,
            description="Low wide faceoff with architectural scale.",
        ),
        CameraShot(
            shot_id="bshot-002",
            start_frame=55,
            end_frame=90,
            behavior="tracking",
            location_start=v(-5, -14, 3.2),
            location_end=v(2, -14, 2.8),
            target_start=v(-3, 0, 1.2),
            target_end=v(2, 0, 1.2),
            lens_mm=28,
            shake=0.12,
            source_event_ids=dodge_ids,
            description="Fast lateral follow on Fighter A's recorded failed rush.",
        ),
        CameraShot(
            shot_id="bshot-003",
            start_frame=91,
            end_frame=111,
            behavior="close_up",
            location_start=v(1.7, -8, 2.4),
            location_end=v(2.8, -7, 2.1),
            target_start=v(2.4, -1.3, 1.4),
            target_end=v(3.5, -1.4, 1.2),
            lens_mm=48,
            shake=0.2,
            source_event_ids=dodge_ids,
            description="Close dodge and attacker overshoot.",
        ),
        CameraShot(
            shot_id="bshot-004",
            start_frame=112,
            end_frame=132,
            behavior="whip_pan",
            location_start=v(-0.5, -16, 3.8),
            location_end=v(1.8, -14, 3.1),
            target_start=v(2.4, -1.5, 1.4),
            target_end=v(5.8, 0, 1.4),
            lens_mm=30,
            shake=0.48,
            source_event_ids=dodge_ids,
            description="Whip pan to presentation-only wall impact.",
        ),
        CameraShot(
            shot_id="bshot-005",
            start_frame=133,
            end_frame=162,
            behavior="over_shoulder",
            location_start=v(0, -15, 3.4),
            location_end=v(1.8, -13, 2.8),
            target_start=v(4.2, -0.2, 1.4),
            target_end=v(4.9, 0, 1.3),
            lens_mm=32,
            shake=0.1,
            source_event_ids=hit_ids,
            description="Fighter B closes from behind for the recorded counter-hit.",
        ),
        CameraShot(
            shot_id="bshot-006",
            start_frame=163,
            end_frame=177,
            behavior="impact_camera",
            location_start=v(1, -13, 3),
            location_end=v(1.6, -12, 2.7),
            target_start=v(4.9, -0.15, 1.35),
            target_end=v(4.9, -0.15, 1.35),
            lens_mm=35,
            shake=0.9,
            hit_stop_frames=3,
            source_event_ids=hit_ids,
            description="Tight impact with three-frame hold.",
        ),
        CameraShot(
            shot_id="bshot-007",
            start_frame=178,
            end_frame=231,
            behavior="knockback_tracking",
            location_start=v(4, -12, 4),
            location_end=v(-2, -14, 6),
            target_start=v(4.9, 0, 1.5),
            target_end=v(-2, 1, 4),
            lens_mm=30,
            shake=0.35,
            source_event_ids=knockback_ids,
            description="Track Fighter A's recorded knockback as an airborne launch.",
        ),
        CameraShot(
            shot_id="bshot-008",
            start_frame=232,
            end_frame=285,
            behavior="high_angle",
            location_start=v(-3, -12, 8),
            location_end=v(-3, -11, 5.5),
            target_start=v(-3, 1, 2),
            target_end=landing,
            lens_mm=34,
            shake=0.22,
            source_event_ids=knockback_ids,
            description="High angle follows recovery into hard landing.",
        ),
        CameraShot(
            shot_id="bshot-009",
            start_frame=286,
            end_frame=360,
            behavior="pull_out",
            location_start=v(-1, -18, 4.5),
            location_end=v(0, -22, 6.5),
            target_start=v(0, 0, 1.2),
            target_end=v(0, 0, 1.2),
            lens_mm=30,
            source_event_ids=knockback_ids,
            description="Dramatic aftermath with both silhouettes and damaged set dressing.",
        ),
    ]
    effects = [
        VFXInstruction(
            effect_id="vfx-001",
            effect="speed_trails",
            frame=55,
            end_frame=105,
            position=v(-1, 0, 1.2),
            direction=v(1, 0, 0),
            intensity=0.9,
            source_event_ids=dodge_ids,
            authority="presentation",
            notes="Readable speed indication for recorded attack attempt.",
        ),
        VFXInstruction(
            effect_id="vfx-002",
            effect="wall_fracture",
            frame=116,
            end_frame=360,
            position=v(5.6, 0, 1.2),
            direction=v(-1, 0, 0),
            intensity=0.8,
            source_event_ids=dodge_ids,
            authority="presentation",
            notes="Set dressing only; simulation records no terrain damage.",
        ),
        VFXInstruction(
            effect_id="vfx-003",
            effect="debris",
            frame=116,
            end_frame=155,
            position=v(5.5, 0, 1.2),
            direction=v(-1, 0, 1),
            intensity=0.75,
            source_event_ids=dodge_ids,
            authority="presentation",
            notes="Fragments accompany the visual overshoot.",
        ),
        VFXInstruction(
            effect_id="vfx-004",
            effect="impact_flash",
            frame=163,
            end_frame=168,
            position=v(4.9, -0.1, 1.45),
            direction=v(-1, 0, 0),
            intensity=1,
            source_event_ids=hit_ids,
            authority="simulation",
            notes="Marks the single recorded counter-hit.",
        ),
        VFXInstruction(
            effect_id="vfx-005",
            effect="shockwave",
            frame=163,
            end_frame=178,
            position=v(4.9, -0.1, 1.45),
            direction=v(-1, 0, 0),
            intensity=0.95,
            source_event_ids=hit_ids,
            authority="presentation",
            notes="Emphasizes the recorded hit without adding damage.",
        ),
        VFXInstruction(
            effect_id="vfx-006",
            effect="motion_streaks",
            frame=178,
            end_frame=238,
            position=v(1, 1, 3),
            direction=v(-1, 0, 1),
            intensity=0.8,
            source_event_ids=knockback_ids,
            authority="presentation",
            notes="Airborne launch trail.",
        ),
        VFXInstruction(
            effect_id="vfx-007",
            effect="dust",
            frame=277,
            end_frame=312,
            position=landing,
            direction=v(0, 0, 1),
            intensity=0.85,
            source_event_ids=knockback_ids,
            authority="presentation",
            notes="Landing dust; no new combat damage.",
        ),
    ]
    return BlenderSequencePlan(
        schema_version=2,
        plan_id=f"generic_blender_poc_{log.simulation_seed}_{log.source_checksum[:8]}",
        source_checksum=log.source_checksum,
        source_outcome_digest=digest(log.outcome),
        source_event_log=source_event_log,
        random_seed=int(log.source_checksum[:8], 16),
        settings=settings,
        characters={
            "fighter_a": CharacterBinding(
                character_id="fighter_a",
                display_name="Fighter A",
                source_fighter_id=attacker,
                color=(0.95, 0.18, 0.12),
            ),
            "fighter_b": CharacterBinding(
                character_id="fighter_b",
                display_name="Fighter B",
                source_fighter_id=defender,
                color=(0.05, 0.55, 1.0),
            ),
        },
        instructions=actions,
        camera_shots=shots,
        effects=effects,
        required_action_primitives=sorted({a.action for a in actions}),
        required_pose_primitives=list(POSE_PRIMITIVES),
    )


def _clip_binding(instruction: CombatInstruction) -> AnimationClipBinding:
    """Choose and phase-configure the generic authored clip for one action."""
    clip_id = default_clip_for_action(instruction.action, actor=instruction.actor)
    contact = instruction.impact_frame
    warp = TimeWarpSettings()
    variation = ClipVariation()
    if instruction.action == "dash":
        warp = TimeWarpSettings(
            anticipation_scale=0.7,
            attack_scale=0.32,
            followthrough_scale=0.55,
            recovery_scale=0.7,
        )
        variation = ClipVariation(pose_amplitude=1.1, torso_twist_degrees=3)
    elif instruction.action == "dodge":
        warp = TimeWarpSettings(
            anticipation_scale=0.55,
            attack_scale=0.38,
            followthrough_scale=0.7,
            recovery_scale=0.8,
        )
        variation = ClipVariation(pose_amplitude=1.08, torso_twist_degrees=-4)
    elif instruction.action == "heavy_punch":
        warp = TimeWarpSettings(
            anticipation_scale=1.15,
            attack_scale=0.32,
            impact_hold_frames=3,
            followthrough_scale=0.7,
            recovery_scale=0.9,
        )
        variation = ClipVariation(
            pose_amplitude=1.12,
            torso_twist_degrees=-8,
            attack_angle_degrees=3,
        )
    elif instruction.action in {"hit_reaction", "launch"}:
        warp = TimeWarpSettings(
            anticipation_scale=0.3,
            attack_scale=0.3,
            impact_hold_frames=3 if instruction.action == "hit_reaction" else 0,
            followthrough_scale=0.8,
            recovery_scale=0.55,
        )
        variation = ClipVariation(pose_amplitude=1.16, torso_twist_degrees=7)
    elif instruction.action in {"landing", "aerial_movement"}:
        warp = TimeWarpSettings(
            anticipation_scale=0.65,
            attack_scale=0.5,
            impact_hold_frames=2 if instruction.action == "landing" else 0,
            followthrough_scale=0.8,
            recovery_scale=0.85,
        )
        variation = ClipVariation(pose_amplitude=1.12, torso_twist_degrees=4)
    return AnimationClipBinding(
        clip_id=clip_id,
        start_frame=instruction.start_frame,
        end_frame=instruction.end_frame,
        contact_frame=contact,
        blend_in_frames=2,
        blend_out_frames=3,
        loop=instruction.action in {"idle", "combat_stance"}
        and instruction.end_frame - instruction.start_frame > 45,
        time_warp=warp,
        variation=variation,
    )


def build_hybrid_plan(
    log: EventLog,
    *,
    source_event_log: str = "events.json",
    settings: BlenderRenderSettings | None = None,
) -> BlenderSequencePlan:
    """Upgrade the V2 choreography with authored-action/NLA playback metadata."""
    base = build_prototype_plan(
        log, source_event_log=source_event_log, settings=settings
    )
    data = base.model_dump(mode="json")
    data["schema_version"] = 3
    data["plan_id"] = (
        f"hybrid_blender_v3_{log.simulation_seed}_{log.source_checksum[:8]}"
    )
    data["action_library_version"] = "generic_humanoid_authored_v1"

    dash = next(raw for raw in data["instructions"] if raw["action"] == "dash")
    wall = {
        "instruction_id": "action-012",
        "action": "wall_impact",
        "actor": "fighter_a",
        "target": None,
        "start_frame": 100,
        "end_frame": 127,
        "start_position": dash["recovery_position"],
        "target_position": dash["recovery_position"],
        "trajectory": "wall_impact",
        "overshoot_position": None,
        "recovery_position": dash["recovery_position"],
        "contact_position": None,
        "impact_frame": 116,
        "clip_stack": [],
        "reaction": None,
        "angular_momentum": None,
        "landing_severity": 0.0,
        "outcome": "environment_contact",
        "intensity": 0.9,
        "source_event_ids": dash["source_event_ids"],
        "source_simulation_time": dash["source_simulation_time"],
        "presentation_notes": [
            "Presentation-only authored wall collision after the recorded missed rush."
        ],
    }
    data["instructions"].insert(4, wall)
    data["required_action_primitives"] = sorted(
        {*data["required_action_primitives"], "wall_impact"}
    )

    used_clips: set[str] = set()
    reaction = choose_reaction(
        attack_family="cross", direction=(-1.0, 0.0, 0.35), relative_power=0.94
    )
    for raw in data["instructions"]:
        action = raw["action"]
        if action == "dash":
            raw["impact_frame"] = 87
        elif action in {"heavy_punch", "hit_reaction"}:
            raw["impact_frame"] = 163
        elif action == "launch":
            raw["impact_frame"] = 178
            raw["trajectory"] = "rotational_launch"
            raw["angular_momentum"] = {"x": 0.45, "y": 1.35, "z": 0.55}
        elif action == "aerial_movement":
            raw["angular_momentum"] = {"x": 0.25, "y": 0.8, "z": 0.35}
        elif action == "landing":
            raw["impact_frame"] = 277
            raw["landing_severity"] = 0.9

        upgraded = CombatInstruction.model_validate(raw)
        binding = _clip_binding(upgraded)
        bindings = [binding]
        if action == "recovery":
            split = min(upgraded.end_frame - 10, upgraded.start_frame + 34)
            bindings = [
                binding.model_copy(update={"end_frame": split, "loop": False}),
                AnimationClipBinding(
                    clip_id="combat_idle",
                    start_frame=split - 3,
                    end_frame=upgraded.end_frame,
                    blend_in_frames=4,
                    blend_out_frames=1,
                    loop=True,
                ),
            ]
        raw["clip_stack"] = [item.model_dump(mode="json") for item in bindings]
        used_clips.update(item.clip_id for item in bindings)
        if action in {"hit_reaction", "launch"}:
            raw["reaction"] = ReactionSpec(
                attack_family="cross",
                impact_direction=v(-1, 0, 0.35),
                relative_power=0.94,
                selected_family=reaction.family,
            ).model_dump(mode="json")

    # Keep effects as timing guides, while making the unassisted body motion readable.
    for effect in data["effects"]:
        effect["intensity"] = round(effect["intensity"] * 0.55, 3)

    identity = identity_bone_map()
    data["rig_adapters"] = {
        character: HumanoidRigAdapter(
            adapter_id="generic_humanoid_v2",
            standard_to_target=identity,
        ).model_dump(mode="json")
        for character in data["characters"]
    }
    data["required_animation_clips"] = list(CLIP_NAMES)
    return BlenderSequencePlan.model_validate(data)
