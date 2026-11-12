"""Check the local search.

1. Correctness, on every small instance and for random and greedy starting plans:
   the result is valid, never worse than the start, and a true local optimum
   (no single move or swap improves it).
2. Quality: greedy + local search vs Gurobi's optimum, first vs best improvement.
3. Preview of GRASP: best of 20 (construction + local search) for each beta.
4. Medium instances: runtime of greedy + local search.

Run from the repo folder:   .venv/bin/python person2/checks/check_local_search.py
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # the person2 folder
from instances import load_map, random_instance                  # noqa: E402
from scoring import is_valid, key                                # noqa: E402
from construction import construct, greedy                       # noqa: E402
from local_search import local_search, neighbours                # noqa: E402
from check_construction import small_instances, same_key         # noqa: E402
from ambulance.model import solve_robust                         # noqa: E402  (Person 1's Gurobi)

BETAS = [0.0, 0.25, 0.5, 0.75, 1.0]
RUNS = 20


def is_local_optimum(inst, plan):
    k = key(inst, plan)
    return all(not key(inst, nb) < k for nb in neighbours(inst, plan))


def main():
    insts = list(small_instances())
    optimum = {inst.name: key(inst, solve_robust(inst, time_limit=30)["assignment"]) for inst in insts}

    print("1. Correctness (greedy start + 5 random starts, both modes)")
    n_checked = n_ok = 0
    for inst in insts:
        rng = np.random.default_rng(7)
        starts = [greedy(inst)] + [construct(inst, 1.0, rng) for _ in range(5)]
        for start in starts:
            for mode in ("first", "best"):
                result = local_search(inst, start, mode)
                ok = is_valid(inst, result) and not key(inst, start) < key(inst, result) \
                    and is_local_optimum(inst, result)
                n_checked += 1
                n_ok += ok
    print(f"  valid, never worse, local optimum: {n_ok}/{n_checked}")

    print("\n2. Greedy + local search vs Gurobi optimum")
    for mode in ("first", "best"):
        t0 = time.perf_counter()
        n_opt = sum(same_key(key(inst, local_search(inst, greedy(inst), mode)), optimum[inst.name])
                    for inst in insts)
        print(f"  {mode:5s} improvement: optimal {n_opt}/{len(insts)}   ({time.perf_counter() - t0:.1f}s total)")

    print(f"\n3. Preview of GRASP: best of {RUNS} x (construction + first-improvement local search)")
    print("  beta  | best of runs optimal")
    for beta in BETAS:
        n_opt = 0
        for inst in insts:
            rng = np.random.default_rng(42)
            best = min(key(inst, local_search(inst, construct(inst, beta, rng))) for _ in range(RUNS))
            n_opt += same_key(best, optimum[inst.name])
        print(f"  {beta:4.2f}  | {n_opt}/{len(insts)}")

    print("\n4. Medium instances: greedy + local search")
    for name, case, nI, cap in [("fez", 1, 18, 2), ("fez", 2, 22, 2), ("fez", 3, 33, 2), ("edmonton", 1, 20, None)]:
        inst = random_instance(load_map(name, case), nI, 0, n_sleeping=2, capacity=cap,
                               T=30 if name == "fez" else 10)
        start = greedy(inst)
        for mode in ("first", "best"):
            t0 = time.perf_counter()
            result = local_search(inst, start, mode)
            print(f"  {name} case {case} |I|={nI} {mode:5s}: valid={is_valid(inst, result)}  "
                  f"greedy={tuple(round(x, 4) for x in key(inst, start))}  "
                  f"after={tuple(round(x, 4) for x in key(inst, result))}  {time.perf_counter() - t0:.2f}s")


if __name__ == "__main__":
    main()
