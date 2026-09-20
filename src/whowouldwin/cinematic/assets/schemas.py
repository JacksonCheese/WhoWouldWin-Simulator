"""Versioned, renderer-facing character and ability asset contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from whowouldwin.cinematic.episodes.schemas import Schema


REQUIRED_HUMANOID_ROLES = (
    "root",
    "pelvis",
    "spine",
    "chest",
    "neck",
    "head",
    "clavicle.L",
    "clavicle.R",
    "upper_arm.L",
    "upper_arm.R",
    "forearm.L",
    "forearm.R",
    "hand.L",
    "hand.R",
    "thigh.L",
    "thigh.R",
    "shin.L",
    "shin.R",
    "foot.L",
    "foot.R",
)

OPTIONAL_HUMANOID_ROLES = (
    "toe.L",
    "toe.R",
    "upper_arm_twist.L",
    "upper_arm_twist.R",
    "forearm_twist.L",
    "forearm_twist.R",
    "thigh_twist.L",
    "thigh_twist.R",
    "scapula.L",
    "scapula.R",
    "elbow_pole.L",
    "elbow_pole.R",
    "wrist_control.L",
    "wrist_control.R",
    "heel.L",
    "heel.R",
    "ball.L",
    "ball.R",
)


class AssetFormat(StrEnum):
    BLEND = "blend"
    FBX = "fbx"
    GLB = "glb"
    GLTF = "gltf"


class RootMotionPolicy(StrEnum):
    REPLACE = "replace"
    EXTRACT = "extract"
    KEEP = "keep"
    IGNORE = "ignore"


class RestPose(StrEnum):
    A_POSE = "A_POSE"
    T_POSE = "T_POSE"
    SOURCE = "SOURCE"


Axis = Literal["X", "-X", "Y", "-Y", "Z", "-Z"]


class TransformOffset(Schema):
    location: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_degrees: tuple[float, float, float] = (0.0, 0.0, 0.0)


class RigAdapterDefinition(Schema):
    schema_version: Literal[1] = 1
    adapter_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    standard_to_target: dict[str, str]
    optional_bones: dict[str, str] = Field(default_factory=dict)
    finger_chains: dict[str, list[str]] = Field(default_factory=dict)
    corrective_shape_keys: list[str] = Field(default_factory=list)
    source_rest_pose: RestPose = RestPose.SOURCE
    target_rest_pose: RestPose = RestPose.A_POSE
    rotation_offsets_degrees: dict[str, tuple[float, float, float]] = Field(
        default_factory=dict
    )
    root_object: str | None = None

    @model_validator(mode="after")
    def complete_contract(self):
        missing = set(REQUIRED_HUMANOID_ROLES) - set(self.standard_to_target)
        if missing:
            raise ValueError(
                "Rig adapter is missing required roles: " + ", ".join(sorted(missing))
            )
        unsupported = set(self.optional_bones) - set(OPTIONAL_HUMANOID_ROLES)
        if unsupported:
            raise ValueError(
                "Unknown optional humanoid roles: " + ", ".join(sorted(unsupported))
            )
        if any(not name.strip() for name in self.standard_to_target.values()):
            raise ValueError("Rig adapter target bone names cannot be blank")
        unknown_offsets = set(self.rotation_offsets_degrees) - (
            set(REQUIRED_HUMANOID_ROLES) | set(OPTIONAL_HUMANOID_ROLES)
        )
        if unknown_offsets:
            raise ValueError("Rotation offsets refer to unknown humanoid roles")
        return self


class MaterialReference(Schema):
    material_id: str
    slots: list[str] = Field(default_factory=list)
    embedded_name: str | None = None
    library_path: str | None = None

    @model_validator(mode="after")
    def has_source(self):
        if not self.embedded_name and not self.library_path:
            raise ValueError("Material reference needs embedded_name or library_path")
        return self


class AttachmentPoint(Schema):
    attachment_id: str
    bone_role: str
    offset: TransformOffset = TransformOffset()


class ClipPhases(Schema):
    anticipation_end: float = Field(default=0.2, ge=0, le=1)
    contact: float = Field(default=0.5, ge=0, le=1)
    followthrough_end: float = Field(default=0.78, ge=0, le=1)

    @model_validator(mode="after")
    def ordered(self):
        if not self.anticipation_end <= self.contact <= self.followthrough_end:
            raise ValueError("Animation phases must be ordered")
        return self


class AnimationClipDefinition(Schema):
    clip_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    action: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    path: str
    source_armature: str | None = None
    action_name: str | None = None
    rig_adapter: str | None = None
    format: AssetFormat | None = None
    root_motion: RootMotionPolicy = RootMotionPolicy.REPLACE
    phases: ClipPhases = ClipPhases()
    mirror_supported: bool = True
    loop: bool = False
    tags: list[str] = Field(default_factory=list)


class PairedActorBinding(Schema):
    """One actor inside a synchronized two-person animation source."""

    actor_id: Literal["fighter_a", "fighter_b"]
    source_armature: str
    action_name: str
    rig_adapter: str


class SupportFootPhase(Schema):
    actor_id: Literal["fighter_a", "fighter_b"]
    side: Literal["L", "R"]
    start_frame: int = Field(ge=0)
    planted_end_frame: int = Field(ge=0)
    heel_release_frame: int | None = Field(default=None, ge=0)
    ball_release_frame: int | None = Field(default=None, ge=0)
    toe_release_frame: int | None = Field(default=None, ge=0)
    recovery_frame: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def ordered(self):
        values = [self.start_frame, self.planted_end_frame]
        if self.heel_release_frame is not None:
            values.append(self.heel_release_frame)
        if self.ball_release_frame is not None:
            values.append(self.ball_release_frame)
        if self.toe_release_frame is not None:
            values.append(self.toe_release_frame)
        if self.recovery_frame is not None:
            values.append(self.recovery_frame)
        if values != sorted(values):
            raise ValueError("Support-foot phase frames must be ordered")
        return self


class PartnerContactPhase(Schema):
    contact_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    actor_id: Literal["fighter_a", "fighter_b"]
    effector_role: str
    target_actor_id: Literal["fighter_a", "fighter_b"]
    target_role: str
    approach_frame: int = Field(ge=0)
    contact_frame: int = Field(ge=0)
    hold_start_frame: int = Field(ge=0)
    hold_end_frame: int = Field(ge=0)
    recoil_frame: int = Field(ge=0)
    release_frame: int = Field(ge=0)
    intended_surface_gap: float = Field(default=0.0, ge=-0.05, le=0.1)

    @model_validator(mode="after")
    def coherent(self):
        if self.actor_id == self.target_actor_id:
            raise ValueError("Paired contact must target the other actor")
        if not (
            self.approach_frame <= self.contact_frame <= self.hold_start_frame
            <= self.hold_end_frame <= self.recoil_frame <= self.release_frame
        ):
            raise ValueError("Partner-contact frames must be ordered")
        return self


class CommercialProvenance(Schema):
    license_name: str = Field(min_length=1)
    license_url: str | None = None
    commercial_use_allowed: bool
    redistribution_allowed: bool
    performers_or_animators: list[str] = Field(min_length=1)
    source_take: str = Field(min_length=1)
    consent_or_release_reference: str | None = None
    acquisition_date: str = Field(min_length=1)


class PairedPerformanceDefinition(Schema):
    """A synchronized authored/mocap performance; never an outcome authority."""

    schema_version: Literal[1] = 1
    performance_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    path: str
    format: AssetFormat
    source_kind: Literal["authored", "paired_mocap", "diagnostic_fixture"]
    frame_rate: float = Field(gt=0, le=240)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    forward_axis: Axis = "-Y"
    up_axis: Axis = "Z"
    unit_scale_meters: float = Field(default=1.0, gt=0, le=100)
    actors: list[PairedActorBinding] = Field(min_length=2, max_length=2)
    support_phases: list[SupportFootPhase] = Field(default_factory=list)
    contacts: list[PartnerContactPhase] = Field(default_factory=list)
    root_motion: RootMotionPolicy = RootMotionPolicy.EXTRACT
    provenance: CommercialProvenance
    quality_status: Literal["unreviewed", "diagnostic_rejected", "approved"] = "unreviewed"

    @model_validator(mode="after")
    def coherent(self):
        if self.end_frame <= self.start_frame:
            raise ValueError("Paired performance must have positive duration")
        if {actor.actor_id for actor in self.actors} != {"fighter_a", "fighter_b"}:
            raise ValueError("Paired performance needs exactly fighter_a and fighter_b")
        for phase in self.support_phases:
            last_frame = phase.recovery_frame or phase.toe_release_frame
            if last_frame is not None and last_frame > self.end_frame:
                raise ValueError("Support phase extends beyond the performance")
        for contact in self.contacts:
            if contact.release_frame > self.end_frame:
                raise ValueError("Contact phase extends beyond the performance")
        if self.quality_status == "approved" and self.source_kind == "diagnostic_fixture":
            raise ValueError("A diagnostic fixture cannot be production-approved")
        if self.quality_status == "approved" and not self.provenance.commercial_use_allowed:
            raise ValueError("Approved paired performance must allow commercial use")
        return self


class VFXDefinition(Schema):
    vfx_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    asset_path: str | None = None
    attachment_point: str | None = None
    duration_seconds: float | None = Field(default=None, gt=0)
    parameters: dict[str, str | float | int | bool] = Field(default_factory=dict)


class AbilityDefinition(Schema):
    """Presentation-only instructions; success remains a simulation fact."""

    ability_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    animation: str
    startup_vfx: list[str] = Field(default_factory=list)
    active_vfx: list[str] = Field(default_factory=list)
    impact_vfx: list[str] = Field(default_factory=list)
    projectile_object: str | None = None
    attachment_points: list[str] = Field(default_factory=list)
    camera_preference: list[str] = Field(default_factory=list)
    environmental_presentation: list[str] = Field(default_factory=list)
    sound_hooks: list[str] = Field(default_factory=list)
    authority: Literal["presentation"] = "presentation"
    simulator_decides_outcome: Literal[True] = True


class CharacterPackageManifest(Schema):
    schema_version: Literal[1] = 1
    character_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    display_name: str = Field(min_length=1)
    package_version: str = Field(min_length=1)
    development_fixture: bool = False
    allow_external_assets: bool = False
    model_path: str
    armature: str
    mesh_objects: list[str] = Field(min_length=1)
    accessory_objects: list[str] = Field(default_factory=list)
    scale: float = Field(default=1.0, gt=0, le=1000)
    forward_axis: Axis = "-Y"
    up_axis: Axis = "Z"
    rest_pose: RestPose = RestPose.A_POSE
    rig_adapter: str = "rig_adapter.json"
    default_materials: list[MaterialReference] = Field(default_factory=list)
    combat_style: list[str] = Field(default_factory=list)
    generic_animation_compatibility: list[str] = Field(default_factory=list)
    animation_clips: list[AnimationClipDefinition] = Field(default_factory=list)
    custom_animation_overrides: dict[str, str] = Field(default_factory=dict)
    ability_definitions: list[str] = Field(default_factory=list)
    vfx_definitions: list[str] = Field(default_factory=list)
    attachment_points: list[AttachmentPoint] = Field(default_factory=list)
    metadata: dict[str, str | float | int | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def coherent(self):
        suffix = self.model_path.lower().rsplit(".", 1)[-1]
        if suffix not in {item.value for item in AssetFormat}:
            raise ValueError("model_path must be .blend, .fbx, .glb, or .gltf")
        if self.forward_axis.lstrip("-") == self.up_axis.lstrip("-"):
            raise ValueError("forward_axis and up_axis must use different axes")
        clips = {clip.clip_id for clip in self.animation_clips}
        if len(clips) != len(self.animation_clips):
            raise ValueError("Animation clip ids must be unique")
        missing = set(self.custom_animation_overrides.values()) - clips
        if missing:
            raise ValueError(
                "Animation overrides refer to undefined clips: "
                + ", ".join(sorted(missing))
            )
        attachments = [point.attachment_id for point in self.attachment_points]
        if len(set(attachments)) != len(attachments):
            raise ValueError("Attachment point ids must be unique")
        return self


class CharacterPackage(Schema):
    root: str
    manifest_path: str
    manifest: CharacterPackageManifest
    rig_adapter: RigAdapterDefinition
    abilities: list[AbilityDefinition] = Field(default_factory=list)
    vfx: list[VFXDefinition] = Field(default_factory=list)


class ValidationMessage(Schema):
    code: str
    message: str
    path: str | None = None
    suggestion: str | None = None


class CharacterValidationReport(Schema):
    character_id: str | None = None
    package_root: str
    valid: bool
    checks: dict[str, bool | int | float | str] = Field(default_factory=dict)
    errors: list[ValidationMessage] = Field(default_factory=list)
    warnings: list[ValidationMessage] = Field(default_factory=list)
    blender: dict = Field(default_factory=dict)


class BoneCandidate(Schema):
    bone_name: str
    score: float = Field(ge=0, le=1)
    reason: str


class BoneMappingSuggestion(Schema):
    role: str
    selected: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    ambiguous: bool = False
    candidates: list[BoneCandidate] = Field(default_factory=list)


class RigMappingProposal(Schema):
    schema_version: Literal[1] = 1
    armature: str
    suggestions: list[BoneMappingSuggestion]
    proposed_standard_to_target: dict[str, str]
    unresolved_required_roles: list[str]
    manual_review_required: bool
