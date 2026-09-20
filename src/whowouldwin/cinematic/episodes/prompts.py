"""Prompt composition is deterministic text generation, not an LLM call."""

from .schemas import ContinuityState, VisualProfile

NEGATIVES = [
    "Do not add damage, hits, powers, weapons or victories absent from the source events.",
    "Do not change identity, costume version or persistent form between shots.",
    "Do not invent anatomical wounds, blood, torn sleeves or destroyed buildings.",
    "A recorded miss or dodge must remain visibly unsuccessful for the attacker.",
    "No UI or written words in future generated art; captions are added by the editor.",
    "Generated visuals are interpretation, not additional evidence for the matchup outcome.",
]


def continuity_text(
    continuity: ContinuityState, visuals: dict[str, VisualProfile]
) -> str:
    rows = []
    for key, state in continuity.characters.items():
        form = (
            visuals[key].transformation_visuals.get(state.transformation, "base form")
            if state.transformation
            else "base form"
        )
        rows.append(
            f"{key}: costume {state.costume_version}; {state.surface_wear}; {form}; {state.relative_position} of opponent; "
            f'persistent effects {", ".join(state.persistent_effects) or "none recorded"}; recorded health {state.health:.2f}.'
        )
    return " ".join(rows)


def keyframe(style, framing, angle, action, environment, subjects, visuals, continuity):
    bible = " ".join(
        f"{key}: {visuals[key].appearance_description} {visuals[key].body_description} {visuals[key].face_description} "
        f"{visuals[key].hair_description} {visuals[key].costume_description}"
        for key in subjects
    )
    return f"{style} {framing}; camera angle: {angle}. {action} Arena: {environment} Character bibles: {bible} Continuity: {continuity_text(continuity,visuals)}"
