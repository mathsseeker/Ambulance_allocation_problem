"""Model H vs Model E on a grid of instances (spec section 7, item 7).

    .venv/bin/python scripts/feasibility_experiment.py --small     # quick grid + time estimate
    .venv/bin/python scripts/feasibility_experiment.py             # full grid

Writes one row per (instance, model) to results/feasibility.csv (the section-5 "base"
model is solved too, to measure what the 2T rule costs) and prints summaries.

Fleet sizes |I|: Table 8 sizes (38-342) do not fit C_j = 2 (total capacity 36 / 44 / 80),
so we use ~0.5, 1 and 1.5 ambulances per base, plus 2, 4, 6 (busy moments).
The ambulance state depends only on (case, |I|, |S|, seed), so every (alpha, cv, M)
setting sees the same states.
"""
from __future__ import annotations

import argparse
import itertools
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ambulance.instance import generate_instance  # noqa: E402
from ambulance.model import solve_elastic, solve_exact, solve_hard  # noqa: E402

FLEETS = {1: [2, 4, 6, 9, 18, 27], 2: [2, 4, 6, 11, 22, 33], 3: [2, 4, 6, 20, 40, 60]}
ALPHAS, CVS, SLEEPING = [0.95, 0.97, 0.99], [0.1, 0.2, 0.3], [0, 2]
KEEP = ["status", "infeasible", "objective", "coverage_term", "moving_cost_term", "n_moves",
        "n_violated", "n_outside_V2", "forced_moves", "iis_families", "iis_implied", "runtime",
        "time_limit_hit", "mip_gap", "n_vars", "n_constrs", "message"]


def run_group(args):
    """All (alpha, cv) settings for one ambulance state; returns rows."""
    case, n, ns, M_mode, seed, time_limit = args
    rows = []
    for alpha, cv in itertools.product(ALPHAS, CVS):
        M = 2 if M_mode == "2" else n
        inst = generate_instance(case, n, seed, n_sleeping=ns, M=M, alpha=alpha, cv=cv)
        key = dict(case=case, alpha=alpha, cv=cv, n_ambulances=n, n_sleeping=ns, M_mode=M_mode, M=M,
                   seed=seed, n_V2=len(inst.V2))
        for model, solver in (("base", solve_exact), ("hard", solve_hard), ("elastic", solve_elastic)):
            r = solver(inst, time_limit=time_limit)
            rows.append({**key, "model": model, **{k: r[k] for k in KEEP}})
    return rows


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    h = df[df.model == "hard"].set_index(["case", "alpha", "cv", "n_ambulances", "n_sleeping", "M_mode", "seed"])
    e = df[df.model == "elastic"].set_index(h.index.names)
    b = df[df.model == "base"].set_index(h.index.names)
    j = pd.DataFrame({
        "H_infeasible": h.status.eq("INFEASIBLE"), "E_infeasible": e.status.eq("INFEASIBLE"),
        "base_infeasible": b.status.eq("INFEASIBLE"),
        "n_outside_V2": h.n_outside_V2, "E_violated": e.n_violated,
        "H_runtime_ms": h.runtime * 1000, "E_runtime_ms": e.runtime * 1000,
    }).reset_index()
    g = j.groupby(["case", "alpha", "cv", "n_ambulances"])
    return g.agg(H_infeasible_share=("H_infeasible", "mean"), base_infeasible_share=("base_infeasible", "mean"),
                 avg_outside_V2=("n_outside_V2", "mean"), avg_E_violated=("E_violated", "mean"),
                 avg_H_ms=("H_runtime_ms", "mean"), avg_E_ms=("E_runtime_ms", "mean")).round(3)


def head_to_head(df: pd.DataFrame) -> str:
    idx = ["case", "alpha", "cv", "n_ambulances", "n_sleeping", "M_mode", "seed"]
    p = df.pivot_table(index=idx, columns="model", values=["status", "objective", "coverage_term", "n_violated",
                                                          "runtime"], aggfunc="first")
    st, obj, cov = p["status"], p["objective"], p["coverage_term"]
    n = len(p)
    base_ok = st["base"].eq("OPTIMAL")
    h_ok, e_ok = st["hard"].eq("OPTIMAL"), st["elastic"].eq("OPTIMAL")
    both = h_ok & e_ok
    eq = (obj["hard"][both] - obj["elastic"][both]).abs().max() if both.any() else float("nan")
    lines = [
        f"instances: {n}",
        f"section-5 model feasible:           {base_ok.mean():6.1%}",
        f"Model H returns a plan:             {h_ok.mean():6.1%}",
        f"Model E returns a plan:             {e_ok.mean():6.1%}",
        f"E plan when H has none:             {(e_ok & ~h_ok).sum()} instances",
        f"E fails although section 5 is fine: {(base_ok & ~e_ok).sum()} instances (must be 0)",
        f"both solved: max |obj_H - obj_E| = {eq:.2e}; E violations there = "
        f"{int(p['n_violated']['elastic'][both].fillna(0).sum())} (must be 0)",
        f"coverage cost of the 2T rule (base - E coverage, where both solve): "
        f"mean {(cov['base'] - cov['elastic'])[base_ok & e_ok].mean():.4f}, "
        f"max {(cov['base'] - cov['elastic'])[base_ok & e_ok].max():.4f}",
        f"statuses: " + ", ".join(f"{m}: {dict(st[m].value_counts())}" for m in ("base", "hard", "elastic")),
        f"time-limit hits: {int(df.time_limit_hit.sum())}; slowest solve {df.runtime.max()*1000:.0f} ms",
    ]
    iis = df[(df.model == "hard") & df.iis_families.notna()]
    if len(iis):
        combo = (iis.iis_families + iis.iis_implied.fillna("").map(lambda s: f" [via {s}]" if s else ""))
        lines.append("IIS families of infeasible Model H: " + ", ".join(f"{k}: {v}" for k, v in combo.value_counts().items()))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", action="store_true", help="1 seed, M=2 only: quick timing run")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--time-limit", type=float, default=60)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", default=str(ROOT / "results" / "feasibility.csv"))
    a = ap.parse_args()

    seeds = range(1 if a.small else a.seeds)
    m_modes = ["2"] if a.small else ["2", "I"]   # spec default M = 2, plus M = |I| (no move limit)
    tasks = [(case, n, ns, mm, seed, a.time_limit)
             for case in (1, 2, 3) for n in FLEETS[case] for ns in SLEEPING for mm in m_modes for seed in seeds]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(a.workers) as ex:
        rows = [r for chunk in ex.map(run_group, tasks, chunksize=4) for r in chunk]
    elapsed = time.perf_counter() - t0
    df = pd.DataFrame(rows)
    out = Path(a.out) if not a.small else Path(a.out).with_name("feasibility_small.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)

    n_inst = len(df) // 3
    print(f"{n_inst} instances x 3 models in {elapsed:.1f} s ({a.workers} workers) -> {out.relative_to(ROOT)}")
    if a.small:
        full = n_inst * a.seeds * 2
        print(f"expected full grid ({a.seeds} seeds, M in {{2, |I|}}): {full} instances, "
              f"~{elapsed * a.seeds * 2:.0f} s")
    pd.set_option("display.width", 200, "display.max_rows", 500)
    for mm in m_modes:
        sub = df[df.M_mode == mm]
        print(f"\n===== M = {'2' if mm == '2' else '|I|'} =====")
        print(head_to_head(sub))
        s = summarise(sub)
        s.to_csv(out.with_name(out.stem + f"_summary_M{mm}.csv"))
        print("\nper (case, alpha, cv, |I|):")
        print(s.to_string())


if __name__ == "__main__":
    main()
