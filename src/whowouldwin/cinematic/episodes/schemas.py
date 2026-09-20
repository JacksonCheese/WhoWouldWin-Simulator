"""Versioned, provider-neutral episode contracts. Combat facts and visual interpretations are separate."""

from enum import StrEnum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Schema(BaseModel):
    model_config = ConfigDict(
        extra="forbid", allow_inf_nan=False, validate_default=True
    )


class Point(Schema):
    x: float
    y: float


class FighterState(Schema):
    health: float
    health_fraction: float
    energy: float
    stamina: float
    position: Point
    velocity: Point
    transformation: str | None = None
    flying: bool = False
    statuses: list[str] = Field(default_factory=list)


class CinematicBattleEvent(Schema):
    event_id: str
    simulation_time: float = Field(ge=0)
    actor_id: str | None = None
    target_ids: list[str] = Field(default_factory=list)
    event_type: str
    ability_id: str | None = None
    success: bool | None = None
    damage: float = Field(default=0, ge=0)
    health_after_damage: float | None = None
    impact_score: float = Field(default=0, ge=0, le=1)
    location: Point | None = None
    positions: dict[str, Point] = Field(default_factory=dict)
    velocities: dict[str, Point] = Field(default_factory=dict)
    actor_state_before: FighterState | None = None
    actor_state_after: FighterState | None = None
    target_state_before: dict[str, FighterState] = Field(default_factory=dict)
    target_state_after: dict[str, FighterState] = Field(default_factory=dict)
    environment_effect: dict[str, Any] | None = None
    narrative_tags: list[str] = Field(default_factory=list)
    source_event_ids: list[str]
    source_index: int
    source_tick: int
    source_values: dict[str, Any] = Field(default_factory=dict)
    derivations: dict[str, str] = Field(default_factory=dict)


class StateFrame(Schema):
    simulation_time: float
    fighters: dict[str, FighterState]


class EventLog(Schema):
    schema_version: Literal[1] = 1
    source_checksum: str
    simulation_seed: int
    fighter_versions: dict[str, str]
    fighter_names: dict[str, str]
    fighter_profile_ids: dict[str, str]
    state_timeline: list[StateFrame]
    initial_states: dict[str, FighterState]
    events: list[CinematicBattleEvent]
    outcome: dict[str, Any]


class SelectorSettings(Schema):
    group_window: float = Field(default=0.4, ge=0, le=2)
    minimum_score: float = Field(default=0.23, ge=0)
    max_moments: int = Field(default=28, ge=3, le=100)
    repetition_penalty: float = Field(default=0.07, ge=0, le=1)
    near_defeat_fraction: float = Field(default=0.2, gt=0, lt=1)


class CinematicMoment(Schema):
    moment_id: str
    source_event_ids: list[str]
    start_time: float
    end_time: float
    importance_score: float = Field(ge=0)
    score_components: dict[str, float]
    moment_type: str
    participants: list[str]
    summary: str
    continuity_consequences: list[str]


class AssetReference(Schema):
    asset_id: str
    path: str
    role: str = "appearance_reference"
    rights_note: str = "Development fixture; verify rights before production use."


class VisualProfile(Schema):
    character_id: str
    version_id: str
    development_fixture: bool = True
    appearance_description: str
    body_description: str
    face_description: str
    hair_description: str
    costume_description: str
    color_palette: list[str] = Field(min_length=1)
    distinctive_features: list[str] = Field(default_factory=list)
    reference_image_paths: list[AssetReference] = Field(default_factory=list)
    transformation_visuals: dict[str, str] = Field(default_factory=dict)
    prohibited_visual_changes: list[str]
    prompt_aliases: list[str]


class ArenaVisualProfile(Schema):
    arena_id: str
    version_id: str = "fixture-v1"
    development_fixture: bool = True
    description: str
    architecture: str
    terrain: str
    lighting: str
    weather: str
    time_of_day: str
    color_palette: list[str] = Field(min_length=1)
    destructible_features: list[str] = Field(default_factory=list)
    reference_assets: list[AssetReference] = Field(default_factory=list)
    continuity_state: dict[str, Any] = Field(default_factory=dict)


class CharacterContinuity(Schema):
    transformation: str | None
    costume_version: str
    visible_injuries: list[str] = Field(default_factory=list)
    clothing_damage: list[str] = Field(default_factory=list)
    surface_wear: str = "clean"
    wear_basis: str = (
        "Presentational scuff level derived from lowest recorded health fraction; no anatomical injury inferred."
    )
    location: Point
    relative_position: str
    weapons_items: list[str] | None = None
    persistent_effects: list[str]
    health: float
    health_fraction: float


class ContinuityState(Schema):
    simulation_time: float
    characters: dict[str, CharacterContinuity]
    lighting: str
    time_of_day: str
    weather: str
    arena_state: dict[str, Any]
    environmental_destruction: list[str] = Field(default_factory=list)
    presentation_notes: list[str] = Field(default_factory=list)


class ShotType(StrEnum):
    ESTABLISHING = "ESTABLISHING"
    WIDE_ACTION = "WIDE_ACTION"
    MEDIUM_ACTION = "MEDIUM_ACTION"
    CLOSE_UP = "CLOSE_UP"
    EXTREME_CLOSE_UP = "EXTREME_CLOSE_UP"
    OVER_SHOULDER = "OVER_SHOULDER"
    POV = "POV"
    LOW_ANGLE = "LOW_ANGLE"
    HIGH_ANGLE = "HIGH_ANGLE"
    AERIAL = "AERIAL"
    IMPACT = "IMPACT"
    REACTION = "REACTION"
    TRANSFORMATION = "TRANSFORMATION"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    FINISHER = "FINISHER"
    VICTORY = "VICTORY"


class ShotStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REGENERATION = "NEEDS_REGENERATION"
    RENDERED = "RENDERED"


class AudioCue(Schema):
    cue: str
    offset_seconds: float = Field(default=0, ge=0)
    authority: Literal["presentation"] = "presentation"


class EditorialEffects(Schema):
    impact_freeze_seconds: float = Field(default=0, ge=0, le=0.5)
    shake: float = Field(default=0, ge=0, le=1)
    punch_in: float = Field(default=0, ge=0, le=0.3)
    flash: bool = False
    fade_in: float = Field(default=0, ge=0, le=0.5)
    fade_out: float = Field(default=0, ge=0, le=0.5)


class Shot(Schema):
    shot_id: str = Field(pattern=r"^shot-[0-9]{3,6}$")
    version: int = Field(default=1, ge=1)
    sequence_index: int
    source_moment_ids: list[str]
    source_event_ids: list[str]
    simulation_start: float
    simulation_end: float
    duration_seconds: float = Field(ge=0.3, le=4)
    frame_count: int = Field(gt=0)
    shot_type: ShotType
    framing: str
    camera_angle: str
    camera_motion: str
    subjects: list[str]
    subject_positions: dict[str, Point]
    action_description: str
    environment_description: str
    continuity_state: ContinuityState
    keyframe_prompt: str
    motion_prompt: str
    negative_constraints: list[str]
    coverage_role: str = ""
    ability_visual_id: str | None = None
    edit_in_seconds: float = Field(default=0, ge=0)
    transition_in: str = "cut"
    transition_out: str = "cut"
    audio_cues: list[AudioCue] = Field(default_factory=list)
    narration_hint: str
    editorial: EditorialEffects = EditorialEffects()
    status: ShotStatus = ShotStatus.DRAFT


class DirectorSettings(Schema):
    duration_seconds: float = Field(default=60, ge=30, le=90)
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"
    shot_count: int = Field(default=24, ge=15, le=35)
    fps: int = Field(default=30, ge=10, le=60)
    width: int = Field(default=1080, ge=144, le=2160)
    height: int = Field(default=1920, ge=144, le=3840)
    intro_seconds: float = Field(default=2.5, ge=0.5, le=4)
    outro_seconds: float = Field(default=3, ge=0.5, le=4)
    visual_style: str = (
        "Refined hybrid comic/anime art; realistic fabric, stone and skin textures; stylized expressive faces; controlled cinematic lighting."
    )
    screen_shake: float = Field(default=0.65, ge=0, le=1)

    @model_validator(mode="after")
    def fits(self):
        a, b = map(int, self.aspect_ratio.split(":"))
        if (
            self.width % 2
            or self.height % 2
            or abs(self.width / self.height - a / b) > 0.006
        ):
            raise ValueError(
                "Resolution must be even and match the requested aspect ratio"
            )
        return self


class GoldenDirectorSettings(DirectorSettings):
    """Short coverage-driven edit, retaining the episode/renderer settings contract."""

    mode: Literal["golden"] = "golden"
    duration_seconds: float = Field(default=10, ge=8, le=12)
    shot_count: int = Field(default=7, ge=4, le=8)
    width: int = 720
    height: int = 1280
    intro_seconds: float = 0.8
    outro_seconds: float = 2.4


class ShotList(Schema):
    schema_version: Literal[1] = 1
    director_version: str = "shots-v1"
    source_checksum: str
    outcome_digest: str
    matchup: str
    arena_id: str
    settings: GoldenDirectorSettings | DirectorSettings
    shots: list[Shot]
    outcome: dict[str, Any]

    @model_validator(mode="after")
    def budget(self):
        expected = round(self.settings.duration_seconds * self.settings.fps)
        if sum(s.frame_count for s in self.shots) != expected:
            raise ValueError("Shot frames must exactly fill the duration budget")
        if len(self.shots) != self.settings.shot_count:
            raise ValueError("Shot count differs from settings")
        if len({s.shot_id for s in self.shots}) != len(self.shots):
            raise ValueError("Duplicate shot IDs")
        if any(
            a.continuity_state.simulation_time > b.continuity_state.simulation_time
            for a, b in zip(self.shots, self.shots[1:])
        ):
            raise ValueError("Continuity time cannot rewind")
        if any(s.sequence_index != i for i, s in enumerate(self.shots)):
            raise ValueError("Shot ordering is invalid")
        if any(
            abs(s.duration_seconds - s.frame_count / self.settings.fps) > 1e-8
            for s in self.shots
        ):
            raise ValueError("Duration/frame mismatch")
        return self


class ProviderSettings(Schema):
    image_provider: Literal["mock", "runway"] = "mock"
    video_provider: Literal["mock", "runway"] = "mock"
    network_enabled: bool = False
    estimated_cost_usd: float = 0
    credentials_required: bool = False

    @model_validator(mode="after")
    def explicit_network(self):
        live = "runway" in (self.image_provider, self.video_provider)
        if live != self.network_enabled or live != self.credentials_required:
            raise ValueError(
                "Runway requires explicit network/credential flags; mocks must remain offline"
            )
        return self


class AssetRecord(Schema):
    path: str
    sha256: str
    shot_version: int | None = None
    provider: str = "local"


class EpisodeManifest(Schema):
    schema_version: Literal[1] = 1
    episode_id: str
    created_at: str
    updated_at: str
    simulation_seed: int
    source_checksum: str
    outcome_digest: str
    fighter_versions: dict[str, str]
    visual_versions: dict[str, str]
    representative_battle: str
    director_settings: GoldenDirectorSettings | DirectorSettings
    selector_settings: SelectorSettings
    provider_settings: ProviderSettings = ProviderSettings()
    shot_versions: dict[str, int]
    approval_status: dict[str, ShotStatus]
    assets: dict[str, AssetRecord] = Field(default_factory=dict)
    render_approvals: dict[str, str] = Field(default_factory=dict)
    actual_cost_usd: float = 0
    stage: str = "DIRECTED"
    golden: dict[str, Any] | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
