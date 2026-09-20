from collections import deque
import pygame

PALETTE = [(81, 218, 228), (255, 168, 96)]


class Effects:
    def __init__(self):
        self.effects = []
        self.feed = deque(maxlen=4)

    def ingest(self, events: list[dict], state: dict):
        for event in events:
            kind = event["type"]
            target = event["target"]
            actor = event["fighter"]
            values = event["values"]
            position = event["position"] or (0, 0)
            if target is not None and kind in {"DamageApplied", "AttackBlocked", "AttackDodged"}:
                f = state["fighters"][target]
                position = (f["x"], f["y"])
            if kind in {"DamageApplied", "AttackReleased", "Explosion", "Dash", "Teleport", "AttackBlocked", "AttackDodged", "TransformationActivated"}:
                self.effects.append(dict(kind=kind, time=event["timestamp"], position=position,
                                         actor=actor or 0, values=values, duration=max(.4, values.get("duration", .6))))
            if kind in {"AttackHit", "AttackDodged", "AttackBlocked", "TransformationActivated", "FighterKO"}:
                name = state["fighters"][actor]["name"] if actor is not None else ""
                verb = {"AttackHit": "connected", "AttackDodged": "attack evaded", "AttackBlocked": "attack blocked",
                        "TransformationActivated": "transformed", "FighterKO": "KO"}[kind]
                self.feed.append((event["timestamp"], f"{name} · {verb}"))

    def draw(self, surface, camera, time, font):
        self.effects = [e for e in self.effects if time - e["time"] < min(1.2, e["duration"])]
        for e in self.effects:
            age = max(0, time - e["time"])
            point = camera.point(*e["position"])
            color = PALETTE[e["actor"]]
            values = e["values"]
            kind = e["kind"]
            if kind == "DamageApplied" and values.get("damage", 0) > 0:
                text = font.render(f"−{values['damage']:.0f}", True, (255, 225, 211))
                surface.blit(text, (point[0] - text.get_width() / 2, point[1] - 48 - age * 38))
            elif kind == "AttackReleased":
                attack_type = values.get("attack_type")
                target = camera.point(*values.get("target_position", e["position"]))
                if attack_type == "beam":
                    pygame.draw.line(surface, color, point, target, max(2, int(9 * (1 - age))))
                    pygame.draw.line(surface, (250, 244, 224), point, target, 2)
                elif attack_type in {"melee", "charged_melee", "grapple"}:
                    radius = round(20 + age * 32)
                    pygame.draw.circle(surface, color, target, radius, 2)
                    pygame.draw.line(surface, color, point, target, 3)
            elif kind == "Explosion":
                center = camera.point(*values["center"])
                radius = max(4, round(values["radius"] * camera.scale * min(1, .25 + age * 2)))
                pygame.draw.circle(surface, color, center, radius, max(1, round(4 - age * 3)))
            elif kind in {"AttackBlocked", "AttackDodged"}:
                label = font.render("BLOCK" if kind == "AttackBlocked" else "DODGE", True, color)
                surface.blit(label, (point[0] - label.get_width() / 2, point[1] - 64 - age * 20))
            elif kind in {"Dash", "Teleport"}:
                pygame.draw.circle(surface, color, point, round(12 + age * 20), 2)
            elif kind == "TransformationActivated":
                pygame.draw.circle(surface, (238, 225, 149), point, round(22 + age * 48), 2)
