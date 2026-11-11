"""Solve one Case-1 instance with all four models (base, H, E, R) and print the results.

    .venv/bin/python scripts/main.py [--n 6] [--seed 0] [--sleeping 0] [--M 2] [--lam 0] [--P 0]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ambulance.data_loader import load_case  # noqa: E402
from ambulance.evaluate import evaluate  # noqa: E402
from ambulance.instance import generate_instance  # noqa: E402
from ambulance.model import solve_elastic, solve_exact, solve_hard, solve_robust  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", type=int, default=1)
    ap.add_argument("--n", type=int, default=6, help="number of free ambulances |I|")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--sleeping", type=int, default=0, help="|S|")
    ap.add_argument("--M", type=int, default=2)
    ap.add_argument("--lam", type=float, default=0.0)
    ap.add_argument("--P", type=float, default=0.0)
    ap.add_argument("--alpha", type=float, default=0.97)
    ap.add_argument("--cv", type=float, default=0.2)
    ap.add_argument("--time-limit", type=float, default=60)
    a = ap.parse_args()

    rd = load_case(a.case)
    inst = generate_instance(a.case, a.n, a.seed, n_sleeping=a.sleeping, M=a.M, lam=a.lam, P=a.P,
                             alpha=a.alpha, cv=a.cv)
    print(f"Instance {inst.name}: |I|={inst.nI} |J|={inst.nJ} |V|={inst.nV} S={[rd.J[j] for j in inst.S]} "
          f"M={inst.M} lam={inst.lam} P={inst.P}")
    print(f"T={inst.T} q={inst.q} | T2=2T={inst.T2} alpha={inst.alpha} (z={inst.z:.3f}) cv={inst.cv} "
          f"| |V2|={len(inst.V2)}, areas outside V2: {inst.n_outside_V2}, forced moves: {inst.forced_moves}")
    print()
    print(f"{'i':>3} {'delta':>6} {'home':>5} {'shift':>6}  allowed bases")
    for i in range(inst.nI):
        print(f"{i:>3} {rd.J[inst.delta[i]]:>6} {rd.J[inst.h[i]]:>5} {int(inst.s[i]):>6}  "
              f"{[rd.J[j] for j in inst.allowed[i]]}")

    for name, solver in (("base", solve_exact), ("hard", solve_hard), ("elastic", solve_elastic),
                         ("robust", solve_robust)):
        r = solver(inst, time_limit=a.time_limit)
        print(f"\n== {name.upper()} == status {r['status']} ({r['runtime']*1000:.1f} ms): {r['message']}")
        if r["assignment"] is None:
            continue
        ev = evaluate(inst, r["assignment"], name)
        print(f"   objective {r['objective']:.6f} | coverage {r['coverage_term']:.6f} | moving cost "
              f"{r['moving_cost_term']:.6f} ({r['moving_minutes']:.0f} min) | moves {r['n_moves']} | gap {r['mip_gap']:.2e}")
        print(f"   evaluate(): objective {ev['objective']:.6f}, feasible {ev['feasible']}, "
              f"2T violations {ev['n_violated_9']}  (match: {abs(ev['objective'] - r['objective']) < 1e-6})")
        moved = {rd.J[inst.delta[i]]: rd.J[j] for i, j in r["assignment"].items() if j != inst.delta[i]}
        print(f"   assignment (ambulance -> base): "
              f"{ {i: rd.J[j] for i, j in sorted(r['assignment'].items())} }")
        if moved:
            print(f"   moves: " + ", ".join(f"amb {i}: base {rd.J[inst.delta[i]]} -> {rd.J[j]}"
                                         for i, j in r["assignment"].items() if j != inst.delta[i]))


if __name__ == "__main__":
    main()
