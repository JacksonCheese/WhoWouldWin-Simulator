"""Compact prompts: explicit ability semantics, shared style and reference-bound identities."""

from .schemas import EpisodeStyleProfile


def utf16_length(text):
    return len(text.encode("utf-16-le")) // 2


class PromptCompiler:
    def compile(self, shot, visuals, ability, arena, style: EpisodeStyleProfile):
        identity = []
        continuity = []
        for key in shot.subjects:
            v = visuals[key]
            s = shot.continuity_state.characters[key]
            identity.append(f"@{key}: {v.body_description} {v.costume_description}")
            form = (
                v.transformation_visuals.get(s.transformation, "base form")
                if s.transformation
                else "base form"
            )
            continuity.append(f"{key} {s.relative_position}, {s.surface_wear}, {form}")
        parts = {
            "style": style.description,
            "identities": " ".join(identity),
            "camera": f"{shot.framing}; {shot.camera_angle}.",
            "action": shot.action_description,
            "effect": (
                ability.energy_or_effect_description
                if shot.coverage_role
                not in {
                    "victory",
                    "defeated_reaction",
                    "environmental_consequence",
                    "dramatic_detail",
                }
                else ""
            ),
            "continuity": "; ".join(continuity) + ".",
            "arena": f"@look: {arena.terrain} {arena.lighting}",
            "constraints": " ".join(
                dict.fromkeys(
                    [
                        style.constraints,
                        *shot.negative_constraints,
                        *(
                            constraint
                            for key in shot.subjects
                            for constraint in visuals[key].prohibited_visual_changes
                        ),
                    ]
                )
            ),
        }
        prompt = " ".join(parts.values())
        # Never silently truncate identity or outcome constraints to satisfy the API.
        if utf16_length(prompt) > 1000:
            raise ValueError(
                f"{shot.shot_id}: keyframe prompt exceeds Runway 1000 UTF-16 units ({utf16_length(prompt)}); shorten the visual/style profile"
            )
        if shot.coverage_role in {"victory", "defeated_reaction", "dramatic_detail"}:
            movement = "Hold the established pose; breathing and cloth move subtly."
        elif shot.coverage_role == "environmental_consequence":
            movement = (
                "The existing light/air effect dissipates; architecture stays intact."
            )
        elif shot.coverage_role == "impact":
            movement = "Begin at the single contact; brief recoil then settle. This is the same hit, never a second strike."
        elif shot.coverage_role in {"setup", "anticipation", "detail", "commitment"}:
            movement = ability.windup_description + " Hold before release."
        else:
            movement = ability.movement_description
        if "avoids" in shot.action_description:
            movement = "The defender slips clear; the attack passes without contact."
        motion = f"{movement} Camera: {shot.camera_motion}. One continuous action, no cuts or additional attacks."
        return (
            prompt,
            motion,
            dict(
                components=parts,
                ability_visual_id=ability.ability_visual_id,
                source_event_ids=shot.source_event_ids,
                coverage_role=shot.coverage_role,
                utf16_units=utf16_length(prompt),
                motion_prompt=motion,
                reference_tags=[*shot.subjects, "look"],
                development_fixture=ability.development_fixture,
            ),
        )
