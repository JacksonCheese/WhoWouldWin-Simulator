import pygame
from .effects import PALETTE


def text(surface, font, label, position, color=(223, 233, 245)):
    surface.blit(font.render(str(label), True, color), position)


def bar(surface, rect, value, maximum, color):
    pygame.draw.rect(surface, (37, 49, 68), rect, border_radius=4)
    filled = rect.copy()
    filled.width = max(0, round(rect.width * min(1, max(0, value / maximum))))
    if filled.width:
        pygame.draw.rect(surface, color, filled, border_radius=4)


def draw_hud(surface, state, fonts, speed, paused, seed, debug, mode):
    width, height = surface.get_size()
    small, regular, large = fonts
    text(surface, small, "WHO WOULD WIN", (32, 20), (135, 156, 184))
    text(surface, small, "AUTONOMOUS COMBAT LAB  /  DEVELOPMENT ESTIMATES", (width - 515, 20), (135, 156, 184))
    card_width = (width - 270) // 2
    for i, f in enumerate(state["fighters"]):
        x = 32 if i == 0 else width - card_width - 32
        pygame.draw.rect(surface, (22, 32, 49), (x, 57, card_width, 137), border_radius=12)
        text(surface, large, f["name"], (x + 18, 66), PALETTE[i])
        text(surface, small, f"{f['health']:.0f} / {f['max_health']:.0f} HP", (x + card_width - 140, 79))
        bar(surface, pygame.Rect(x + 18, 108, card_width - 36, 13), f["health"], f["max_health"], PALETTE[i])
        half = (card_width - 52) // 2
        text(surface, small, f"STAMINA {f['stamina']:.0f}", (x + 18, 130), (147, 167, 190))
        text(surface, small, f"ENERGY {f['energy']:.0f}", (x + 34 + half, 130), (147, 167, 190))
        bar(surface, pygame.Rect(x + 18, 155, half, 5), f["stamina"], f["max_stamina"], (136, 206, 158))
        bar(surface, pygame.Rect(x + 34 + half, 155, half, 5), f["energy"], f["max_energy"], (150, 146, 236))
        text(surface, small, f["action"], (x + 18, 168), (175, 192, 215))
    label = large.render(f"{state['time']:05.1f}", True, (242, 246, 250))
    surface.blit(label, (width / 2 - label.get_width() / 2, 80))
    status = "PAUSED" if paused else f"{speed:g}× PLAY"
    text(surface, small, status, (width / 2 - 37, 126))
    text(surface, small, f"TICK {state['tick']}", (width / 2 - 40, 151), (126, 149, 178))
    pygame.draw.rect(surface, (17, 25, 40), (0, height - 64, width, 64))
    text(surface, small, "SPACE pause   R restart   1 / 2 / 4 speed   0 slow   → step   D debug   ESC exit", (32, height - 52))
    text(surface, small, f"{mode.upper()}   ·   SEED {seed}   ·   Both fighters use utility AI", (32, height - 27), (126, 149, 178))
    if debug:
        for i, f in enumerate(state["fighters"]):
            x = 32 if i == 0 else width - 332
            panel = pygame.Surface((300, 278), pygame.SRCALPHA)
            panel.fill((12, 19, 32, 232))
            surface.blit(panel, (x, 216))
            text(surface, small, f"AI / {f['action']}", (x + 12, 224), PALETTE[i])
            for row, (key, value) in enumerate(f["debug"].items()):
                text(surface, small, f"{key:16s} {value:+.3f}", (x + 12, 247 + row * 17))
            cooldowns = "  ".join(f"{k}:{v:.1f}" for k, v in list(f["cooldowns"].items())[:3])
            text(surface, small, cooldowns[:43], (x + 12, 467), (148, 166, 191))
