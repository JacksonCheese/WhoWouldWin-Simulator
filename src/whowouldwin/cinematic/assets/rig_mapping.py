"""Conservative rig-name matching that never accepts an ambiguous guess."""

from __future__ import annotations

import re

from .schemas import (
    BoneCandidate,
    BoneMappingSuggestion,
    OPTIONAL_HUMANOID_ROLES,
    REQUIRED_HUMANOID_ROLES,
    RigMappingProposal,
)


ALIASES = {
    "root": ("root", "rootmotion", "motionroot", "master"),
    "pelvis": ("pelvis", "hips", "hip", "cog"),
    "spine": ("spine", "spine01", "spinelower", "lowerback"),
    "chest": ("chest", "spine02", "spine2", "spineupper", "upperchest"),
    "neck": ("neck", "neck01"),
    "head": ("head",),
    "clavicle.L": ("claviclel", "shoulderl", "leftshoulder", "lclavicle"),
    "clavicle.R": ("clavicler", "shoulderr", "rightshoulder", "rclavicle"),
    "upper_arm.L": ("upperarml", "leftarm", "lupperarm", "armupperl"),
    "upper_arm.R": ("upperarmr", "rightarm", "rupperarm", "armupperr"),
    "forearm.L": ("forearml", "leftforearm", "leftlowerarm", "lowerarml"),
    "forearm.R": ("forearmr", "rightforearm", "rightlowerarm", "lowerarmr"),
    "hand.L": ("handl", "lefthand", "lhand"),
    "hand.R": ("handr", "righthand", "rhand"),
    "thigh.L": ("thighl", "leftupleg", "leftupperleg", "upperlegl"),
    "thigh.R": ("thighr", "rightupleg", "rightupperleg", "upperlegr"),
    "shin.L": ("shinl", "leftleg", "leftlowerleg", "lowerlegl", "calfl"),
    "shin.R": ("shinr", "rightleg", "rightlowerleg", "lowerlegr", "calfr"),
    "foot.L": ("footl", "leftfoot", "lfoot", "anklel"),
    "foot.R": ("footr", "rightfoot", "rfoot", "ankler"),
    "toe.L": ("toel", "lefttoe", "lefttoebase", "balll"),
    "toe.R": ("toer", "righttoe", "righttoebase", "ballr"),
    "upper_arm_twist.L": ("upperarmtwistl", "leftarmtwist"),
    "upper_arm_twist.R": ("upperarmtwistr", "rightarmtwist"),
    "forearm_twist.L": ("forearmtwistl", "leftforearmtwist"),
    "forearm_twist.R": ("forearmtwistr", "rightforearmtwist"),
    "thigh_twist.L": ("thightwistl", "leftthightwist"),
    "thigh_twist.R": ("thightwistr", "rightthightwist"),
    "scapula.L": ("scapulal", "leftscapula", "shoulderbladel"),
    "scapula.R": ("scapular", "rightscapula", "shoulderblader"),
    "elbow_pole.L": ("elbowpolel", "leftelbowpole", "armikpolel"),
    "elbow_pole.R": ("elbowpoler", "rightelbowpole", "armikpoler"),
    "wrist_control.L": ("wristcontroll", "leftwristcontrol", "handikl"),
    "wrist_control.R": ("wristcontrolr", "rightwristcontrol", "handikr"),
    "heel.L": ("heell", "leftheel"),
    "heel.R": ("heelr", "rightheel"),
    "ball.L": ("balll", "leftball", "leftballoffoot"),
    "ball.R": ("ballr", "rightball", "rightballoffoot"),
}


def normalize_bone_name(name: str) -> str:
    name = name.split(":")[-1]
    name = re.sub(r"^(def|org|mch)[-_.]", "", name, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _candidate(role: str, bone: str) -> BoneCandidate | None:
    normalized = normalize_bone_name(bone)
    aliases = ALIASES[role]
    if normalized in aliases:
        return BoneCandidate(bone_name=bone, score=1.0, reason="exact normalized alias")
    matches = [alias for alias in aliases if alias in normalized or normalized in alias]
    if not matches:
        return None
    longest = max(len(match) for match in matches)
    score = min(0.88, 0.62 + longest / max(len(normalized), 1) * 0.22)
    return BoneCandidate(bone_name=bone, score=round(score, 3), reason="partial alias")


def suggest_rig_mapping(bones: list[str], armature: str) -> RigMappingProposal:
    suggestions = []
    selected = {}
    for role in (*REQUIRED_HUMANOID_ROLES, *OPTIONAL_HUMANOID_ROLES):
        candidates = sorted(
            filter(None, (_candidate(role, bone) for bone in bones)),
            key=lambda item: (-item.score, item.bone_name),
        )[:5]
        winner = None
        ambiguous = False
        confidence = candidates[0].score if candidates else 0.0
        if candidates:
            ambiguous = len(candidates) > 1 and candidates[0].score - candidates[1].score < 0.08
            if not ambiguous and confidence >= 0.72:
                winner = candidates[0].bone_name
                selected[role] = winner
        suggestions.append(
            BoneMappingSuggestion(
                role=role,
                selected=winner,
                confidence=confidence,
                ambiguous=ambiguous,
                candidates=candidates,
            )
        )
    unresolved = [role for role in REQUIRED_HUMANOID_ROLES if role not in selected]
    return RigMappingProposal(
        armature=armature,
        suggestions=suggestions,
        proposed_standard_to_target={
            role: target for role, target in selected.items() if role in REQUIRED_HUMANOID_ROLES
        },
        unresolved_required_roles=unresolved,
        manual_review_required=bool(unresolved)
        or any(item.ambiguous for item in suggestions),
    )
