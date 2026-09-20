from dataclasses import dataclass


@dataclass
class Camera:
    width: int
    height: int
    arena_width: float
    arena_height: float
    focus_x: float | None = None
    zoom: float | None = None

    def update(self, fighters):
        left, right = min(f["x"] for f in fighters), max(f["x"] for f in fighters)
        span = min(self.arena_width, max(36, right - left + 24))
        vertical = max(15, max(f["y"] for f in fighters) + 6)
        self.zoom = min((self.width - 120) / span, (self.height - 320) / vertical)
        visible_half = (self.width - 120) / self.zoom / 2
        center = (left + right) / 2
        self.focus_x = max(visible_half, min(self.arena_width - visible_half, center)) if visible_half * 2 < self.arena_width else self.arena_width / 2

    @property
    def scale(self):
        return self.zoom or min((self.width - 100) / self.arena_width, (self.height - 290) / self.arena_height)

    @property
    def floor(self):
        return self.height - 126

    def point(self, x: float, y: float) -> tuple[int, int]:
        return round(self.width / 2 + (x - (self.focus_x if self.focus_x is not None else self.arena_width / 2)) * self.scale), round(self.floor - y * self.scale)
