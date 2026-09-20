"""Provider-neutral contracts compiled into a standalone Blender scene script."""

from typing import Literal

from pydantic import Field, model_validator

from whowouldwin.cinematic.episodes.schemas import Schema

ActionName = Literal[
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
]

TrajectoryName = Literal[
    "stationary",
    "linear_blitz",
    "accelerating_blitz",
    "decelerating_approach",
    "curved_approach",
    "aerial_arc",
    "launch_trajectory",
    "rotational_launch",
    "knockback_trajectory",
    "ground_skid",
    "wall_impact",
    "recovery_landing",
]

ClipName = Literal[
    "combat_idle",
    "stance",
    "step_forward",
    "step_back",
    "sprint",
    "dash",
    "aerial_travel",
    "jab",
    "cross",
    "heavy_cross",
    "hook",
    "uppercut",
    "body_punch",
    "front_kick",
    "roundhouse",
    "flying_punch",
    "aerial_kick",
    "downward_strike",
    "dodge_left",
    "dodge_right",
    "backstep",
    "duck",
    "lean_dodge",
    "block_high",
    "block_body",
    "hit_head",
    "hit_body",
    "heavy_hit",
    "stagger",
    "spin_reaction",
    "launch_backward",
    "launch_upward",
    "airborne_tumble",
    "wall_impact",
    "ground_impact",
    "hard_landing",
    "landing_recoil",
    "ground_skid",
    "get_up",
    "aerial_recovery",
]

PoseName = Literal[
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
]

CameraBehavior = Literal[
    "wide_establishing",
    "tracking",
    "orbit",
    "push_in",
    "pull_out",
    "close_up",
    "over_shoulder",
    "low_angle",
    "high_angle",
    "whip_pan",
    "impact_camera",
    "knockback_tracking",
]

EffectName = Literal[
    "impact_flash",
    "shockwave",
    "dust",
    "debris",
    "speed_trails",
    "motion_streaks",
    "energy_trail",
    "smoke",
    "wall_fracture",
]


class Vector3(Schema):
    x: float
    y: float
    z: float


class CharacterBinding(Schema):
    character_id: str
    display_name: str
    source_fighter_id: str
    color: tuple[float, float, float]
    model_path: str | None = None
    action_overrides: dict[ActionName, str] = Field(default_factory=dict)
    rig_adapter_id: str = "generic_humanoid_v2"
    character_package: str | None = None


class HumanoidRigAdapter(Schema):
    adapter_id: str
    standard_to_target: dict[str, str]
    root_object: str | None = None


class TimeWarpSettings(Schema):
    anticipation_scale: float = Field(default=1.0, gt=0, le=4)
    attack_scale: float = Field(default=1.0, gt=0, le=4)
    impact_hold_frames: int = Field(default=0, ge=0, le=6)
    followthrough_scale: float = Field(default=1.0, gt=0, le=4)
    recovery_scale: float = Field(default=1.0, gt=0, le=4)


class ClipVariation(Schema):
    mirrored: bool = False
    pose_amplitude: float = Field(default=1.0, ge=0.75, le=1.3)
    torso_twist_degrees: float = Field(default=0.0, ge=-20, le=20)
    attack_angle_degrees: float = Field(default=0.0, ge=-15, le=15)


class AnimationClipBinding(Schema):
    clip_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    start_frame: int = Field(ge=1)
    end_frame: int = Field(ge=1)
    contact_frame: int | None = Field(default=None, ge=1)
    blend_in_frames: int = Field(default=2, ge=0, le=8)
    blend_out_frames: int = Field(default=2, ge=0, le=8)
    loop: bool = False
    time_warp: TimeWarpSettings = TimeWarpSettings()
    variation: ClipVariation = ClipVariation()

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end_frame < self.start_frame:
            raise ValueError("Animation clip ends before it starts")
        if self.contact_frame is not None and not (
            self.start_frame <= self.contact_frame <= self.end_frame
        ):
            raise ValueError("Clip contact frame must be inside its interval")
        return self


class ReactionSpec(Schema):
    attack_family: str
    impact_direction: Vector3
    relative_power: float = Field(ge=0, le=1)
    selected_family: str


class CombatInstruction(Schema):
    instruction_id: str = Field(pattern=r"^action-[0-9]{3}$")
    action: ActionName
    actor: str
    target: str | None = None
    start_frame: int = Field(ge=1)
    end_frame: int = Field(ge=1)
    start_position: Vector3
    target_position: Vector3
    trajectory: TrajectoryName = "stationary"
    overshoot_position: Vector3 | None = None
    recovery_position: Vector3 | None = None
    contact_position: Vector3 | None = None
    impact_frame: int | None = Field(default=None, ge=1)
    clip_stack: list[AnimationClipBinding] = Field(default_factory=list)
    reaction: ReactionSpec | None = None
    angular_momentum: Vector3 | None = None
    landing_severity: float = Field(default=0.0, ge=0, le=1)
    outcome: Literal[
        "staged",
        "evaded",
        "environment_contact",
        "hit",
        "launched",
        "recovered",
    ]
    intensity: float = Field(ge=0, le=1)
    source_event_ids: list[str]
    source_simulation_time: float | None = Field(default=None, ge=0)
    presentation_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end_frame < self.start_frame:
            raise ValueError("Combat instruction ends before it starts")
        if self.outcome != "staged" and not self.source_event_ids:
            raise ValueError("Non-staged motion requires source-event provenance")
        if self.trajectory == "accelerating_blitz" and not self.overshoot_position:
            raise ValueError("Accelerating blitz requires an overshoot position")
        if self.impact_frame is not None and not (
            self.start_frame <= self.impact_frame <= self.end_frame
        ):
            raise ValueError("Impact frame must be inside instruction interval")
        if any(
            clip.start_frame < self.start_frame or clip.end_frame > self.end_frame
            for clip in self.clip_stack
        ):
            raise ValueError("Animation clip must remain inside its instruction")
        return self


class CameraShot(Schema):
    shot_id: str = Field(pattern=r"^bshot-[0-9]{3}$")
    start_frame: int = Field(ge=1)
    end_frame: int = Field(ge=1)
    behavior: CameraBehavior
    location_start: Vector3
    location_end: Vector3
    target_start: Vector3
    target_end: Vector3
    lens_mm: float = Field(default=50, ge=18, le=120)
    shake: float = Field(default=0, ge=0, le=1)
    hit_stop_frames: int = Field(default=0, ge=0, le=3)
    source_event_ids: list[str] = Field(default_factory=list)
    description: str

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end_frame < self.start_frame:
            raise ValueError("Camera shot ends before it starts")
        return self


class VFXInstruction(Schema):
    effect_id: str = Field(pattern=r"^vfx-[0-9]{3}$")
    effect: EffectName
    frame: int = Field(ge=1)
    end_frame: int = Field(ge=1)
    position: Vector3
    direction: Vector3 = Vector3(x=1, y=0, z=0)
    intensity: float = Field(ge=0, le=1)
    source_event_ids: list[str]
    authority: Literal["simulation", "presentation"] = "presentation"
    notes: str

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end_frame < self.frame:
            raise ValueError("VFX ends before it starts")
        return self


class BlenderRenderSettings(Schema):
    fps: int = Field(default=30, ge=24, le=60)
    duration_seconds: float = Field(default=12, ge=10, le=15)
    preview_width: int = Field(default=360, ge=180, le=1080)
    preview_height: int = Field(default=640, ge=320, le=1920)
    final_width: int = Field(default=1080, ge=360, le=2160)
    final_height: int = Field(default=1920, ge=640, le=3840)
    preview_samples: int = Field(default=16, ge=1, le=64)
    final_samples: int = Field(default=64, ge=8, le=256)
    motion_blur: bool = True

    @model_validator(mode="after")
    def vertical(self):
        for width, height in (
            (self.preview_width, self.preview_height),
            (self.final_width, self.final_height),
        ):
            if width % 2 or height % 2 or abs(width / height - 9 / 16) > 0.006:
                raise ValueError("Blender outputs must be even 9:16 resolutions")
        return self


class BlenderSequencePlan(Schema):
    schema_version: Literal[1, 2, 3] = 2
    plan_id: str
    source_checksum: str
    source_outcome_digest: str
    source_event_log: str
    random_seed: int
    settings: BlenderRenderSettings = BlenderRenderSettings()
    characters: dict[str, CharacterBinding]
    instructions: list[CombatInstruction]
    camera_shots: list[CameraShot]
    effects: list[VFXInstruction]
    required_action_primitives: list[ActionName]
    required_pose_primitives: list[PoseName] = Field(default_factory=list)
    rig_adapters: dict[str, HumanoidRigAdapter] = Field(default_factory=dict)
    required_animation_clips: list[str] = Field(default_factory=list)
    action_library_version: str | None = None
    environment_id: str = "procedural_damaged_city_v1"
    style: str = (
        "Stylized 3D anime combat, strong silhouettes, hard rim light, "
        "exaggerated poses, fast readable action."
    )

    @model_validator(mode="after")
    def coherent(self):
        final = round(self.settings.duration_seconds * self.settings.fps)
        if len(self.characters) != 2:
            raise ValueError("The proof sequence requires exactly two characters")
        if set(self.characters) != {"fighter_a", "fighter_b"}:
            raise ValueError("Proof character bindings must be fighter_a and fighter_b")
        if not self.camera_shots or self.camera_shots[0].start_frame != 1:
            raise ValueError("Camera edit must start on frame 1")
        if self.camera_shots[-1].end_frame != final:
            raise ValueError("Camera edit must exactly fill the sequence")
        for left, right in zip(self.camera_shots, self.camera_shots[1:]):
            if right.start_frame != left.end_frame + 1:
                raise ValueError("Camera shots must be contiguous without overlap")
        known = set(self.characters)
        if any(
            i.actor not in known or (i.target and i.target not in known)
            for i in self.instructions
        ):
            raise ValueError("Instruction refers to an unknown character")
        used = {i.action for i in self.instructions}
        if not used.issubset(set(self.required_action_primitives)):
            raise ValueError("Required action registry omits an instruction")
        if self.schema_version == 2:
            if not self.required_pose_primitives:
                raise ValueError("Version 2 plans require a pose registry")
            if any(
                i.action in {"punch", "heavy_punch", "kick"}
                and i.contact_position is None
                for i in self.instructions
            ):
                raise ValueError("Version 2 contact attacks require target points")
        if self.schema_version == 3:
            if set(self.rig_adapters) != set(self.characters):
                raise ValueError(
                    "Version 3 plans require one rig adapter per character"
                )
            used_clips = {
                clip.clip_id
                for instruction in self.instructions
                for clip in instruction.clip_stack
            }
            if not used_clips or not used_clips.issubset(
                set(self.required_animation_clips)
            ):
                raise ValueError("Version 3 clip registry omits a used animation")
            if any(not instruction.clip_stack for instruction in self.instructions):
                raise ValueError(
                    "Version 3 instructions require authored clip bindings"
                )
        return self


class BlenderProjectManifest(Schema):
    schema_version: Literal[1] = 1
    plan_sha256: str
    runtime_sha256: str
    asset_runtime_sha256: str | None = None
    source_checksum: str
    created_at: str
    blender_executable: str | None = None
    mode: Literal["planned", "preview", "final"] = "planned"
    blend_file: str = "scene.blend"
    video_file: str | None = None
    video_sha256: str | None = None
