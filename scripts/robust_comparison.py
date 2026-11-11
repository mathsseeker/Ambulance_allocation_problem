"""Base vs Model H vs strict Model E vs Model R on the feasibility grid (same grid and seeds,
T = 30, T2 = 2T = 60).

    .venv/bin/python scripts/robust_comparison.py --small   # 1 seed, quick timing run
    .venv/bin/python scripts/robust_comparison.py           # full grid (10 seeds)

Writes results/robust_comparison.csv (one row per instance and model),
results/robust_comparison_summary.csv, and prints the comparison. All metrics are
recomputed with evaluate() so every model is scored the same way. Instances refused by the
size-limited licence are kept with status SIZE_LIMIT and their size (vars, constraints).
"""
from __future__ import annotations

import argparse
import itertools
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ambulance.evaluate import evaluate  # noqa: E402
from ambulance.instance import generate_instance  # noqa: E402
from ambulance.model import solve_elastic, solve_exact, solve_hard, solve_robust  # noqa: E402
from feasibility_experiment import ALPHAS, CVS, FLEETS, SLEEPING  # noqa: E402  same grid

MODELS = (("base", solve_exact), ("hard", solve_hard), ("elastic", solve_elastic), ("robust", solve_robust))
KEY = ["case", "alpha", "cv", "n_ambulances", "n_sleeping", "M_mode", "seed"]


def run_group(args):
    case, n, ns, M_mode, seed, time_limit = args
    rows = []
    for alpha, cv in itertools.product(ALPHAS, CVS):
        M = 2 if M_mode == "2" else n
        inst = generate_instance(case, n, seed, n_sleeping=ns, M=M, alpha=alpha, cv=cv)   # T = 30, T2 = 60
        key = dict(case=case, alpha=alpha, cv=cv, n_ambulances=n, n_sleeping=ns, M_mode=M_mode, M=M, seed=seed,
                   T=inst.T, T2=inst.T2, n_V2=len(inst.V2), outside_V2=inst.n_outside_V2,
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
    out = df.groupby(by + ["model"], sort=False).agg(
        feasible_share=("has_plan", "mean"), guarantee_ok=("guarantee_ok", "mean"),
        outside_V2=("outside_V2", "mean"), coverage=("coverage", "mean"),
        moves=("moves", "mean"), extra_moves=("extra_moves", "mean"),
        overtime_minutes=("overtime_minutes", "mean"),
        overtime_share=("overtime_minutes", lambda s: float((s > 0).mean()) if s.notna().any() else np.nan),
        max_overtime_one=("max_overtime_one", "max"),
        violations=("violations", "mean"),
        runtime_ms_mean=("runtime_ms", "mean"), runtime_ms_max=("runtime_ms", "max"),
        size_limit=("status", lambda s: int((s == "SIZE_LIMIT").sum())),
    )
    return out.round(4)


def e_vs_r(df: pd.DataFrame, key: list[str] = KEY) -> str:
    vals = ["coverage", "violations", "extra_moves", "overtime_minutes", "has_plan"]
    p = df.pivot_table(index=key, columns="model", values=vals, aggfunc="first")
    e_ok, r_ok = p["has_plan"]["elastic"].astype(bool), p["has_plan"]["robust"].astype(bool)
    both = e_ok & r_ok
    lines = [f"R has a plan where strict E has none: {(~e_ok & r_ok).sum()} instances"]
    if both.any():
        dcov = (p["coverage"]["robust"] - p["coverage"]["elastic"])[both]
        fewer = (p["violations"]["robust"] < p["violations"]["elastic"])[both]
        r_ot = (p["overtime_minutes"]["robust"] > p["overtime_minutes"]["elastic"])[both]
        r_ex = (p["extra_moves"]["robust"] > 0)[both]
        lines += [
            f"both feasible: {both.sum()} instances",
            f"coverage R - E: mean {dcov.mean():+.5f}, max |diff| {dcov.abs().max():.5f} "
            f"(min {dcov.min():+.5f}, max {dcov.max():+.5f})",
            f"R has fewer violations: {fewer.sum()} ({fewer.mean():.1%}); of those, using more overtime: "
            f"{(fewer & r_ot).sum()}, using extra moves: {(fewer & r_ex).sum()}, "
            f"using both: {(fewer & r_ot & r_ex).sum()}, using neither: {(fewer & ~r_ot & ~r_ex).sum()}",
            f"R has more violations than E: {(p['violations']['robust'] > p['violations']['elastic'])[both].sum()} "
            f"(must be 0)",
        ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", action="store_true", help="1 seed only (timing run)")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--time-limit", type=float, default=60)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    seeds = range(1 if a.small else a.seeds)

    t0 = time.perf_counter()
    tasks = [(case, n, ns, mm, seed, a.time_limit)
             for case in (1, 2, 3) for n in FLEETS[case] for ns in SLEEPING for mm in ("2", "I") for seed in seeds]
    rows, done = [], 0
    with ProcessPoolExecutor(a.workers) as ex:
        for chunk in ex.map(run_group, tasks, chunksize=2):
            rows += chunk
            done += 1
            if done % max(1, len(tasks) // 20) == 0 or done == len(tasks):
                el = time.perf_counter() - t0
                print(f"  progress {done}/{len(tasks)} groups, {el:.0f} s elapsed, "
                      f"~{el / done * (len(tasks) - done):.0f} s left", flush=True)
    elapsed = time.perf_counter() - t0
    df = pd.DataFrame(rows)
    name = "robust_comparison_small" if a.small else "robust_comparison"
    out = ROOT / "results" / f"{name}.csv"
    df.to_csv(out, index=False)
    print(f"\n{len(df) // len(MODELS)} instances x {len(MODELS)} models in {elapsed:.1f} s -> {out.relative_to(ROOT)}")
    if a.small:
        print(f"expected full grid ({a.seeds} seeds): ~{elapsed * a.seeds:.0f} s")
    print("T =", df["T"].unique(), " T2 =", df["T2"].unique())
    print("statuses:", {m: dict(g.status.value_counts()) for m, g in df.groupby("model")})
    print(f"time-limit hits: {int(df.time_limit_hit.sum())}")

    sl = df[df.status == "SIZE_LIMIT"]
    if len(sl):
        print(f"\nSIZE_LIMIT (skipped, not shrunk): {len(sl)} solves")
        print(sl.groupby(["model", "case", "n_ambulances", "n_sleeping"]).agg(
            solves=("status", "size"), vars_min=("n_vars", "min"), vars_max=("n_vars", "max"),
            constrs_min=("n_constrs", "min"), constrs_max=("n_constrs", "max")).to_string())

    rob = df[df.model == "robust"]
    rg = rob[rob.guarantee_ok & (rob.status != "SIZE_LIMIT")]
    print(f"\ncapacity guarantee holds on {rob.guarantee_ok.mean():.1%} of instances "
          f"({(~rob.guarantee_ok).sum()} fail it, counted separately)")
    print(f"Model R feasible on {rg.has_plan.mean():.1%} of guaranteed instances that fit the licence ({len(rg)}); "
          f"hard rules ok: {bool(rg.hard_rules_ok.all())}; o == extra moves: {bool((rg.o_var == rg.extra_moves).all())}")

    pd.set_option("display.width", 250, "display.max_rows", 3000, "display.max_columns", 30)
    parts = []
    for mm, label in (("2", "M = 2"), ("I", "M = |I|")):
        sub = df[df.M_mode == mm]
        print(f"\n================ {label} ================")
        print(summary(sub.assign(overall="all"), ["overall"]).to_string())
        print("\nstrict E vs Model R:\n" + e_vs_r(sub))
        per = summary(sub, ["case", "alpha", "cv", "n_ambulances"])
        print("\nper (case, alpha, cv, |I|):")
        print(per.to_string())
        parts.append(per.assign(M_mode=mm))
    pd.concat(parts).to_csv(ROOT / "results" / f"{name}_summary.csv")


if __name__ == "__main__":
    main()
