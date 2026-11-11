"""Experiment: Model R with overtime ranked FIRST (before 2T violations) vs the fixed Model R.

    .venv/bin/python scripts/priority_experiment.py

Same grid, seeds and settings as robust_comparison.py (T = 30, T2 = 60). Needs
results/robust_comparison.csv for the fixed Model R. Writes results/priority_experiment.csv.
"""
from __future__ import annotations

import itertools
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ambulance.evaluate import evaluate  # noqa: E402
from ambulance.instance import generate_instance  # noqa: E402
from ambulance.model import solve_robust_overtime_first  # noqa: E402
from feasibility_experiment import ALPHAS, CVS, FLEETS, SLEEPING  # noqa: E402

KEY = ["case", "alpha", "cv", "n_ambulances", "n_sleeping", "M_mode", "seed"]


def run_group(args):
    case, n, ns, M_mode, seed = args
    rows = []
    for alpha, cv in itertools.product(ALPHAS, CVS):
        M = 2 if M_mode == "2" else n
        inst = generate_instance(case, n, seed, n_sleeping=ns, M=M, alpha=alpha, cv=cv)
        r = solve_robust_overtime_first(inst)
        row = dict(case=case, alpha=alpha, cv=cv, n_ambulances=n, n_sleeping=ns, M_mode=M_mode, M=M, seed=seed,
                   model="robust_ot_first", status=r["status"], has_plan=r["assignment"] is not None,
                   runtime_ms=r["runtime"] * 1000, n_vars=r["n_vars"], outside_V2=inst.n_outside_V2)
        if r["assignment"] is not None:
            ev = evaluate(inst, r["assignment"], "robust")
            row.update(coverage=ev["coverage_term"], moves=ev["n_moves"], extra_moves=ev["extra_moves"],
                       overtime_minutes=ev["overtime_minutes"], violations=ev["n_violated_9"],
                       max_overtime_one=int(max(inst.ot[i, j] for i, j in r["assignment"].items())),
                       hard_rules_ok=ev["feasible"])
        rows.append(row)
    return rows


def main():
    t0 = time.perf_counter()
    tasks = [(c, n, ns, mm, s) for c in (1, 2, 3) for n in FLEETS[c] for ns in SLEEPING for mm in ("2", "I")
             for s in range(10)]
    with ProcessPoolExecutor(max(1, (os.cpu_count() or 2) - 1)) as ex:
        rows = [r for chunk in ex.map(run_group, tasks, chunksize=2) for r in chunk]
    new = pd.DataFrame(rows)
    new.to_csv(ROOT / "results" / "priority_experiment.csv", index=False)
    print(f"{len(new)} solves in {time.perf_counter() - t0:.1f} s; statuses {dict(new.status.value_counts())}")

    old = pd.read_csv(ROOT / "results" / "robust_comparison.csv")
    old = old[old.model.isin(["elastic", "robust"])]
    both = pd.concat([old, new], ignore_index=True)
    bad = both[both.status == "SIZE_LIMIT"].set_index(KEY).index.unique()
    fit = both[~both.set_index(KEY).index.isin(bad)]
    print(f"instances where all compared models fit the licence: {len(fit[fit.model == 'robust'])}")
    for mm in ("2", "I"):
        s = fit[fit.M_mode == mm].groupby("model", sort=False).agg(
            plan=("has_plan", "mean"), coverage=("coverage", "mean"), violations=("violations", "mean"),
            overtime=("overtime_minutes", "mean"), ot_any=("overtime_minutes", lambda x: (x > 0).mean()),
            ot_over_60=("max_overtime_one", lambda x: (x > 60).mean()), worst_ot=("max_overtime_one", "max"),
            moves=("moves", "mean"), extra=("extra_moves", "mean"), ms=("runtime_ms", "mean")).round(3)
        print(f"\nM = {'2' if mm == '2' else '|I|'}\n{s.to_string()}")
    r = fit[fit.model == "robust_ot_first"]
    print(f"\novertime-first: hard rules ok on all plans: {bool(r.hard_rules_ok.all())}")


if __name__ == "__main__":
    main()
