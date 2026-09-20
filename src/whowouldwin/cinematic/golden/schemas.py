from typing import Literal
from pydantic import Field
from whowouldwin.cinematic.episodes.schemas import Schema, AssetReference


class AbilityVisualProfile(Schema):
    ability_visual_id: str
    fighter_profile_id: str
    simulation_ability_id: str
    development_fixture: bool = True
    display_name: str
    action_description: str
    windup_description: str
    movement_description: str
    impact_description: str
    energy_or_effect_description: str
    pose_guidance: str
    environment_interaction: str
    reference_asset_paths: list[AssetReference] = Field(default_factory=list)
    form_requirements: list[str] = Field(default_factory=list)
    prohibited_visual_changes: list[str]
    prompt_constraints: list[str]


class EpisodeStyleProfile(Schema):
    style_id: str = "golden-comic-3d-v1"
    description: str = (
        "Cinematic stylized 3D comic/anime, high-end cel shading, semi-realistic materials, "
        "rim light, readable silhouettes, superhero posing, cinematic depth, controlled saturated colors, "
        "high contrast, expressive faces."
    )
    constraints: str = (
        "No text, extra attacks, weapons, wounds or invented destruction."
    )


class CoverageBeat(Schema):
    role: str
    seconds: float
    framing: str
    angle: str
    motion: str
    phase: Literal["before", "contact", "after"]


class CinematicCoverageTemplate(Schema):
    template_id: str
    beats: list[CoverageBeat]
    constraint: str = (
        "Different perspectives of the same recorded action; no extra attack or damage."
    )


class ProviderJob(Schema):
    job_key: str
    shot_id: str
    shot_version: int
    kind: Literal["image", "video"]
    model: str
    request_digest: str
    attempt: int
    task_id: str | None = None
    state: str = "RESERVED"
    reserved_usd: float = Field(ge=0)
    actual_usd: float | None = Field(default=None, ge=0)
    output_path: str
    output_sha256: str | None = None
    failure: str | None = None
    poll_retries: int = 0
    created_at: str


class GoldenState(Schema):
    schema_version: Literal[1] = 1
    parent_episode: str
    parent_manifest_sha256: str
    selection_start: float
    selection_end: float
    selection_moment_ids: list[str]
    selection_reason: str
    style: EpisodeStyleProfile = EpisodeStyleProfile()
    reference_files: dict[str, str] = Field(default_factory=dict)
    reference_digest: str | None = None
    approved_reference_digest: str | None = None
    keyframe_approvals: dict[str, str] = Field(default_factory=dict)
    jobs: list[ProviderJob] = Field(default_factory=list)
    max_cost_usd: float | None = None
    pricing_verified: str = "2026-09-06"
    confirmed_cost_usd: float = 0
    conservative_cost_usd: float = 0
    failures: list[str] = Field(default_factory=list)
