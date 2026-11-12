"""Tables and plots for the beta / iterations experiment (reads results/*.csv).

Run from the repo folder, after run_experiment.py:
    .venv/bin/python person2/experiment/make_plots.py

Writes into person2/experiment/results/:
  tables.md                    all tables (also printed)
  quality_vs_iterations.png    % optimal (small) and % best known (medium) after k iterations
  quality_vs_time.png          % best known vs seconds, medium instances
"""
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
BETAS = [0.0, 0.25, 0.5, 0.75, 1.0]
SMALL_CHECKPOINTS = [1, 5, 10, 20, 50]
MEDIUM_CHECKPOINTS = [1, 5, 10, 20, 50, 100]
TOL = 1e-9

# beta is ordered (0 = greedy ... 1 = random), so one blue hue from light to dark
COLOURS = {0.0: "#86b6ef", 0.25: "#5598e7", 0.5: "#2a78d6", 0.75: "#1c5cab", 1.0: "#0d366b"}
MARKERS = {0.0: "o", 0.25: "s", 0.5: "^", 0.75: "D", 1.0: "v"}


def as_key(f1, f2, f3, f4):
    return (int(f1), int(f2), int(f3), -float(f4))


def same(k1, k2):
    return k1[:3] == k2[:3] and abs(k1[3] - k2[3]) < TOL


def first_worse_goal(k, best):
    """1, 2, 3 or 4: the first goal where plan key k is worse than the best key (0 if equal)."""
    for g in range(3):
        if k[g] != best[g]:
            return g + 1
    return 0 if abs(k[3] - best[3]) < TOL else 4


def load():
    runs = list(csv.DictReader(open(RESULTS / "runs.csv")))
    history = defaultdict(list)                      # (instance, beta, seed) -> [(seconds, iteration, key)]
    for row in csv.DictReader(open(RESULTS / "history.csv")):
        history[(row["instance"], float(row["beta"]), int(row["seed"]))].append(
            (float(row["seconds"]), int(row["iteration"]), as_key(row["f1"], row["f2"], row["f3"], row["f4"])))
    return runs, history


def best_after(events, iteration=None, seconds=None):
    """Best key found within the first `iteration` iterations, or the first `seconds` seconds."""
    found = None
    for s, it, k in events:                          # events are in order, each better than the last
        if (iteration is not None and it <= iteration) or (seconds is not None and s <= seconds):
            found = k
    return found


def main():
    runs, history = load()
    small = [r for r in runs if r["group"] == "small"]
    medium = [r for r in runs if r["group"] == "medium"]
    n_seeds = len({r["seed"] for r in runs})

    # reference key for each instance: Gurobi optimum (small) or best plan of all runs (medium)
    reference = {}
    for r in small:
        reference[r["instance"]] = as_key(r["opt_f1"], r["opt_f2"], r["opt_f3"], r["opt_f4"])
    for r in medium:
        k = history[(r["instance"], float(r["beta"]), int(r["seed"]))][-1][2]
        if r["instance"] not in reference or k < reference[r["instance"]]:
            reference[r["instance"]] = k

    def hit_rate(group_runs, checkpoint=None, seconds=None):
        """% of runs whose best plan equals the reference, per beta."""
        out = {}
        for beta in BETAS:
            sel = [r for r in group_runs if float(r["beta"]) == beta]
            hits = 0
            for r in sel:
                k = best_after(history[(r["instance"], beta, int(r["seed"]))], checkpoint, seconds)
                hits += k is not None and same(k, reference[r["instance"]])
            out[beta] = 100 * hits / len(sel)
        return out

    lines = []

    def table(title, header, rows):
        lines.append(f"### {title}\n")
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "---|" * len(header))
        for row in rows:
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    # 1. quality vs iterations
    n_small, n_medium = len({r["instance"] for r in small}), len({r["instance"] for r in medium})
    small_rates = {k: hit_rate(small, k) for k in SMALL_CHECKPOINTS}
    medium_rates = {k: hit_rate(medium, k) for k in MEDIUM_CHECKPOINTS}
    table(f"Small instances ({n_small} x {n_seeds} seeds): % of runs that reach the optimum",
          ["β"] + [f"{k} it." for k in SMALL_CHECKPOINTS],
          [[f"{b:g}"] + [f"{small_rates[k][b]:.0f}%" for k in SMALL_CHECKPOINTS] for b in BETAS])
    table(f"Medium instances ({n_medium} x {n_seeds} seeds): % of runs that reach the best known plan",
          ["β"] + [f"{k} it." for k in MEDIUM_CHECKPOINTS],
          [[f"{b:g}"] + [f"{medium_rates[k][b]:.0f}%" for k in MEDIUM_CHECKPOINTS] for b in BETAS])

    # 2. where the medium runs lose (after 100 iterations): first goal that is worse than best known
    #    and, for runs equal on goals 1-3, how much coverage (goal 4) they lose, in % of the best known
    rows = []
    for beta in BETAS:
        counts, gaps = [0] * 5, []
        for r in medium:
            if float(r["beta"]) == beta:
                k, best = history[(r["instance"], beta, int(r["seed"]))][-1][2], reference[r["instance"]]
                counts[first_worse_goal(k, best)] += 1
                if k[:3] == best[:3]:
                    gaps.append(100 * (k[3] - best[3]) / -best[3])
        rows.append([f"{beta:g}"] + [str(c) for c in counts]
                    + [f"{sum(gaps) / len(gaps):.2f}%" if gaps else "-", f"{max(gaps):.2f}%" if gaps else "-"])
    table("Medium instances after 100 iterations: first goal where the run is worse than best known (runs), "
          "and goal-4 gap of the runs equal on goals 1-3",
          ["β", "equal to best", "goal 1", "goal 2", "goal 3", "goal 4", "avg goal-4 gap", "max goal-4 gap"], rows)

    # 3. runtime and when the best plan was found
    rows = []
    for beta in BETAS:
        sel = [r for r in medium if float(r["beta"]) == beta]
        runtime = sum(float(r["runtime"]) for r in sel) / len(sel)
        best_it = sum(int(r["best_iteration"]) for r in sel) / len(sel)
        rows.append([f"{beta:g}", f"{runtime:.1f} s", f"{best_it:.0f}"])
    table("Medium instances: average runtime of 100 iterations and iteration where the best plan was found",
          ["β", "runtime", "best found at iteration"], rows)

    rows = []
    for inst in sorted({r["instance"] for r in medium}):
        sel = [r for r in medium if r["instance"] == inst]
        runtime = sum(float(r["runtime"]) for r in sel) / len(sel)
        f1, f2, f3, mf4 = reference[inst]
        rows.append([inst, f"{runtime:.1f} s", f"({f1}, {f2}, {f3}, {-mf4:.4f})"])
    table("Medium instances: average runtime (all β) and best known goals (f1, f2, f3, f4)",
          ["instance", "runtime of 100 it.", "best known goals"], rows)

    text = "\n".join(lines)
    (RESULTS / "tables.md").write_text(text)
    print(text)

    # ---------- plots ----------
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, rates, checkpoints, title in [
            (axes[0], small_rates, SMALL_CHECKPOINTS, f"Small instances: reached the optimum"),
            (axes[1], medium_rates, MEDIUM_CHECKPOINTS, f"Medium instances: reached the best known plan")]:
        for beta in BETAS:
            ax.plot(checkpoints, [rates[k][beta] for k in checkpoints], color=COLOURS[beta],
                    marker=MARKERS[beta], markersize=6, linewidth=2, label=f"β = {beta:g}")
        ax.set_xscale("log")
        ax.set_xticks(checkpoints, [str(k) for k in checkpoints])
        ax.minorticks_off()
        ax.set_xlabel("GRASP iterations")
        ax.set_title(title, fontsize=10)
        ax.grid(axis="y", color="#e5e5e5")
        ax.set_ylim(0, 102)
    axes[0].set_ylabel("% of runs")
    axes[1].legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(RESULTS / "quality_vs_iterations.png", dpi=150)

    times = [0.1 * 1.1 ** i for i in range(80) if 0.1 * 1.1 ** i <= 20]   # every run ends by ~13 s
    fig, ax = plt.subplots(figsize=(6, 4))
    for beta in BETAS:
        rates = [hit_rate(medium, seconds=s)[beta] for s in times]
        ax.plot(times, rates, color=COLOURS[beta], linewidth=2, label=f"β = {beta:g}")
    ax.set_xscale("log")
    ax.set_xlabel("seconds")
    ax.set_ylabel("% of runs at the best known plan")
    ax.set_title("Medium instances: quality vs time", fontsize=10)
    ax.grid(axis="y", color="#e5e5e5")
    ax.set_ylim(0, 102)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(RESULTS / "quality_vs_time.png", dpi=150)
    print(f"\nPlots saved in {RESULTS}")


if __name__ == "__main__":
    main()
