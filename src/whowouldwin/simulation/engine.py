"""Authoritative fixed-tick orchestration. No rendering or character-specific behavior."""
from collections import Counter
from math import ceil, hypot
from random import Random
from whowouldwin.characters.schema import Character
from whowouldwin.characters.loader import load_character
from whowouldwin.combat.environment import Matchup
from whowouldwin.combat.fighter import Fighter
from whowouldwin.combat.state import World, Projectile
from whowouldwin.combat.actions import start_action, resolve_support
from whowouldwin.combat.ability import ATTACK_TYPES
from whowouldwin.combat.movement import move, separate, clamp_to_arena
from whowouldwin.combat.damage import resolve_hit
from whowouldwin.combat.status_effects import update_fighter, apply_status
from whowouldwin.ai.utility_ai import choose_action
from whowouldwin.ai.targeting import distance, direction, segment_distance
from .events import CombatEvent


class Engine:
    def __init__(self, config: Matchup | None = None, *, seed: int | None = None,
                 profiles: tuple[Character, Character] | None = None, record: bool = False):
        self.config = config or Matchup()
        self.seed = self.config.seed if seed is None else seed
        self.rng = Random(self.seed)
        self.profiles = profiles or (load_character(self.config.fighter_a), load_character(self.config.fighter_b))
        mid = self.config.arena.width / 2
        gap = self.config.starting_distance / 2
        self.world = World([Fighter(i, p, p.stats(getattr(self.config.scaling, f"fighter_{'ab'[i]}")), mid + (-gap if i == 0 else gap))
                            for i, p in enumerate(self.profiles)], self.config.arena)
        self.record = record
        self.events: list[dict] = []
        self.frames: list[dict] = []
        self.event_counts: Counter = Counter()
        self.projectile_id = 0
        self.emit("FightStarted", seed=self.seed, fighters=[p.identity.id for p in self.profiles])
        self._capture()

    def emit(self, kind: str, fighter: Fighter | None = None, target: Fighter | None = None,
             action: str | None = None, **values):
        self.event_counts[kind] += 1
        if self.record:
            event = CombatEvent(kind, self.world.tick, self.world.time,
                                fighter.slot if fighter else None, target.slot if target else None,
                                action, fighter.position if fighter else None, values)
            self.events.append(event.to_dict())

    def _capture(self):
        if self.record:
            self.frames.append({"state": self.world.snapshot(), "events": list(self.events)})

    def apply_status(self, f, name, duration, magnitude, source, action):
        apply_status(f, name, duration, magnitude, source, action, self.emit)

    def step(self) -> World:
        w = self.world
        if w.done:
            return w
        dt = self.config.rules.timestep
        w.tick += 1
        w.time = round(w.tick * dt, 9)
        self.events = []
        old_positions = [f.position for f in w.fighters]
        for f in w.fighters:
            update_fighter(f, w.fighters, dt, self.emit)
        # Both AIs perceive the same pre-commit state. Initiative changes commit
        # ordering, never which fighter receives a free first decision.
        decisions = []
        for f in w.fighters:
            if f.alive and f.busy <= 1e-8 and f.decision <= 1e-8 and not f.pending:
                target = w.fighters[1 - f.slot]
                action, parts = choose_action(f, target, w, self.rng, self.config.rules.bloodlusted)
                f.debug = parts
                f.decision = .28 / f.stat("reaction_speed")
                if action:
                    decisions.append((f.stat("reaction_speed") + self.rng.random() * .5, f, target, action))
                    self.emit("ActionChosen", f, target, action.id, utility=parts)
        for _, f, target, action in sorted(decisions, key=lambda v: -v[0]):
            start_action(f, target, action, dt, self.emit)
        for f in w.fighters:
            move(f, w.fighters[1 - f.slot], w.arena, dt, self.config.rules.bloodlusted)
        separate(*w.fighters, w.arena)
        # Collect all due attacks before damage. Simultaneous releases can trade
        # and produce a mutual KO; a stun cannot erase a release already due.
        due = []
        for f in w.fighters:
            if f.pending:
                f.pending.remaining -= dt
                if f.pending.remaining <= 1e-8:
                    due.append((f, f.pending))
                    f.pending = None
        for f, pending in due:
            self._resolve(f, w.fighters[1 - f.slot], pending.ability, pending.target_position)
        self._projectiles(dt, old_positions)
        self._victory()
        self._capture()
        return w

    def _resolve(self, f, target, ability, locked_position):
        a = ability
        if a.type not in ATTACK_TYPES:
            if f.alive:
                resolve_support(f, target, a, self.emit, self.apply_status)
                clamp_to_arena(f, self.world.arena)
            return
        if a.mobility_distance:
            dx, dy = direction(f.x, f.y, target.x, target.y)
            gap = min(a.mobility_distance, max(0, distance(f, target) - 2.5))
            f.x += dx * gap
            f.y += dy * gap
            clamp_to_arena(f, self.world.arena)
            self.emit("Dash", f, target, a.id)
        self.emit("AttackReleased", f, target, a.id, attack_type=a.type,
                  target_position=target.position, radius=a.area_of_effect, duration=a.active)
        if a.type == "projectile":
            travel = distance(f, target) / a.projectile_speed
            lead = min(.7, travel) * f.profile.combat.battle_iq
            dx, dy = direction(f.x, f.y, target.x + target.vx * lead, target.y + target.vy * lead)
            self.projectile_id += 1
            p = Projectile(self.projectile_id, f.slot, target.slot, a, f.x, f.y,
                           dx * a.projectile_speed, dy * a.projectile_speed,
                           (a.range + 2) / a.projectile_speed)
            self.world.projectiles.append(p)
            self.emit("ProjectileSpawned", f, target, a.id, projectile=p.snapshot())
        else:
            d = distance(f, target)
            # Ground-targeted area attacks lock their center on commitment.
            if a.type == "area":
                center = locked_position if a.targeting == "ground" else f.position
                in_range = hypot(target.x - center[0], target.y - center[1]) <= a.area_of_effect + target.radius
                self.emit("Explosion", f, target, a.id, center=center, radius=a.area_of_effect)
            else:
                in_range = a.minimum_range <= d <= a.range + f.radius + target.radius
            if in_range:
                resolve_hit(f, target, a, self.rng, self.emit, self.apply_status)
            else:
                self.emit("AttackMissed", f, target, a.id, reason="range")

    def _projectiles(self, dt, old_positions):
        live = []
        for p in self.world.projectiles:
            f, target = self.world.fighters[p.owner], self.world.fighters[p.target]
            ox, oy = p.x, p.y
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.remaining -= dt
            tx, ty = old_positions[p.target]
            collided = segment_distance(ox - tx, oy - ty, p.x - target.x, p.y - target.y) <= target.radius + .55
            expired = p.remaining <= 0 or not 0 <= p.x <= self.world.arena.width or not 0 <= p.y <= self.world.arena.height
            if collided or expired:
                blast = p.ability.area_of_effect
                self.emit("ProjectileExpired", f, target, p.ability.id, projectile_id=p.id, position=(p.x, p.y))
                if blast:
                    self.emit("Explosion", f, target, p.ability.id, center=(p.x, p.y), radius=blast)
                if collided or blast and hypot(p.x - target.x, p.y - target.y) <= blast + target.radius:
                    resolve_hit(f, target, p.ability, self.rng, self.emit, self.apply_status)
                else:
                    self.emit("AttackMissed", f, target, p.ability.id, reason="trajectory")
            else:
                live.append(p)
        self.world.projectiles = live

    def _victory(self):
        w = self.world
        fallen = [f for f in w.fighters if not f.alive]
        incapacitated = [f for f in w.fighters if f.control_time + 1e-8 >= self.config.rules.incapacitation_seconds]
        if fallen:
            w.done = True
            w.winner = 1 - fallen[0].slot if len(fallen) == 1 else None
            w.condition = "mutual_ko" if len(fallen) == 2 else ("death" if self.config.rules.lethal else "ko")
            for f in fallen:
                self.emit("FighterKO", f, action=f.last_damage_action)
        elif incapacitated:
            w.done = True
            w.winner = 1 - incapacitated[0].slot if len(incapacitated) == 1 else None
            w.condition = "incapacitation" if len(incapacitated) == 1 else "draw"
        elif w.tick >= ceil(self.config.rules.timeout / self.config.rules.timestep):
            w.done, w.winner, w.condition = True, None, "timeout"
        if w.done:
            self.emit("FightEnded", winner=w.winner, condition=w.condition, duration=w.time)

    def run(self) -> dict:
        while not self.world.done:
            self.step()
        return self.result()

    def result(self) -> dict:
        if not self.world.done:
            raise RuntimeError("Fight is still running")
        w = self.world
        loser = w.fighters[1 - w.winner] if w.winner is not None else None
        finisher = loser.last_damage_action if loser else None
        if w.condition == "incapacitation" and loser:
            finisher = loser.control_action or "control"
        return {"seed": self.seed, "winner": w.winner, "condition": w.condition, "duration": w.time,
                "ticks": w.tick, "finisher": finisher, "events": dict(self.event_counts),
                "fighters": [{"id": f.profile.identity.id, "name": f.profile.identity.name,
                              "health": f.health, "health_fraction": f.health_fraction,
                              "damage_dealt": f.damage_dealt, "damage_received": f.damage_received,
                              "uses": dict(f.uses), "hits": dict(f.hits), "damage_by_ability": dict(f.damage_by_ability)}
                             for f in w.fighters]}
