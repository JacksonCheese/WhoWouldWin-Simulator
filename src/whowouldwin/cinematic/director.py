"""Deterministic replay -> choreography compiler.

Only presentation time is stretched. Authoritative timestamps, health samples,
damage records, source ordering and the final result are copied without editing.
"""
from bisect import bisect_right
import json
from math import hypot
from .profiles import load_visual_profile
from whowouldwin.simulation.replay import digest

DIRECTOR_VERSION = "1.0.0"
IMPORTANT = {"AttackStarted", "AbilityStarted", "AttackReleased", "AttackHit", "AttackMissed", "AttackDodged",
             "AttackBlocked", "DamageApplied", "StatusApplied", "StatusExpired", "TransformationActivated",
             "TransformationEnded", "Knockback", "FlightStarted", "FlightEnded", "Dash", "Teleport", "Jump",
             "FighterKO", "FightEnded", "ActionInterrupted", "ProjectileSpawned", "ProjectileExpired", "DefenseActivated"}


class PresentationClock:
    """Piecewise monotonic time map with explicit holds, intro and outro."""
    def __init__(self, duration: float, impacts: list[dict], forms: list[float]):
        windows = []
        holds = {}
        for hit in impacts:
            t, intensity = hit["simulationTime"], hit["intensity"]
            stop = .18 if hit["finisher"] else (.11 if intensity >= .65 else (.06 if intensity >= .3 else .025))
            holds[t] = max(holds.get(t, 0), stop)
            if intensity >= .65 or hit["finisher"]:
                windows.append((max(0, t - .28), min(duration, t + .24), .32 if hit["finisher"] else .7))
        windows.extend((max(0, t - .12), min(duration, t + .6), .72) for t in forms)
        boundaries = sorted({0., duration, *holds, *(v for a, b, _ in windows for v in (a, b))})
        self.segments = [{"start": 0., "end": 1.8, "simulationStart": 0., "simulationEnd": 0., "kind": "intro"}]
        now = 1.8
        self.arrivals = {0.: now}
        for i, start in enumerate(boundaries[:-1]):
            if start in holds:
                self.segments.append({"start": now, "end": now + holds[start], "simulationStart": start, "simulationEnd": start, "kind": "hitstop"})
                now += holds[start]
            end = boundaries[i + 1]
            middle = (start + end) / 2
            rate = min((rate for a, b, rate in windows if a <= middle <= b), default=1.)
            length = (end - start) / rate
            self.segments.append({"start": now, "end": now + length, "simulationStart": start, "simulationEnd": end, "kind": "slow" if rate < 1 else "play"})
            now += length
            self.arrivals[end] = now
        if duration in holds:
            self.segments.append({"start": now, "end": now + holds[duration], "simulationStart": duration, "simulationEnd": duration, "kind": "hitstop"})
            now += holds[duration]
        self.segments.append({"start": now, "end": now + 2.6, "simulationStart": duration, "simulationEnd": duration, "kind": "outro"})
        self.duration = now + 2.6

    def presentation_time(self, simulation: float) -> float:
        if simulation in self.arrivals:
            return self.arrivals[simulation]
        for seg in self.segments:
            a, b = seg["simulationStart"], seg["simulationEnd"]
            if a <= simulation <= b and b > a:
                return seg["start"] + (simulation - a) / (b - a) * (seg["end"] - seg["start"])
        raise ValueError("Simulation time outside replay")


def _source_events(replay):
    return [(i, e) for i, e in enumerate(e for frame in replay["frames"] for e in frame["events"])]


def _movement(frames, slot, important_times):
    samples = []
    for frame in frames:
        s, f = frame["state"], frame["state"]["fighters"][slot]
        samples.append({"time": s["time"], "x": f["x"], "y": f["y"], "vx": f["vx"], "vy": f["vy"],
                        "flying": f["flying"], "form": f["form"], "stunned": "stun" in f["statuses"],
                        "teleport": any(e["type"] == "Teleport" and e["fighter"] == slot for e in frame["events"])})
    # Keep event boundaries and state changes. Reduce only nearly linear spans,
    # with a maximum 0.15-second spacing and 0.025-unit linear error budget.
    kept = [samples[0]]
    for i in range(1, len(samples) - 1):
        before, current, after = kept[-1], samples[i], samples[i + 1]
        t = (current["time"] - before["time"]) / (after["time"] - before["time"])
        error = hypot(current["x"] - (before["x"] + t * (after["x"] - before["x"])),
                      current["y"] - (before["y"] + t * (after["y"] - before["y"])))
        changed = any(current[k] != before[k] or current[k] != after[k] for k in ("flying", "form", "stunned", "teleport"))
        if error > .025 or after["time"] - before["time"] > .15 or current["time"] in important_times or changed:
            kept.append(current)
    kept.append(samples[-1])
    return kept


def compile_cinematic(replay: dict, *, profile_directory=None) -> dict:
    frames, result = replay["frames"], replay["result"]
    if not frames or not frames[-1]["state"]["done"]:
        raise ValueError("Cinematic export needs a completed authoritative replay")
    indexed = _source_events(replay)
    profiles = [load_visual_profile(c, profile_directory) for c in replay["characters"]]
    mappings = [{a["abilityId"]: a for a in p["abilities"]} for p in profiles]
    raw_abilities = [{a["id"]: a for a in p["abilities"]} for p in replay["characters"]]
    lookup = {(e["timestamp"], e["fighter"], e["target"], e["action"], e["type"]): e for _, e in indexed}
    impacts, damage = [], []
    for i, e in indexed:
        if e["type"] != "DamageApplied":
            continue
        v, t = e["values"], e["timestamp"]
        row = {"sourceIndex": i, "tick": e["tick"], "simulationTime": t,
               "actor": e["fighter"], "target": e["target"], "ability": e["action"], "damage": v["damage"], "healthAfter": v["health"]}
        damage.append(row)
        is_hit = (t, e["fighter"], e["target"], e["action"], "AttackHit") in lookup
        if not is_hit or v["damage"] <= 0:
            continue  # DOT remains authoritative, but does not create 20 hit-stops/sec.
        knock = lookup.get((t, e["fighter"], e["target"], e["action"], "Knockback"), {}).get("values", {}).get("force", 0)
        maximum = replay["characters"][e["target"]]["resources"]["health"]
        finisher = v["health"] <= 0
        intensity = min(1., max(v["damage"] / maximum * 3.8, knock / 32, 1. if finisher else .12))
        impacts.append(dict(row, intensity=intensity, knockback=knock, finisher=finisher,
                            importance=min(1., intensity + (.2 if frames[min(e["tick"], len(frames)-1)]["state"]["fighters"][e["fighter"]]["health"] / replay["characters"][e["fighter"]]["resources"]["health"] < .2 else 0))))
    forms = [e["timestamp"] for _, e in indexed if e["type"] == "TransformationActivated"]
    clock = PresentationClock(result["duration"], impacts, forms)
    for row in damage:
        row["presentationTime"] = clock.presentation_time(row["simulationTime"])
    timeline = []
    for i, e in indexed:
        if e["type"] not in IMPORTANT:
            continue
        values = e["values"]
        timeline.append({"sourceIndex": i, "tick": e["tick"], "simulationTime": e["timestamp"],
                         "presentationTime": clock.presentation_time(e["timestamp"]), "type": e["type"],
                         "actor": -1 if e["fighter"] is None else e["fighter"], "target": -1 if e["target"] is None else e["target"],
                         "ability": e["action"] or "", "damage": values.get("damage", 0), "healthAfter": values.get("health", -1),
                         "x": (e["position"] or [0, 0])[0], "y": (e["position"] or [0, 0])[1],
                         "valuesJson": json.dumps(values, sort_keys=True, separators=(",", ":"))})
    cues, moments = [], []
    def cue(kind, event, index, start, end, intensity=.3, variant=0, actor=None):
        who = event["fighter"] if actor is None else actor
        if who is None or who < 0:
            return
        mapping = mappings[event["fighter"]].get(event["action"], {}) if event["fighter"] is not None else {}
        cues.append({"kind": kind, "actor": who, "target": event["target"] if event["target"] is not None else 1-who,
                     "ability": event["action"] or "", "start": max(0, start), "end": max(start+.01, end),
                     "simulationTime": event["timestamp"], "sourceIndex": index, "intensity": intensity,
                     "variant": variant, "vfx": mapping.get("vfx", "impact"), "sound": mapping.get("sound", "impact"),
                     "presentationalOnly": True})
    starts, combo = {}, {}
    release_rows = []
    for index, e in indexed:
        t, actor, action, kind = e["timestamp"], e["fighter"], e["action"], e["type"]
        ct = clock.presentation_time(t)
        if actor is None:
            continue
        mapping = mappings[actor].get(action, {})
        key = actor, action
        if kind in {"AttackStarted", "AbilityStarted"}:
            starts[key] = (ct, index)
            startup = e["values"].get("startup", .15)
            release_t = min(result["duration"], t + startup)
            cue("AnticipateAttack" if kind == "AttackStarted" else "Charge", e, index, ct, clock.presentation_time(release_t), .5 if startup > .5 else .25)
        elif kind == "AttackReleased":
            previous, count = combo.get(actor, (-10, -1))
            count = count + 1 if t - previous < 1.7 else 0
            combo[actor] = t, count
            ability = raw_abilities[actor][action]
            primitive = mapping["primitive"]
            cue(primitive, e, index, max(0, ct - .06), ct + .32, .75 if ability["damage"] >= 100 else .4, count % 3)
            release_rows.append((index, e))
        elif kind == "AttackDodged":
            cue("SuccessfulDodge", e, index, ct - .17, ct + .42, .65, actor=e["target"])
            cue("NearMiss", e, index, ct, ct + .35, .4)
            moments.append({"time": ct, "simulationTime": t, "kind": "dodge", "importance": .72, "actor": e["target"]})
        elif kind == "AttackBlocked":
            cue("BlockImpact", e, index, ct - .08, ct + .4, .4, actor=e["target"])
        elif kind == "AttackMissed":
            cue("NearMiss", e, index, ct, ct + .25, .2)
        elif kind == "TransformationActivated":
            cue("Transformation", e, index, ct, ct + 1.25, 1.)
            moments.append({"time": ct, "simulationTime": t, "kind": "transformation", "importance": .95, "actor": actor})
        elif kind == "StatusApplied" and e["values"].get("status") == "decoy":
            cue("CloneFeint", e, index, ct, ct + min(3, e["values"].get("duration", 2)), .6)
        elif kind == "Knockback":
            cue("Launcher", e, index, ct, ct + .5, min(1., e["values"]["force"] / 25), actor=e["target"])
        elif kind in {"Dash", "Jump", "Teleport", "FlightStarted"}:
            cue({"Dash": "DashPast", "Jump": "JumpAttack", "Teleport": "Teleport", "FlightStarted": "Flight"}[kind], e, index, ct - .14, ct + .28, .65)
        elif kind == "DefenseActivated":
            cue("Guard" if e["values"]["defense"] == "block" else "SuccessfulDodge", e, index, ct, ct + e["values"].get("duration", .4), .35)
    for impact in impacts:
        index = impact["sourceIndex"]
        e = indexed[index][1]
        ct = clock.presentation_time(impact["simulationTime"])
        intensity = impact["intensity"]
        kind = "Finisher" if impact["finisher"] else ("HeavyHit" if intensity >= .65 else "MeleeHit")
        cue(kind, e, index, ct, min(clock.duration, ct + (1.6 if impact["finisher"] else .7)), intensity, actor=e["target"])
        moments.append({"time": ct, "simulationTime": impact["simulationTime"], "kind": kind, "importance": impact["importance"], "actor": e["target"]})
    # Clashes decorate compatible near-simultaneous releases. No new damage.
    for (i, a), (_, b) in zip(release_rows, release_rows[1:]):
        compatible = a["values"].get("attack_type") in {"melee", "charged_melee", "projectile"} and b["values"].get("attack_type") in {"melee", "charged_melee", "projectile"}
        if compatible and a["fighter"] != b["fighter"] and 0 <= b["timestamp"] - a["timestamp"] <= .12:
            ct = clock.presentation_time(b["timestamp"])
            cue("Clash", a, i, ct, ct + .3, .7)
    # Landing and braking are inferred from motion, not extra combat actions.
    for slot in range(2):
        for previous, current in zip(frames, frames[1:]):
            a, b = previous["state"]["fighters"][slot], current["state"]["fighters"][slot]
            if a["y"] > 1.05 and b["y"] <= 1.01 and a["vy"] < -2:
                t = current["state"]["time"]
                synthetic = {"fighter": slot, "target": 1-slot, "action": "", "timestamp": t}
                ct = clock.presentation_time(t)
                cue("GroundImpact", synthetic, -1, ct, ct + .5, min(.8, abs(a["vy"])/25))
    projectiles = _projectiles(frames, indexed, clock, starts, result["duration"])
    fighters = []
    times = {e["timestamp"] for _, e in indexed if e["type"] in IMPORTANT}
    for slot, profile in enumerate(profiles):
        resources = replay["characters"][slot]["resources"]
        health = [{"time": f["state"]["time"], "health": f["state"]["fighters"][slot]["health"],
                   "energy": f["state"]["fighters"][slot]["energy"], "stamina": f["state"]["fighters"][slot]["stamina"]} for f in frames]
        fighters.append({"slot": slot, "id": profile["characterId"], "name": replay["characters"][slot]["identity"]["name"],
                         "maxHealth": resources["health"], "maxEnergy": resources["energy"], "maxStamina": resources["stamina"],
                         "visual": profile, "movement": _movement(frames, slot, times), "health": health})
    final = {"winner": result["winner"] if result["winner"] is not None else -1, "condition": result["condition"],
             "simulationDuration": result["duration"], "finisher": result["finisher"] or "", "health": [f["health"] for f in result["fighters"]]}
    return {"formatVersion": 1, "directorVersion": DIRECTOR_VERSION,
            "metadata": {"title": " vs ".join(f["name"] for f in fighters), "seed": str(replay["seed"]),
                         "engineVersion": replay["engine_version"], "sourceChecksum": replay["checksum"],
                         "scalingNote": replay["characters"][0]["scaling_note"], "simulationDuration": result["duration"],
                         "presentationDuration": clock.duration, "timestep": replay["config"]["rules"]["timestep"],
                         "outcomeDigest": digest(result), "damageDigest": digest(damage)},
            "arena": replay["config"]["arena"], "fighters": fighters, "timeMap": clock.segments,
            "authoritativeTimeline": timeline, "damageTimeline": damage,
            "cues": sorted(cues, key=lambda c: (c["start"], c["sourceIndex"], c["kind"], c["actor"])),
            "moments": sorted(moments, key=lambda m: (m["time"], m["actor"])), "projectiles": projectiles, "finalOutcome": final}


def _projectiles(frames, indexed, clock, starts, duration):
    tracks = {}
    for index, e in indexed:
        v = e["values"]
        if e["type"] == "ProjectileSpawned":
            p = v["projectile"]
            tracks[p["id"]] = {"id": p["id"], "actor": e["fighter"], "target": e["target"], "ability": e["action"],
                               "simulationStart": e["timestamp"], "simulationEnd": duration,
                               "start": clock.presentation_time(e["timestamp"]), "end": clock.presentation_time(duration),
                               "outcome": "inFlight", "points": [{"time": e["timestamp"], "x": p["x"], "y": p["y"]}]}
        elif e["type"] == "ProjectileExpired":
            track = tracks[v["projectile_id"]]
            t = e["timestamp"]
            track.update(simulationEnd=t, end=clock.presentation_time(t), outcome="miss")
            track["points"].append({"time": t, "x": v["position"][0], "y": v["position"][1]})
            for _, follow in indexed[index + 1:]:
                if follow["timestamp"] != t:
                    break
                if follow["fighter"] == e["fighter"] and follow["action"] == e["action"]:
                    if follow["type"] in {"AttackHit", "AttackDodged", "AttackBlocked"}:
                        track["outcome"] = {"AttackHit": "hit", "AttackDodged": "dodge", "AttackBlocked": "block"}[follow["type"]]
                        break
            if track["end"] - track["start"] < .14:
                track["start"] = max(1.8, track["end"] - .14)
    for frame in frames:
        for p in frame["state"]["projectiles"]:
            if p["id"] in tracks:
                tracks[p["id"]]["points"].append({"time": frame["state"]["time"], "x": p["x"], "y": p["y"]})
    for track in tracks.values():
        track["points"].sort(key=lambda p: p["time"])
    return list(tracks.values())
