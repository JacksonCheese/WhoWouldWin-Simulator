from collections import Counter
from math import sqrt
from statistics import mean, median


def wilson_interval(wins: int, total: int) -> list[float]:
    z = 1.96
    p = wins / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(100 * max(0, center - margin), 3), round(100 * min(1, center + margin), 3)]


class Metrics:
    """Streaming aggregates: memory grows with durations, not complete battle logs."""
    def __init__(self, profiles):
        self.profiles = profiles
        self.durations = []
        self.wins = [0, 0]
        self.conditions = Counter()
        self.win_conditions = [Counter(), Counter()]
        self.uses = [Counter(), Counter()]
        self.hits = [Counter(), Counter()]
        self.ability_damage = [Counter(), Counter()]
        self.finishers = [Counter(), Counter()]
        self.dealt = [0., 0.]
        self.received = [0., 0.]
        self.remaining = [0., 0.]
        self.event_counts = Counter()
        self.interesting = {}
        self.per_winner = {}

    def add(self, result: dict):
        self.durations.append(result["duration"])
        self.conditions[result["condition"]] += 1
        self.event_counts.update(result["events"])
        winner = result["winner"]
        if winner is not None:
            self.wins[winner] += 1
            self.win_conditions[winner][result["condition"]] += 1
            self.finishers[winner][result["finisher"] or result["condition"]] += 1
            self.remaining[winner] += result["fighters"][winner]["health"]
            self.per_winner.setdefault(winner, result)
        for i, fighter in enumerate(result["fighters"]):
            self.uses[i].update(fighter["uses"])
            self.hits[i].update(fighter["hits"])
            self.ability_damage[i].update(fighter["damage_by_ability"])
            self.dealt[i] += fighter["damage_dealt"]
            self.received[i] += fighter["damage_received"]
        def keep(key, rank):
            if key not in self.interesting or rank(result) < rank(self.interesting[key]):
                self.interesting[key] = result
        keep("fastest", lambda r: r["duration"])
        keep("longest", lambda r: -r["duration"])
        if winner is not None:
            keep("closest", lambda r: r["fighters"][r["winner"]]["health_fraction"])
            keep("dominant", lambda r: -r["fighters"][r["winner"]]["health_fraction"])

    def report(self) -> dict:
        n = len(self.durations)
        if not n:
            raise ValueError("At least one fight is required")
        minority = min(range(2), key=lambda i: self.wins[i])
        if self.wins[0] != self.wins[1] and minority in self.per_winner:
            self.interesting["upset"] = self.per_winner[minority]
        fighters = []
        for i, p in enumerate(self.profiles):
            names = {a.id: a.name for a in p.abilities}
            abilities = [{"id": key, "name": names.get(key, key), "uses": count,
                          "hits": self.hits[i][key], "hit_rate": 100 * self.hits[i][key] / count,
                          "damage": self.ability_damage[i][key],
                          "mean_uses_per_fight": count / n}
                         for key, count in self.uses[i].most_common()]
            finishers = [{"id": key, "name": names.get(key, key), "count": count,
                          "percent_of_wins": 100 * count / self.wins[i]}
                         for key, count in self.finishers[i].most_common()]
            fighters.append({"slot": i, "id": p.identity.id, "name": p.identity.name, "wins": self.wins[i],
                             "win_percent": 100 * self.wins[i] / n,
                             "win_percent_95ci": wilson_interval(self.wins[i], n),
                             "average_damage_dealt": self.dealt[i] / n,
                             "average_damage_received": self.received[i] / n,
                             "average_winner_remaining_health": self.remaining[i] / self.wins[i] if self.wins[i] else None,
                             "abilities": abilities,
                             "most_successful_abilities": sorted((a for a in abilities if a["hits"]), key=lambda a: (-a["hits"], -a["damage"])),
                             "finishers": finishers,
                             "win_conditions": {k: {"count": v, "percent_of_runs": 100 * v / n, "percent_of_wins": 100 * v / self.wins[i]}
                                                for k, v in self.win_conditions[i].items()}})
        maximum = max(self.durations)
        bin_width = max(1, maximum / 20)
        counts = [0] * 20
        for duration in self.durations:
            counts[min(19, int(duration / bin_width))] += 1
        return {"runs": n, "scaling_note": self.profiles[0].scaling_note,
                "fighters": fighters, "draws": n - sum(self.wins), "draw_percent": 100 * (n - sum(self.wins)) / n,
                "duration": {"median": median(self.durations), "mean": mean(self.durations),
                             "shortest": min(self.durations), "longest": maximum,
                             "histogram": {"edges": [i * bin_width for i in range(21)], "counts": counts}},
                "conditions": dict(self.conditions), "event_counts": dict(self.event_counts),
                "interesting": {key: {"seed": r["seed"], "winner": r["winner"], "duration": r["duration"]}
                                for key, r in self.interesting.items()}}
