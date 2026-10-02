"""Strict contracts for simulator-derived beats and manually uploaded shots."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True, allow_inf_nan=False)


class FightBeat(Schema):
    beat_id: str
    source_event_id: str
    source_index: int
    event_type: str
    acting_character: str | None
    target_character: str | None
    ability_id: str | None
    intent: str
    simulation_time: float = Field(ge=0)
    start_time: float = Field(ge=0)
    end_time: float = Field(ge=0)
    anticipation: str
    action: str
    contact_or_near_contact: str
    reaction: str
    recovery: str
    required_character_poses: list[str]
    required_ability_effects: list[str]
    camera_importance: float = Field(ge=0, le=1)
    continuity_requirements: list[str]
    can_combine: bool
    success: bool | None
    recorded_damage: float = Field(ge=0)


class CharacterVisualBible(Schema):
    character_id: str
    version_id: str
    development_fixture: bool = True
    simplified_production_design: str
    silhouette_rules: list[str]
    face_and_hair_anchors: list[str]
    costume_colors: list[str]
    proportions: str
    signature_poses: list[str]
    movement_personality: str
    allowed_exaggeration: list[str]
    forbidden_design_drift: list[str]
    required_views: list[Literal["front", "side", "three_quarter"]]
    seedance_image_reference_requirements: list[str]


class AbilityVisualSpec(Schema):
    character_id: str
    ability_id: str
    ability_type: str
    activation_pose: str
    visual_shape: str
    color_palette: list[str]
    scale: str
    lighting_behavior: str
    motion_behavior: str
    impact_behavior: str
    screen_space_readability: str
    continuity_rules: list[str]
    never_confuse_with: list[str]
    requires_image_reference: bool
    development_fixture: bool = True


class VisualContinuity(Schema):
    simulation_time: float
    screen_positions: dict[str, str]
    facing: dict[str, str]
    stance: dict[str, str]
    dominant_limb: dict[str, str]
    costume_state: dict[str, str]
    injury_state: dict[str, str]
    ability_state: dict[str, str]
    energy_state: dict[str, float]
    camera_side: str
    environment_landmarks: list[str]
    lighting_direction: str
    time_of_day: str
    transition_safe_pose: dict[str, str]
    source_event_ids: list[str]


class SeedanceShot(Schema):
    shot_id: str
    sequence_index: int
    duration_seconds: float = Field(ge=0.5, le=3.5)
    purpose: str
    source_beat_ids: list[str] = Field(min_length=1)
    characters_visible: list[str]
    starting_pose: dict[str, str]
    ending_pose: dict[str, str]
    action_description: str
    camera_framing: str
    camera_movement: str
    lens_style_direction: str
    background_description: str
    ability_effects: list[str]
    transition_in: str
    transition_out: str
    continuity_anchors: list[str]
    seedance_prompt: str
    negative_prompt: str
    required_reference_images: list[str]
    optional_motion_reference_video: str | None = None
    human_review_checklist: list[str]
    continuity_start: VisualContinuity
    continuity_end: VisualContinuity
    source_simulation_time: float
    editorial_note: str = ""


class EpisodePlan(Schema):
    schema_version: Literal[1] = 1
    episode_id: str
    source_checksum: str
    canonical_event_sha256: str
    seed: int
    fighter_ids: list[str]
    aspect_ratio: Literal["9:16"] = "9:16"
    target_resolution: list[int] = [1080, 1920]
    fps: Literal[24, 30] = 30
    duration_seconds: float = Field(ge=8, le=65)
    style: str
    shots: list[SeedanceShot] = Field(min_length=6, max_length=32)
    outcome: dict

    @model_validator(mode="after")
    def check_edit(self):
        if abs(sum(s.duration_seconds for s in self.shots) - self.duration_seconds) > 1e-6:
            raise ValueError("Shot durations do not match episode duration")
        for left, right in zip(self.shots, self.shots[1:]):
            if left.continuity_end != right.continuity_start:
                raise ValueError(f"Continuity break: {left.shot_id} to {right.shot_id}")
        return self
