"""Deterministic shot planning; future LLM directors implement the same protocol."""

from typing import Protocol
from whowouldwin.simulation.replay import digest
from .continuity import ContinuityTracker
from .prompts import NEGATIVES, keyframe
from .schemas import (
    ArenaVisualProfile,
    AudioCue,
    CinematicMoment,
    DirectorSettings,
    EditorialEffects,
    EventLog,
    Point,
    Shot,
    ShotList,
    ShotType,
    VisualProfile,
)


class Director(Protocol):
    def direct(
        self,
        log: EventLog,
        moments: list[CinematicMoment],
        visuals: dict[str, VisualProfile],
        arena: ArenaVisualProfile,
        settings: DirectorSettings,
    ) -> ShotList: ...


COMPOSITIONS = [
    (
        ShotType.OVER_SHOULDER,
        "Foreground shoulder silhouette with opponent beyond",
        "over shoulder",
        "sweeping orbit",
    ),
    (
        ShotType.CLOSE_UP,
        "One face and upper body; expressive reaction",
        "eye level",
        "controlled punch-in zoom",
    ),
    (
        ShotType.LOW_ANGLE,
        "Dominant torso and hand reaching toward lens",
        "low angle",
        "aggressive crash zoom",
    ),
    (
        ShotType.AERIAL,
        "Diagonal overhead spatial composition",
        "high overhead",
        "high-speed follow camera",
    ),
    (
        ShotType.POV,
        "Opponent advancing toward the viewpoint",
        "fighter POV",
        "whip pan into action",
    ),
    (
        ShotType.MEDIUM_ACTION,
        "Three-quarter action silhouette with depth",
        "three-quarter",
        "tracking shot",
    ),
    (
        ShotType.EXTREME_CLOSE_UP,
        "Eyes and brow fill the frame",
        "tight eye level",
        "static dramatic composition",
    ),
    (
        ShotType.HIGH_ANGLE,
        "Foreground depth with the focus fighter below",
        "high angle",
        "descending tracking shot",
    ),
    (
        ShotType.WIDE_ACTION,
        "Diagonal composition, fighters at different depths",
        "oblique",
        "fast lateral follow",
    ),
    (
        ShotType.REACTION,
        "Isolated hit or defense reaction detail",
        "three-quarter close",
        "handheld impact",
    ),
]


def budget_frames(weights: list[float], settings: DirectorSettings) -> list[int]:
    """Allocate integer frames, enforcing every shot's 0.5–4 second bounds."""
    fps = settings.fps
    minimum = (fps + 1) // 2
    maximum = 4 * fps
    counts = [minimum] * len(weights)
    counts[0] = round(settings.intro_seconds * fps)
    counts[-1] = round(settings.outro_seconds * fps)
    left = round(settings.duration_seconds * fps) - sum(counts)
    if left < 0 or left > (len(weights) - 2) * (maximum - minimum):
        raise ValueError(
            "Duration cannot fit this shot count and intro/outro; adjust --shots or --duration"
        )
    while left:
        available = [i for i in range(1, len(weights) - 1) if counts[i] < maximum]
        denominator = sum(weights[i] for i in available)
        quotas = [(i, max(1, int(left * weights[i] / denominator))) for i in available]
        for i, amount in quotas:
            add = min(amount, maximum - counts[i], left)
            counts[i] += add
            left -= add
    return counts


class CinematicDirector:
    def direct(
        self,
        log: EventLog,
        moments: list[CinematicMoment],
        visuals: dict[str, VisualProfile],
        arena: ArenaVisualProfile,
        settings: DirectorSettings,
    ) -> ShotList:
        intro = next(m for m in moments if m.moment_type == "faceoff")
        outro = next(m for m in moments if m.moment_type == "outcome")
        middle = [
            m for m in moments if m.moment_type not in {"faceoff", "outcome", "defeat"}
        ]
        slots = settings.shot_count - 2
        if len(middle) > slots:
            ranked = sorted(
                middle,
                key=lambda m: (
                    m.moment_type not in {"finisher", "transformation"},
                    -m.importance_score,
                    m.start_time,
                ),
            )
            middle = ranked[:slots]
        # Concurrent windups overlap. Order by resolution so continuity never rewinds.
        middle = sorted(middle, key=lambda m: (m.end_time, m.start_time, m.moment_id))
        if not middle:
            middle = [intro]
        chosen = (
            [intro]
            + [
                middle[min(len(middle) - 1, i * len(middle) // slots)]
                for i in range(slots)
            ]
            + [outro]
        )
        frames = budget_frames(
            [1 + min(2, m.importance_score) * 0.5 for m in chosen], settings
        )
        tracker = ContinuityTracker(log, visuals, arena)
        shots = []
        for i, (moment, count) in enumerate(zip(chosen, frames)):
            kind, framing, angle, motion = COMPOSITIONS[(i - 1) % len(COMPOSITIONS)]
            if i == 0:
                kind, framing, angle, motion = (
                    ShotType.ESTABLISHING,
                    "Separated foreground and background faceoff",
                    "low three-quarter",
                    "slow inward track",
                )
            elif i == len(chosen) - 1:
                kind, framing, angle, motion = (
                    ShotType.VICTORY,
                    "Final outcome portrait",
                    "low angle",
                    "slow pull-back",
                )
            elif moment.moment_type == "transformation":
                kind, framing, angle, motion = (
                    ShotType.TRANSFORMATION,
                    "Form change surrounding the focal fighter",
                    "low angle",
                    "sweeping orbit",
                )
            elif moment.moment_type == "finisher":
                kind, framing, angle, motion = (
                    ShotType.FINISHER,
                    "Decisive contact and defeated fighter reaction",
                    "dynamic oblique",
                    "slow-motion impact",
                )
            elif moment.moment_type in {"hit", "special_hit"} and i % 3 == 0:
                kind, framing, angle, motion = (
                    ShotType.IMPACT,
                    "Contact detail with radial action lines",
                    "tight oblique",
                    "handheld impact",
                )
            elif moment.moment_type in {"dodge", "block"}:
                kind, framing, angle, motion = (
                    ShotType.REACTION,
                    "Defender visibly avoids or absorbs the recorded attack",
                    "three-quarter close",
                    "whip pan to defender",
                )
            subjects = list(moment.participants)
            if moment.moment_type in {"dodge", "block"}:
                subjects = subjects[::-1]
            if kind == ShotType.VICTORY:
                winner = log.outcome["winner"]
                subjects = (
                    [list(log.fighter_names)[winner]]
                    if winner is not None
                    else list(log.fighter_names)
                )
            if kind in {
                ShotType.CLOSE_UP,
                ShotType.EXTREME_CLOSE_UP,
                ShotType.REACTION,
                ShotType.LOW_ANGLE,
                ShotType.VICTORY,
            }:
                subjects = (
                    subjects[:1]
                    if log.outcome["winner"] is not None or kind != ShotType.VICTORY
                    else subjects
                )
            continuity = tracker.at(moment.end_time)
            positions = {
                key: Point(x=0.48 if j == 0 else 0.8, y=0.55 if j == 0 else 0.35)
                for j, key in enumerate(subjects)
            }
            if kind in {ShotType.ESTABLISHING, ShotType.WIDE_ACTION}:
                positions = {
                    key: Point(x=0.3 + j * 0.4, y=0.59 - j * 0.16)
                    for j, key in enumerate(subjects)
                }
            impact = kind in {ShotType.IMPACT, ShotType.FINISHER}
            editorial = EditorialEffects(
                impact_freeze_seconds=(
                    0.16 if kind == ShotType.FINISHER else 0.08 if impact else 0
                ),
                shake=settings.screen_shake if impact else 0,
                punch_in=0.15 if "zoom" in motion or impact else 0.04,
                flash=impact,
                fade_in=0.25 if i == 0 else 0,
                fade_out=0.3 if i == len(chosen) - 1 else 0,
            )
            audio = (
                [
                    AudioCue(
                        cue="final_impact" if kind == ShotType.FINISHER else "impact",
                        offset_seconds=0.12,
                    )
                ]
                if impact
                else (
                    [AudioCue(cue="whoosh", offset_seconds=0.1)]
                    if any(s in motion for s in ["pan", "zoom", "follow"])
                    else []
                )
            )
            if kind == ShotType.TRANSFORMATION:
                audio = [AudioCue(cue="transformation", offset_seconds=0.15)]
            description = moment.summary
            if i not in {0, len(chosen) - 1} and moment.moment_type == "faceoff":
                description = "A pre-fight stance / arena detail; no additional attack is implied."
            negative = list(NEGATIVES) + [
                item
                for key in subjects
                for item in visuals[key].prohibited_visual_changes
            ]
            shots.append(
                Shot(
                    shot_id=f"shot-{i+1:03d}",
                    sequence_index=i,
                    source_moment_ids=[moment.moment_id],
                    source_event_ids=moment.source_event_ids,
                    simulation_start=moment.start_time,
                    simulation_end=moment.end_time,
                    duration_seconds=count / settings.fps,
                    frame_count=count,
                    shot_type=kind,
                    framing=framing,
                    camera_angle=angle,
                    camera_motion=motion,
                    subjects=subjects,
                    subject_positions=positions,
                    action_description=description,
                    environment_description=arena.description,
                    continuity_state=continuity,
                    keyframe_prompt=keyframe(
                        settings.visual_style,
                        framing,
                        angle,
                        description,
                        arena.description,
                        subjects,
                        visuals,
                        continuity,
                    ),
                    motion_prompt=f"{motion}. {description} Preserve all source outcomes and identities. Use camera/staging motion only; no new damaging action. Duration {count/settings.fps:.3f}s, {settings.aspect_ratio}.",
                    negative_constraints=list(dict.fromkeys(negative)),
                    transition_in="fade" if i == 0 else "cut",
                    transition_out="fade" if i == len(chosen) - 1 else "cut",
                    audio_cues=audio,
                    narration_hint=description,
                    editorial=editorial,
                )
            )
        return ShotList(
            source_checksum=log.source_checksum,
            outcome_digest=digest(log.outcome),
            matchup=" vs ".join(log.fighter_names.values()),
            arena_id=arena.arena_id,
            settings=settings,
            shots=shots,
            outcome=log.outcome,
        )
