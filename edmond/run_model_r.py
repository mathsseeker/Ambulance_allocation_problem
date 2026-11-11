"""Solve Model R on Edmonton.

    .venv/bin/python edmond/run_model_r.py demo  [--n 8] [--seed 0] [--sleeping 2] [--T 8]
    .venv/bin/python edmond/run_model_r.py grid  -> edmond/results/grid.csv, summary.csv, report.txt

Every Gurobi solution is re-scored with ambulance.evaluate.evaluate (no Gurobi) and the
two must agree; disagreements are counted in the report.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from edmonton import edmonton_instance, load_edmonton  # noqa: E402
from ambulance.evaluate import evaluate  # noqa: E402
from ambulance.model import solve_robust  # noqa: E402

RESULTS = HERE / "results"

GRID = dict(T=[8, 10, 30], n=[4, 8, 12, 16], sleeping=[0, 2], seed=range(10), sigma_mode=["cv", "empirical"])
FIXED = dict(q=0.3, alpha=0.97, M=2, lam=0.0, P=0.0)


def stay_plan(inst):
    """Status quo: every ambulance stays at delta_i. None if that breaks (3) or (6)."""
    plan = {i: int(inst.delta[i]) for i in range(inst.nI)}
    ev = evaluate(inst, plan, "robust")
    return ev if ev["feasible"] else None


def solve_one(inst, time_limit=60):
    r = solve_robust(inst, time_limit=time_limit)
    row = dict(name=inst.name, **inst.meta, q=inst.q, alpha=inst.alpha, z=round(inst.z, 4), cv=inst.cv,
               M=inst.M, T2=inst.T2, V2=len(inst.V2), outside_V2=inst.n_outside_V2,
               mean_a_per_area=float(inst.a.sum(axis=0).mean()), mean_b_per_area=float(inst.b.sum(axis=0).mean()),
               status=r["status"], runtime_ms=round(r["runtime"] * 1000, 2),
               n_vars=r.get("n_vars"), n_constrs=r.get("n_constrs"), message=r["message"])
    if r.get("assignment") is not None:
        ev = evaluate(inst, r["assignment"], "robust")
        row.update(f1_violations=r["n_violated"], f2_overtime_min=r["overtime_minutes"],
                   f3_extra_moves=r["extra_moves"], f4_coverage=r["coverage_term"], moves=r["n_moves"],
                   moving_min=round(r["moving_minutes"], 3),
                   eval_feasible=ev["feasible"],
                   eval_match=abs(ev["regular"] - r["regular"]) < 1e-9 and ev["n_violated_9"] == r["n_violated"]
                   and ev["overtime_minutes"] == r["overtime_minutes"])
    st = stay_plan(inst)
    row.update(stay_feasible=st is not None,
               stay_violations=st["n_violated_9"] if st else None,
               stay_overtime_min=st["overtime_minutes"] if st else None,
               stay_coverage=st["coverage_term"] if st else None)
    return row, r


def demo(a):
    inst = edmonton_instance(a.n, a.seed, n_sleeping=a.sleeping, T=a.T, sigma_mode=a.sigma_mode, **FIXED)
    print(f"{inst.name}: |I|={inst.nI} |J|={inst.nJ} |V|={inst.nV} S={[j + 1 for j in inst.S]} C={inst.C.tolist()}")
    print(f"T={inst.T} 2T={inst.T2} q={inst.q} alpha={inst.alpha} z={inst.z:.3f} cv={inst.cv} M={inst.M} "
          f"| |V2|={len(inst.V2)} outside V2={inst.n_outside_V2} | feasibility condition: {inst.robust_guaranteed_feasible()}")
    print(f"{'i':>3} {'delta':>6} {'home':>5} {'shift':>6}")
    for i in range(inst.nI):
        print(f"{i:>3} {inst.delta[i] + 1:>6} {inst.h[i] + 1:>5} {int(inst.s[i]):>6}")
    row, r = solve_one(inst)
    print(f"\nstatus {r['status']} ({row['runtime_ms']} ms, {row['n_vars']} vars, {row['n_constrs']} constrs): {r['message']}")
    if r.get("assignment"):
        print("moves: " + (", ".join(f"amb {i}: {inst.delta[i] + 1} -> {j + 1}" for i, j in sorted(r["assignment"].items())
                                    if j != inst.delta[i]) or "none"))
        print(f"evaluate() agrees: {row['eval_match']}, feasible: {row['eval_feasible']}")
    if row["stay_feasible"]:
        print(f"status quo (nobody moves): {row['stay_violations']} violations, {row['stay_overtime_min']} min overtime, "
              f"coverage {row['stay_coverage']:.6f}")
    else:
        print("status quo (nobody moves) is infeasible (an ambulance sits at a sleeping base or a base is over capacity)")


def grid(a):
    RESULTS.mkdir(exist_ok=True)
    rows, t0 = [], time.perf_counter()
    for T, n, sl, seed, sm in itertools.product(*GRID.values()):
        inst = edmonton_instance(n, seed, n_sleeping=sl, T=T, sigma_mode=sm, **FIXED)
        rows.append(solve_one(inst, time_limit=a.time_limit)[0])
    wall = time.perf_counter() - t0
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(RESULTS / "grid.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)

    groups = defaultdict(list)
    for r in rows:
        groups[(r["T"], r["sigma_mode"], r["n_ambulances"], r["n_sleeping"])].append(r)
    summ = []
    for (T, sm, n, sl), g in sorted(groups.items()):
        ok = [r for r in g if r["status"] == "OPTIMAL"]
        sq = [r for r in ok if r["stay_feasible"]]
        mean = lambda xs: float(np.mean(xs)) if xs else None  # noqa: E731
        summ.append(dict(
            T=T, sigma_mode=sm, n_ambulances=n, n_sleeping=sl, instances=len(g), optimal=len(ok),
            statuses="/".join(sorted({r["status"] for r in g})),
            V2=g[0]["V2"], mean_a=round(g[0]["mean_a_per_area"], 2), mean_b=round(g[0]["mean_b_per_area"], 2),
            f1_violations=mean([r["f1_violations"] for r in ok]), f2_overtime=mean([r["f2_overtime_min"] for r in ok]),
            f3_extra=mean([r["f3_extra_moves"] for r in ok]), f4_coverage=mean([r["f4_coverage"] for r in ok]),
            moves=mean([r["moves"] for r in ok]), runtime_ms=mean([r["runtime_ms"] for r in ok]),
            max_runtime_ms=max((r["runtime_ms"] for r in ok), default=None),
            n_vars_max=max((r["n_vars"] or 0 for r in g), default=None),
            stay_feasible=len(sq),
            stay_violations=mean([r["stay_violations"] for r in sq]),
            stay_coverage=mean([r["stay_coverage"] for r in sq]),
            R_violations_same=mean([r["f1_violations"] for r in sq]),
            R_coverage_same=mean([r["f4_coverage"] for r in sq]),
            eval_mismatch=sum(1 for r in ok if not r["eval_match"])))
    with open(RESULTS / "summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0])); w.writeheader(); w.writerows(summ)

    fmt = lambda x, p=3: "-" if x is None else f"{x:.{p}f}"  # noqa: E731
    lines = [f"Model R on Edmonton: {len(rows)} instances in {wall:.1f} s. Fixed: {FIXED}, cv={load_edmonton().cv}.",
             f"Statuses: { {s: sum(r['status'] == s for r in rows) for s in sorted({r['status'] for r in rows})} }",
             f"evaluate() mismatches: {sum(s['eval_mismatch'] for s in summ)}", "",
             "T  sigma      |I| |S| opt/n  |V2| a/area b/area  f1 viol  f2 OT  f3 extra  f4 cov   moves  ms(mean/max)  "
             "| status quo: feasible, viol, cov  vs R on same: viol, cov"]
    for s in summ:
        lines.append(f"{s['T']:<2} {s['sigma_mode']:<10} {s['n_ambulances']:>3} {s['n_sleeping']:>3} "
                     f"{s['optimal']:>2}/{s['instances']:<2} {s['V2']:>4} {s['mean_a']:>6} {s['mean_b']:>6} "
                     f"{fmt(s['f1_violations'], 1):>8} {fmt(s['f2_overtime'], 1):>6} {fmt(s['f3_extra'], 1):>8} "
                     f"{fmt(s['f4_coverage'], 4):>7} {fmt(s['moves'], 1):>6} {fmt(s['runtime_ms'], 1):>6}/{fmt(s['max_runtime_ms'], 0):<6} "
                     f"| {s['stay_feasible']:>2}, {fmt(s['stay_violations'], 1):>5}, {fmt(s['stay_coverage'], 4)}"
                     f"  vs {fmt(s['R_violations_same'], 1):>5}, {fmt(s['R_coverage_same'], 4)}")
    (RESULTS / "report.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["demo", "grid"])
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--sleeping", type=int, default=2)
    ap.add_argument("--T", type=float, default=8)
    ap.add_argument("--sigma-mode", default="cv", choices=["cv", "empirical"])
    ap.add_argument("--time-limit", type=float, default=60)
    a = ap.parse_args()
    demo(a) if a.mode == "demo" else grid(a)
