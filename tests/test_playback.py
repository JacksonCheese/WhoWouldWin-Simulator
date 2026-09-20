import os
import pytest


@pytest.mark.parametrize("recorded", [False, True])
def test_pause_step_restart_and_debug_keys(monkeypatch, tmp_path, recorded):
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    from whowouldwin.visual.app import main
    from whowouldwin.visual.renderer import Renderer
    from whowouldwin.simulation.engine import Engine
    from whowouldwin.simulation.replay import save_replay
    import pygame
    schedule = [[pygame.K_SPACE], [pygame.K_RIGHT], [], [pygame.K_r], [pygame.K_SPACE], [pygame.K_RIGHT], [pygame.K_d]]
    # Supply key events while running the actual app, engine/player and renderer.
    def events():
        return [pygame.event.Event(pygame.KEYDOWN, key=key) for key in schedule.pop(0)]
    monkeypatch.setattr(pygame.event, "get", events)
    frames = []
    original_draw = Renderer.draw
    def observe(self, state, **kwargs):
        frames.append((state, kwargs))
        original_draw(self, state, **kwargs)
    monkeypatch.setattr(Renderer, "draw", observe)
    args = ["--headless", "--max-frames", "7"]
    if recorded:
        engine = Engine(record=True)
        engine.run()
        path = save_replay(engine, tmp_path / "control.json")
        args += ["--replay", str(path)]
    assert main(args) == 0
    assert [state["tick"] for state, _ in frames] == [0, 1, 1, 1, 1, 2, 2]
    assert frames[-1][1]["debug"] is True
    expected = Engine()
    expected.step(); expected.step()
    assert frames[-1][0] == expected.world.snapshot()
