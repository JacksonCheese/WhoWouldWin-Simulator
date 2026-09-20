import pytest
from whowouldwin.simulation.engine import Engine
from whowouldwin.combat.environment import Matchup
from whowouldwin.characters.loader import load_character


@pytest.fixture
def engine():
    return Engine(Matchup(starting_distance=4), record=True)


@pytest.fixture(scope="session")
def profiles():
    return tuple(load_character(name) for name in ("naruto", "omniman", "aang", "homelander"))
