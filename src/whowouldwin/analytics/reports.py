import csv
import json
import os
from pathlib import Path


def console_report(report: dict) -> str:
    a, b = report["fighters"]
    lines = ["WHO WOULD WIN SIMULATION", f"{a['name']} vs {b['name']}",
             f"Runs: {report['runs']:,} | Seed: {report['seed']} | PLACEHOLDER GAMEPLAY VALUES", ""]
    for f in (a, b):
        ci = f["win_percent_95ci"]
        lines.append(f"{f['name']}: {f['win_percent']:.1f}% ({f['wins']:,} wins; 95% CI {ci[0]:.1f}–{ci[1]:.1f}%)")
    lines += [f"Draws: {report['draw_percent']:.1f}% ({report['draws']:,})", "",
              f"Fight length: median {report['duration']['median']:.2f}s | mean {report['duration']['mean']:.2f}s",
              f"Shortest {report['duration']['shortest']:.2f}s | longest {report['duration']['longest']:.2f}s"]
    for f in (a, b):
        lines += ["", f"{f['name'].upper()}",
                  f"Average damage dealt / received: {f['average_damage_dealt']:.1f} / {f['average_damage_received']:.1f}"]
        remaining = f['average_winner_remaining_health']
        lines.append(f"Winner remaining health: {remaining:.1f}" if remaining is not None else "Winner remaining health: n/a")
        lines.append("Top finishers: " + (", ".join(f"{x['name']} {x['percent_of_wins']:.1f}%" for x in f["finishers"][:4]) or "none"))
        lines.append("Most used: " + ", ".join(f"{x['name']} ({x['uses']:,})" for x in f["abilities"][:3]))
        lines.append("Most successful: " + ", ".join(f"{x['name']} ({x['hits']:,} hits, {x['hit_rate']:.1f}% / use)" for x in f["most_successful_abilities"][:3]))
        lines.append("Win conditions: " + (", ".join(f"{k} {v['percent_of_runs']:.1f}% of runs" for k, v in f["win_conditions"].items()) or "none"))
    lines += ["", report["scaling_note"], "Confidence intervals reflect simulation sampling only, not uncertainty about canon."]
    return "\n".join(lines)


def write_reports(report: dict, directory: str | Path, durations: list[float], *, charts: bool = True) -> list[Path]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "report.json"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    text_path = directory / "report.txt"
    text_path.write_text(console_report(report) + "\n", encoding="utf-8")
    csv_path = directory / "summary.csv"
    fields = ["slot", "id", "name", "wins", "win_percent", "average_damage_dealt", "average_damage_received", "average_winner_remaining_health"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["fighters"])
    duration_path = directory / "durations.csv"
    with duration_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["seed", "duration_seconds"])
        writer.writerows((report["seed"] + i, value) for i, value in enumerate(durations))
    paths = [json_path, text_path, csv_path, duration_path]
    if charts:
        paths.extend(write_charts(report, durations, directory))
    return paths


def write_charts(report, durations, directory):
    # Import only in reporting, never in the combat loop or worker processes.
    os.environ.setdefault("MPLCONFIGDIR", str(directory.resolve() / ".matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    paths = []
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    ax.bar([f["name"] for f in report["fighters"]] + ["Draw"], [f["win_percent"] for f in report["fighters"]] + [report["draw_percent"]])
    ax.set(ylabel="Percent of fights", ylim=(0, 100), title="Matchup outcomes · development estimates")
    path = directory / "win_percentage.png"
    fig.savefig(path, dpi=160); plt.close(fig); paths.append(path)
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    ax.hist(durations, bins=report["duration"]["histogram"]["edges"])
    ax.set(xlabel="Fight duration (seconds)", ylabel="Fights", title="Fight-duration distribution")
    path = directory / "fight_durations.png"
    fig.savefig(path, dpi=160); plt.close(fig); paths.append(path)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for ax, fighter in zip(axes, report["fighters"]):
        entries = fighter["finishers"][:5]
        ax.barh([e["name"] for e in entries], [e["percent_of_wins"] for e in entries])
        ax.set(title=fighter["name"], xlabel="Percent of their wins")
        if not entries:
            ax.text(.5, .5, "No wins", transform=ax.transAxes, ha="center")
    path = directory / "finishing_methods.png"
    fig.savefig(path, dpi=160); plt.close(fig); paths.append(path)
    return paths
