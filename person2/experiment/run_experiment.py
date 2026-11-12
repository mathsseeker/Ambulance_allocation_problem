"""Experiment: effect of beta and of the number of iterations on GRASP.

For every instance, every beta in BETAS and every seed in SEEDS, run GRASP once
for MAX_ITERATIONS iterations and save its improvement history. The history says
when (iteration, seconds) the best plan improved, so the best plan after 1, 5,
10, ... iterations, or after any number of seconds, can be read from this one run
(GRASP with fewer iterations and the same seed does exactly the first iterations).

Two groups of instances:
  small   55 instances (40 Madrid, 15 Fez-Meknes case 1), optimum known from Gurobi
  medium   8 instances (Fez-Meknes case 1 and 2, Edmonton), optimum unknown:
          compared with the best plan found by any run ("best known")

Output (person2/experiment/results/):
  runs.csv      one row per run: group, instance, beta, seed, runtime, iterations,
                best_iteration, and for small instances the optimal goals
  history.csv   one row per improvement: instance, beta, seed, seconds, iteration, f1..f4

Run from the repo folder (about 30 minutes):
    .venv/bin/python person2/experiment/run_experiment.py
Then:
    .venv/bin/python person2/experiment/make_plots.py
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))                              # the person2 folder
sys.path.insert(0, str(HERE.parent / "checks"))
from instances import load_map, random_instance                  # noqa: E402
from scoring import goals                                        # noqa: E402
from grasp import grasp                                          # noqa: E402
from check_construction import small_instances                   # noqa: E402
from ambulance.model import solve_robust                         # noqa: E402  (Person 1's Gurobi)

BETAS = [0.0, 0.25, 0.5, 0.75, 1.0]
SEEDS = range(5)
SMALL_ITERATIONS = 50
MEDIUM_ITERATIONS = 100
RESULTS = HERE / "results"


def medium_instances():
    """8 medium instances: 3 situations on Fez case 1, 2 on Fez case 2, 3 on Edmonton."""
    setups = [("fez", 1, 18, 2, 30.0)] * 3 + [("fez", 2, 22, 2, 30.0)] * 2 + [("edmonton", 1, 20, None, 10.0)] * 3
    counter = {}
    for region, case, n_amb, capacity, T in setups:
        situation = counter.get((region, case), 0)
        counter[(region, case)] = situation + 1
        inst = random_instance(load_map(region, case), n_amb, situation, n_sleeping=2, capacity=capacity, T=T)
        inst.name = f"{region}{case}_s{situation}" if region == "fez" else f"edmonton_s{situation}"
        yield inst


def main():
    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / "runs.csv", "w", newline="") as f_runs, open(RESULTS / "history.csv", "w", newline="") as f_hist:
        runs, hist = csv.writer(f_runs), csv.writer(f_hist)
        runs.writerow(["group", "instance", "beta", "seed", "runtime", "iterations", "best_iteration",
                       "opt_f1", "opt_f2", "opt_f3", "opt_f4"])
        hist.writerow(["instance", "beta", "seed", "seconds", "iteration", "f1", "f2", "f3", "f4"])

        groups = [("small", list(small_instances()), SMALL_ITERATIONS),
                  ("medium", list(medium_instances()), MEDIUM_ITERATIONS)]
        for group, insts, iterations in groups:
            for n, inst in enumerate(insts, 1):
                optimum = ["", "", "", ""]
                if group == "small":
                    optimum = list(goals(inst, solve_robust(inst, time_limit=30)["assignment"]))
                for beta in BETAS:
                    for seed in SEEDS:
                        r = grasp(inst, beta=beta, iterations=iterations, seed=seed)
                        runs.writerow([group, inst.name, beta, seed, round(r["runtime"], 4), r["iterations"],
                                       r["best_iteration"], *optimum])
                        for seconds, it, g in r["history"]:
                            hist.writerow([inst.name, beta, seed, round(seconds, 4), it, *g])
                f_runs.flush()
                f_hist.flush()
                print(f"{group} {n}/{len(insts)} {inst.name} done", flush=True)


if __name__ == "__main__":
    main()
