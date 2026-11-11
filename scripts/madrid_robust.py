"""Base vs Model H vs strict Model E vs Model R on the Madrid instance
(Fuencarral - El Pardo + neighbouring SAMUR-PC bases, data/madrid/processed).

    .venv/bin/python scripts/madrid_robust.py --small   # 1 seed
    .venv/bin/python scripts/madrid_robust.py           # 10 seeds

Grid: T in {10, 15, 20, 30} (T2 = 2T), alpha x cv as in the Fez-Meknes grid, |I| in FLEETS,
|S| in {0, 2}, M in {2, |I|}, capacity in {estimated C_j = 5, project default 2}.
Writes results/madrid_robust.csv, results/madrid_robust_summary.csv and
results/madrid_robust_report.txt. All metrics are recomputed with evaluate().
"""
from __future__ import annotations

import argparse
import io
import itertools
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ambulance.evaluate import evaluate  # noqa: E402
from ambulance.madrid import generate_madrid_instance, load_madrid  # noqa: E402
from ambulance.model import solve_elastic, solve_exact, solve_hard, solve_robust  # noqa: E402
from feasibility_experiment import ALPHAS, CVS, SLEEPING  # noqa: E402  same alpha/cv/|S| grid
from robust_comparison import e_vs_r  # noqa: E402

MODELS = (("base", solve_exact), ("hard", solve_hard), ("elastic", solve_elastic), ("robust", solve_robust))
TS = (10, 15, 20, 30)
FLEETS = (2, 4, 6, 8, 12, 16)          # 8 bases: 0.25 .. 2 ambulances per base
CAPACITIES = (None, 2)                  # None = estimated C_j column (5), 2 = project default
KEY = ["T", "capacity", "alpha", "cv", "n_ambulances", "n_sleeping", "M_mode", "seed"]


def run_group(args):
    n, ns, M_mode, seed, cap, time_limit = args
    rows = []
    for T, alpha, cv in itertools.product(TS, ALPHAS, CVS):
        M = 2 if M_mode == "2" else n
        inst = generate_madrid_instance(n, seed, n_sleeping=ns, capacity=cap, M=M, T=T, alpha=alpha, cv=cv)
        key = dict(T=T, T2=inst.T2, capacity="est5" if cap is None else str(cap), alpha=alpha, cv=cv,
                   n_ambulances=n, n_sleeping=ns, M_mode=M_mode, M=M, seed=seed,
                   n_V2=len(inst.V2), outside_V2=inst.n_outside_V2, forced_moves=inst.forced_moves,
                   guarantee_ok=inst.robust_guaranteed_feasible())
        for model, solver in MODELS:
            r = solver(inst, time_limit=time_limit)
            row = {**key, "model": model, "status": r["status"], "has_plan": r["assignment"] is not None,
                   "runtime_ms": r["runtime"] * 1000, "time_limit_hit": r["time_limit_hit"],
                   "n_vars": r["n_vars"], "n_constrs": r["n_constrs"], "o_var": r["o_var"],
                   "iis_families": r["iis_families"], "message": r["message"]}
            if r["assignment"] is not None:
                ev = evaluate(inst, r["assignment"], model)
                row.update(coverage=ev["coverage_term"], regular=ev["regular"], moves=ev["n_moves"],
                           extra_moves=ev["extra_moves"], overtime_minutes=ev["overtime_minutes"],
                           max_overtime_one=int(max(inst.ot[i, j] for i, j in r["assignment"].items())),
                           violations=ev["n_violated_9"], hard_rules_ok=ev["feasible"])
            rows.append(row)
    return rows


def summary(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    return df.groupby(by + ["model"], sort=False).agg(
        instances=("has_plan", "size"), plan_share=("has_plan", "mean"),
        guarantee_ok=("guarantee_ok", "mean"), outside_V2=("outside_V2", "mean"),
        coverage=("coverage", "mean"), moves=("moves", "mean"), extra_moves=("extra_moves", "mean"),
        overtime_minutes=("overtime_minutes", "mean"),
        overtime_share=("overtime_minutes", lambda s: float((s > 0).mean()) if s.notna().any() else np.nan),
        max_overtime_one=("max_overtime_one", "max"), violations=("violations", "mean"),
        runtime_ms_mean=("runtime_ms", "mean"), runtime_ms_max=("runtime_ms", "max"),
        size_limit=("status", lambda s: int((s == "SIZE_LIMIT").sum())),
    ).round(4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--time-limit", type=float, default=60)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    seeds = range(1 if a.small else a.seeds)
    md = load_madrid()

    t0 = time.perf_counter()
    tasks = [(n, ns, mm, seed, cap, a.time_limit)
             for n in FLEETS for ns in SLEEPING for mm in ("2", "I") for seed in seeds for cap in CAPACITIES]
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        for chunk in ex.map(run_group, tasks, chunksize=4):
            rows += chunk
    elapsed = time.perf_counter() - t0
    df = pd.DataFrame(rows)
    name = "madrid_robust_small" if a.small else "madrid_robust"
    df.to_csv(ROOT / "results" / f"{name}.csv", index=False)

    buf = io.StringIO()
    with redirect_stdout(buf):
        pd.set_option("display.width", 250, "display.max_rows", 3000, "display.max_columns", 30)
        print(f"Madrid: {md.district}, |V| = {len(md.V)}, |J| = {len(md.J)}, estimated C_j = {sorted(set(md.C))}")
        print(f"{len(df) // len(MODELS)} instances x {len(MODELS)} models in {elapsed:.1f} s")
        print("statuses:", {m: dict(g.status.value_counts()) for m, g in df.groupby("model")})
        print(f"time-limit hits: {int(df.time_limit_hit.sum())}, size-limit: {int((df.status == 'SIZE_LIMIT').sum())}, "
              f"max vars {int(df.n_vars.max())}, max constraints {int(df.n_constrs.max())}")
        rob = df[df.model == "robust"]
        rg = rob[rob.guarantee_ok]
        print(f"capacity guarantee holds on {rob.guarantee_ok.mean():.1%} of instances; "
              f"Model R has a plan on {rg.has_plan.mean():.1%} of those; hard rules ok: {bool(rg.hard_rules_ok.all())}; "
              f"o == extra moves: {bool((rg.o_var == rg.extra_moves).all())}; "
              f"Model R plan when guarantee fails: {int(rob[~rob.guarantee_ok].has_plan.sum())} (must be 0)")
        print(f"areas outside V2 (no base within 2T with prob. alpha), mean per T: "
              f"{rob.groupby('T').outside_V2.mean().round(2).to_dict()}")
        parts = []
        for mm, label in (("2", "M = 2"), ("I", "M = |I|")):
            sub = df[df.M_mode == mm]
            print(f"\n================ {label} ================")
            print(summary(sub, ["T"]).to_string())
            print("\nstrict E vs Model R:\n" + e_vs_r(sub, KEY))
            per = summary(sub, ["T", "capacity", "n_ambulances"])
            parts.append(per.assign(M_mode=mm))
        print("\n================ by capacity (all T, M) ================")
        print(summary(df, ["capacity"]).to_string())
    txt = buf.getvalue()
    print(txt)
    (ROOT / "results" / f"{name}_report.txt").write_text(txt)
    pd.concat(parts).to_csv(ROOT / "results" / f"{name}_summary.csv")


if __name__ == "__main__":
    main()
