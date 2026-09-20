"""Continuity reads all state frames and explicit environment effects, including omitted events."""

from copy import deepcopy
from .schemas import (
    ArenaVisualProfile,
    CharacterContinuity,
    ContinuityState,
    EventLog,
    VisualProfile,
)


class ContinuityTracker:
    def __init__(
        self,
        log: EventLog,
        visuals: dict[str, VisualProfile],
        arena: ArenaVisualProfile,
    ):
        self.log = log
        self.visuals = visuals
        self.arena = arena

    def at(self, time: float) -> ContinuityState:
        states = deepcopy(self.log.initial_states)
        lowest = {k: v.health_fraction for k, v in states.items()}
        for frame in self.log.state_timeline:
            if frame.simulation_time > time + 1e-9:
                break
            states = frame.fighters
            for k, v in states.items():
                lowest[k] = min(lowest[k], v.health_fraction)
        arena_state = deepcopy(self.arena.continuity_state)
        destruction = []
        for event in self.log.events:
            if event.simulation_time > time + 1e-9:
                break
            effect = event.environment_effect
            # The current adapter never asserts destruction; future adapters must supply explicit evidence.
            if effect and effect.get("persistent_destruction") is True:
                description = effect.get("description")
                if isinstance(description, str) and description not in destruction:
                    destruction.append(description)
                if isinstance(effect.get("state_update"), dict):
                    arena_state.update(deepcopy(effect["state_update"]))
        center = sum(s.position.x for s in states.values()) / len(states)
        characters = {}
        for key, s in states.items():
            wear = (
                "heavy surface scuffs"
                if lowest[key] < 0.25
                else (
                    "visible surface scuffs"
                    if lowest[key] < 0.65
                    else "light surface scuffs" if lowest[key] < 0.9 else "clean"
                )
            )
            characters[key] = CharacterContinuity(
                transformation=s.transformation,
                costume_version=self.visuals[key].version_id,
                surface_wear=wear,
                location=s.position,
                relative_position=(
                    "left"
                    if s.position.x < center
                    else (
                        "right"
                        if s.position.x > center
                        else "same horizontal coordinate"
                    )
                ),
                persistent_effects=s.statuses,
                health=s.health,
                health_fraction=s.health_fraction,
            )
        return ContinuityState(
            simulation_time=time,
            characters=characters,
            lighting=self.arena.lighting,
            time_of_day=self.arena.time_of_day,
            weather=self.arena.weather,
            arena_state=arena_state,
            environmental_destruction=destruction,
            presentation_notes=[
                "Wear is a non-anatomical presentation convention, not a new combat fact.",
                "No persistent terrain damage or inventory is exposed by this engine.",
            ],
        )
