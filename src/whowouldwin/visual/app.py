"""Real-time observer and recorded-state player. Keyboard input controls playback only."""
import argparse
import os
from pathlib import Path
from whowouldwin.cli.main import add_matchup_arguments, config_from_args
from whowouldwin.simulation.engine import Engine
from whowouldwin.simulation.replay import ReplayPlayer, load_replay, save_replay


def main(argv=None):
    parser = argparse.ArgumentParser(description="Watch utility-AI fighters battle in a 2D arena")
    add_matchup_arguments(parser)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--save-replay", type=Path)
    parser.add_argument("--speed", type=float, choices=[.25, 1, 2, 4], default=1)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--headless", action="store_true", help="SDL dummy display for automated visual checks")
    parser.add_argument("--auto-quit", action="store_true", help="Exit on completed fight")
    parser.add_argument("--max-frames", type=int, help="Bounded render smoke test")
    parser.add_argument("--screenshot", type=Path, help="Save final rendered frame as PNG")
    args = parser.parse_args(argv)
    if args.max_frames is not None and args.max_frames < 1:
        parser.error("--max-frames must be positive")
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame
    from .renderer import Renderer
    try:
        data = load_replay(args.replay) if args.replay else None
        config = config_from_args(args) if not data else None
        engine = Engine(config, record=True) if not data else None
        player = ReplayPlayer(data) if data else None
        seed = data["seed"] if data else engine.seed
        arena = data["config"]["arena"] if data else config.arena.model_dump()
        dt = data["config"]["rules"]["timestep"] if data else config.rules.timestep
    except (ValueError, OSError) as error:
        parser.exit(2, f"Error: {error}\n")
    pygame.display.init()
    pygame.font.init()
    surface = pygame.display.set_mode((1280, 800))
    pygame.display.set_caption("WhoWouldWin Simulator — Autonomous Combat Lab")
    renderer = Renderer(surface, arena)
    clock = pygame.time.Clock()
    paused, running, debug, speed = False, True, args.debug, args.speed
    accumulator, frames, saved = 0., 0, False
    state = player.frame["state"] if player else engine.world.snapshot()
    try:
        while running:
            elapsed = dt if args.headless else min(.25, clock.tick(60) / 1000)
            single_step = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        paused = not paused
                        accumulator = 0
                    elif event.key == pygame.K_d:
                        debug = not debug
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_4, pygame.K_0):
                        speed = {pygame.K_1: 1, pygame.K_2: 2, pygame.K_4: 4, pygame.K_0: .25}[event.key]
                    elif event.key in (pygame.K_RIGHT, pygame.K_PERIOD):
                        paused, single_step, accumulator = True, True, 0
                    elif event.key == pygame.K_r:
                        if player:
                            player.restart()
                        else:
                            engine = Engine(config, record=True)
                        from .effects import Effects
                        renderer.effects = Effects()
                        state = player.frame["state"] if player else engine.world.snapshot()
                        accumulator, paused, saved = 0, False, False
            if single_step:
                accumulator = dt
            elif not paused:
                accumulator += elapsed * speed
            while accumulator + 1e-9 >= dt and not state["done"]:
                if player:
                    frame = player.step()
                    state, events = frame["state"], frame["events"]
                else:
                    engine.step()
                    state, events = engine.world.snapshot(), engine.events
                renderer.effects.ingest(events, state)
                accumulator = max(0, accumulator - dt)
            if state["done"]:
                accumulator = 0
            renderer.draw(state, speed=speed, paused=paused, seed=seed, debug=debug, mode="recorded replay" if player else "live engine")
            pygame.display.flip()
            frames += 1
            if state["done"] and args.save_replay and engine and not saved:
                save_replay(engine, args.save_replay)
                saved = True
            if args.auto_quit and state["done"] or args.max_frames and frames >= args.max_frames:
                running = False
        if args.screenshot:
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(surface, str(args.screenshot))
        print(f"Rendered {frames} frames; tick {state['tick']}; {state['time']:.2f}s; winner={state['winner']}; condition={state['condition'] or 'in progress'}")
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
