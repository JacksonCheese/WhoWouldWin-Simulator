from math import isfinite
from random import Random
import pytest
from whowouldwin.characters.schema import Ability, Character
from whowouldwin.combat.actions import legal_abilities, start_action, resolve_support
from whowouldwin.combat.damage import resolve_hit, expected_damage
from whowouldwin.combat.movement import move, separate
from whowouldwin.combat.status_effects import update_fighter
from whowouldwin.combat.state import Projectile
from whowouldwin.combat.fighter import Pending
from whowouldwin.simulation.engine import Engine
from whowouldwin.combat.environment import Matchup, Rules


def attack(**kwargs):
    return Ability(id="test", name="Test", type="melee", damage=50, hit_modifier=1, critical_chance=0, **kwargs)


def test_resources_cooldowns_and_legal_actions(engine):
    f, target = engine.world.fighters
    ability = next(a for a in f.profile.abilities if a.id == "energy_orb")
    stamina, energy = f.stamina, f.energy
    start_action(f, target, ability, .05, engine.emit)
    assert f.energy == energy - ability.energy_cost
    assert f.stamina == stamina - ability.stamina_cost
    assert ability.id in f.cooldowns
    assert ability not in legal_abilities(f, target)
    for _ in range(40):
        update_fighter(f, engine.world.fighters, .05, engine.emit)
    f.pending = None
    assert ability.id not in f.cooldowns
    assert ability in legal_abilities(f, target)
    f.energy = 0
    assert ability not in legal_abilities(f, target)


def test_startup_never_releases_early(profiles):
    e = Engine(seed=42, profiles=profiles[:2], record=True)
    e.run()
    starts = {}
    for frame in e.frames:
        for event in frame["events"]:
            key = (event["fighter"], event["action"])
            if event["type"] == "AttackStarted":
                starts[key] = event["timestamp"] + event["values"]["startup"]
            elif event["type"] == "AttackReleased":
                assert event["timestamp"] + 1e-8 >= starts[key]


def test_health_and_resources_stay_bounded(profiles):
    for seed in range(10):
        e = Engine(seed=seed, profiles=profiles[:2])
        while not e.world.done:
            e.step()
            for f in e.world.fighters:
                assert 0 <= f.health <= f.profile.resources.health
                assert 0 <= f.energy <= f.profile.resources.energy
                assert 0 <= f.stamina <= f.profile.resources.stamina
                assert all(isfinite(x) for x in (f.health, f.x, f.y, f.vx, f.vy))


def test_horizontal_movement_and_boundaries(engine):
    f, target = engine.world.fighters
    f.x, target.x = 10, 100
    for _ in range(20):
        move(f, target, engine.world.arena, .05)
    assert f.x > 10 and f.vx > 0
    f.x, f.vx = 119, 500
    move(f, target, engine.world.arena, .2)
    assert f.x <= 119


def test_collision_separation(engine):
    a, b = engine.world.fighters
    a.x = b.x = 50
    separate(a, b, engine.world.arena)
    assert abs(a.x - b.x) == pytest.approx(2)


def test_jump_and_flight(engine):
    target, f = engine.world.fighters
    fly = next(a for a in f.profile.abilities if a.type == "flight")
    resolve_support(f, target, fly, engine.emit, engine.apply_status)
    for _ in range(30):
        move(f, target, engine.world.arena, .05)
    assert f.flying and f.y > 1
    f.flight_time = .01
    update_fighter(f, engine.world.fighters, .05, engine.emit)
    assert not f.flying
    for _ in range(100):
        move(f, target, engine.world.arena, .05)
    assert f.y == f.radius
    jump = next(a for a in f.profile.abilities if a.type == "jump")
    resolve_support(f, target, jump, engine.emit, engine.apply_status)
    move(f, target, engine.world.arena, .05)
    assert f.y > 1 and f.vy > 0


def test_block_reduces_damage(engine):
    a, b = engine.world.fighters
    initial = b.health
    resolve_hit(a, b, attack(), Random(1), engine.emit, engine.apply_status)
    unblocked = initial - b.health
    b.health, b.defense = initial, "block"
    resolve_hit(a, b, attack(), Random(1), engine.emit, engine.apply_status)
    assert 0 < initial - b.health < unblocked
    assert engine.event_counts["AttackBlocked"] == 1


def test_dodge_prevents_hit(engine):
    a, b = engine.world.fighters
    b.defense = "dodge"
    before = b.health
    assert not resolve_hit(a, b, attack(), Random(1), engine.emit, engine.apply_status)
    assert b.health == before
    assert engine.event_counts["AttackDodged"] == 1


def test_grapple_bypasses_block(engine):
    a, b = engine.world.fighters
    b.defense = "block"
    grapple = attack().model_copy(update={"type": "grapple"})
    assert resolve_hit(a, b, grapple, Random(1), engine.emit, engine.apply_status)
    assert not engine.event_counts["AttackBlocked"]


def test_knockback_and_stun_expire(engine):
    a, b = engine.world.fighters
    resolve_hit(a, b, attack(knockback=15, stun=.3), Random(1), engine.emit, engine.apply_status)
    assert b.vx > 0 and "stun" in b.statuses
    for _ in range(10):
        update_fighter(b, engine.world.fighters, .05, engine.emit)
    assert "stun" not in b.statuses and b.stun_immunity > 0
    engine.apply_status(b, "stun", .3, 1, a, "test")
    assert "stun" not in b.statuses


def test_transformation_expiry(engine):
    f, target = engine.world.fighters
    form = next(a for a in f.profile.abilities if a.type == "transform")
    base = f.stat("striking_power")
    resolve_support(f, target, form, engine.emit, engine.apply_status)
    assert f.form and f.stat("striking_power") > base
    assert form not in legal_abilities(f, target)
    f.form_time = .01
    update_fighter(f, engine.world.fighters, .05, engine.emit)
    assert not f.form and f.stat("striking_power") == base


def test_regeneration_decoy_and_shield(engine):
    f, target = engine.world.fighters
    f.health -= 100
    engine.apply_status(f, "regen", 1, 20, f, "heal")
    before = f.health
    update_fighter(f, engine.world.fighters, .5, engine.emit)
    assert f.health >= before + 10
    damage = expected_damage(target, f, attack())
    engine.apply_status(f, "shield", 1, .5, f, "shield")
    assert expected_damage(target, f, attack()) < damage


def test_dash_and_teleport(engine):
    f, target = engine.world.fighters
    f.x, target.x = 15, 100
    teleport = next(a for a in f.profile.abilities if a.type == "teleport")
    resolve_support(f, target, teleport, engine.emit, engine.apply_status)
    assert f.x == 35
    dash = next(a for a in f.profile.abilities if a.type == "dash")
    resolve_support(f, target, dash, engine.emit, engine.apply_status)
    assert f.vx > f.stat("movement_speed")


def test_swept_projectile_hit_and_miss(engine):
    a, b = engine.world.fighters
    a.x, b.x = 10, 20
    ability = Ability(id="bullet", name="Bullet", type="projectile", range=50, damage=30, hit_modifier=1)
    engine.rng = Random(1)
    engine.world.projectiles = [Projectile(1, 0, 1, ability, 10, 1, 1000, 0, .2)]
    before = b.health
    engine._projectiles(.05, [a.position, b.position])
    assert b.health < before and not engine.world.projectiles
    engine.world.projectiles = [Projectile(2, 0, 1, ability, 10, 10, 1000, 0, .01)]
    before = b.health
    engine._projectiles(.05, [a.position, b.position])
    assert b.health == before and engine.event_counts["AttackMissed"]


def test_nonlinear_damage_remains_positive(engine):
    a, b = engine.world.fighters
    a.base["striking_power"], b.base["durability"] = 1, 100000
    value = expected_damage(a, b, attack())
    assert 0 < value < attack().damage


def test_ko_no_resurrection_and_timeout(engine):
    a, b = engine.world.fighters
    a.health = 0
    engine.step()
    assert a.health == 0 and engine.world.winner == 1 and engine.world.condition == "ko"
    tick = engine.world.tick
    engine.step()
    assert engine.world.tick == tick
    e = Engine(Matchup(rules=Rules(timeout=.1)))
    assert e.run()["condition"] == "timeout" and e.world.winner is None


def test_simultaneous_attacks_can_mutual_ko(engine):
    a, b = engine.world.fighters
    ability = attack(range=100).model_copy(update={"damage": 100000})
    engine.rng = Random(1)
    for f in (a, b):
        f.health, f.busy = 1, 100
        f.pending = Pending(ability, .01, (50, 1))
    engine.step()
    assert engine.world.condition == "mutual_ko"
    assert engine.world.winner is None


def test_death_and_incapacitation():
    e = Engine(Matchup(rules=Rules(lethal=True)))
    e.world.fighters[0].health = 0
    e.step()
    assert e.world.condition == "death"
    e = Engine(Matchup(rules=Rules(incapacitation_seconds=.1)))
    a, b = e.world.fighters
    e.apply_status(a, "incapacitated", 1, 1, b, "capture")
    e.step(); e.step()
    assert e.world.condition == "incapacitation" and e.world.winner == 1


@pytest.mark.parametrize("duration,expected", [(3.0, True), (2.99, False)])
def test_incapacitation_exact_duration_boundary(duration, expected):
    e = Engine(Matchup())
    a, b = e.world.fighters
    a.busy = b.busy = 100
    e.apply_status(a, "incapacitated", duration, 1, b, "capture")
    for _ in range(60):
        e.step()
    assert e.world.done is expected
    if expected:
        assert e.result()["finisher"] == "capture"
