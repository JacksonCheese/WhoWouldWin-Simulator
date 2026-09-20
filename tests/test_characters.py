import math
import pytest
from pydantic import ValidationError
from whowouldwin.characters.schema import Character, PLACEHOLDER_NOTE, Ability
from whowouldwin.characters.validator import validate_directory
from whowouldwin.combat.environment import Matchup


def test_all_starters_validate(profiles):
    assert validate_directory() == ["aang", "homelander", "naruto", "omniman"]
    assert all(p.scaling_note == PLACEHOLDER_NOTE for p in profiles)


@pytest.mark.parametrize("mutation", [
    lambda p: p["resources"].update(health=-1),
    lambda p: p["physical"].update(movement_speed=0),
    lambda p: p["physical"].update(strength={"low": 3, "expected": 2, "high": 1}),
    lambda p: p["physical"].update(durability=math.nan),
    lambda p: p["resistances"].update(energy=1),
    lambda p: p["abilities"].append(p["abilities"][0]),
    lambda p: p["abilities"][0].update(required_form="unknown"),
    lambda p: p["abilities"][0].update(energy_cost=10000),
    lambda p: p.update(unknown_field=True),
])
def test_invalid_character_rejected(profiles, mutation):
    raw = profiles[0].model_dump(mode="json")
    mutation(raw)
    with pytest.raises(ValidationError):
        Character.model_validate(raw)


def test_range_scaling(profiles):
    p = profiles[0]
    assert p.stats("low")["strength"] < p.stats()["strength"] < p.stats("high")["strength"]
    with pytest.raises(ValueError):
        p.stats("fiction")


@pytest.mark.parametrize("raw", [{"starting_distance": 999}, {"rules": {"timestep": 0}}, {"arena": {"height": -5}}, {"scaling": {"fighter_a": "unknown"}}])
def test_invalid_matchup(raw):
    with pytest.raises(ValueError):
        Matchup.model_validate(raw)


def test_ability_range_and_transform_validation():
    with pytest.raises(ValueError):
        Ability(id="bad", name="Bad", type="melee", range=2, minimum_range=4)
    with pytest.raises(ValueError):
        Ability(id="bad", name="Bad", type="transform")
