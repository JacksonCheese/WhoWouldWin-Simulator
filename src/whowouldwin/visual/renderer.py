import math
import pygame
from .camera import Camera
from .effects import Effects, PALETTE
from .hud import draw_hud, text


class Renderer:
    """Consumes plain snapshots/events; imports no combat rules."""
    def __init__(self, surface, arena):
        self.surface = surface
        self.camera = Camera(*surface.get_size(), arena["width"], arena["height"])
        self.fonts = (pygame.font.SysFont("Menlo", 13), pygame.font.SysFont("Helvetica", 18), pygame.font.SysFont("Helvetica", 28, bold=True))
        self.effects = Effects()

    def draw(self, state, *, speed=1, paused=False, seed=42, debug=False, mode="live"):
        surface, camera = self.surface, self.camera
        camera.update(state["fighters"])
        width, height = surface.get_size()
        surface.fill((12, 19, 32))
        surface.set_clip(pygame.Rect(0, 204, width, height - 268))
        # Stable geometric skyline and arena grid; no randomness affects rendering.
        for i in range(16):
            building_height = 30 + (i * 31) % 110
            pygame.draw.rect(surface, (17, 28, 44), (i * width // 15, camera.floor - building_height, width // 20, building_height))
        for x in range(0, int(camera.arena_width) + 1, 10):
            pygame.draw.line(surface, (25, 39, 57), camera.point(x, 0), camera.point(x, camera.arena_height), 1)
        for y in range(0, int(camera.arena_height) + 1, 5):
            pygame.draw.line(surface, (25, 39, 57), camera.point(0, y), camera.point(camera.arena_width, y), 1)
        pygame.draw.rect(surface, (22, 34, 48), (0, camera.floor, width, 62))
        pygame.draw.line(surface, (89, 120, 142), (0, camera.floor), (width, camera.floor), 2)
        text(surface, self.fonts[0], "ARENA 01  /  " + f"{camera.arena_width:g} × {camera.arena_height:g} m", (32, 211), (104, 128, 152))
        for p in state["projectiles"]:
            point = camera.point(p["x"], p["y"])
            pygame.draw.circle(surface, PALETTE[p["owner"]], point, 7)
            pygame.draw.circle(surface, (243, 248, 251), point, 3)
        for f in state["fighters"]:
            self._fighter(f, state["time"])
        self.effects.draw(surface, camera, state["time"], self.fonts[1])
        surface.set_clip(None)
        for row, (time, entry) in enumerate(self.effects.feed):
            text(surface, self.fonts[0], f"{time:05.1f}  {entry}", (width - 338, height - 144 + row * 17), (139, 161, 185))
        draw_hud(surface, state, self.fonts, speed, paused, seed, debug, mode)
        if state["done"]:
            panel = pygame.Surface((560, 110), pygame.SRCALPHA)
            panel.fill((12, 19, 32, 240))
            x, y = width // 2 - 280, 236
            surface.blit(panel, (x, y))
            winner = state["winner"]
            label = f"{state['fighters'][winner]['name']} wins" if winner is not None else "Draw"
            text(surface, self.fonts[2], label, (x + 24, y + 18))
            text(surface, self.fonts[1], f"{state['condition'].replace('_', ' ').upper()}  ·  {state['time']:.2f}s  ·  R to replay", (x + 24, y + 64), (159, 184, 207))

    def _fighter(self, f, time):
        surface, camera = self.surface, self.camera
        x, y = camera.point(f["x"], f["y"])
        color = PALETTE[f["slot"]] if f["health"] > 0 else (98, 108, 124)
        r = max(8, min(20, round(camera.scale * f["radius"])))
        pygame.draw.ellipse(surface, (7, 12, 21), (x - r * 2, camera.floor - 4, r * 4, 8))
        if f["form"]:
            pygame.draw.circle(surface, (193, 175, 105), (x, y - r), round(r * 2.8 + 3 * math.sin(time * 8)), 2)
        if "decoy" in f["statuses"]:
            for offset in (-28, 28):
                pygame.draw.circle(surface, (46, 100, 119), (x + offset, y - r), r, 1)
        if f["flying"]:
            for offset in (-5, 5):
                pygame.draw.line(surface, (115, 134, 167), (x + offset, y + r), (x + offset, y + r + 16), 2)
        if f["defense"] == "dodge":
            for i in range(1, 4):
                pygame.draw.line(surface, (60, 114, 143), (x - i * 8, y - 10), (x - i * 8 - 15, y + 5), 2)
        # Abstract silhouette: head, torso, arms, and independently animated legs.
        moving = min(1, abs(f["vx"]) / 5)
        stride = round(math.sin(time * 14) * 5 * moving)
        pygame.draw.line(surface, color, (x - 4, y), (x - 7 - stride, y + r), 4)
        pygame.draw.line(surface, color, (x + 4, y), (x + 7 + stride, y + r), 4)
        if f["id"] in {"omniman", "homelander"}:
            pygame.draw.polygon(surface, color, [(x - r, y - 2 * r), (x + r, y - 2 * r), (x + 5, y + 2), (x - 5, y + 2)])
        else:
            pygame.draw.rect(surface, color, (x - 6, y - 2 * r, 12, 2 * r), border_radius=4)
        pygame.draw.circle(surface, color, (x, y - 3 * r), max(5, r - 2))
        pygame.draw.line(surface, color, (x - 6, y - r * 2 + 4), (x - r - 5, y - r + stride), 3)
        pygame.draw.line(surface, color, (x + 6, y - r * 2 + 4), (x + r + 5, y - r - stride), 3)
        if f["defense"] == "block" or "shield" in f["statuses"]:
            pygame.draw.circle(surface, color, (x, y - r), r * 3, 2)
        if f["pending"]:
            pygame.draw.circle(surface, (237, 210, 153), (x + r + 4, y - r), 6, 2)
        label = self.fonts[0].render(f["name"], True, color)
        label_x = max(12, min(surface.get_width() - label.get_width() - 12, x - label.get_width() / 2))
        surface.blit(label, (label_x, y - r * 5 - 4 - f["slot"] * 17))
        statuses = list(f["statuses"])
        if f["form"]:
            statuses.append(f["form"].upper())
        if statuses:
            label = self.fonts[0].render(" · ".join(statuses), True, (232, 206, 141))
            label_x = max(12, min(surface.get_width() - label.get_width() - 12, x - label.get_width() / 2))
            surface.blit(label, (label_x, y - r * 6 - 10 - f["slot"] * 17))
