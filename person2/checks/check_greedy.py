"""Check the greedy construction.

1. Small instances: greedy's plan is valid, and how close is it to Gurobi's optimum?
2. Medium instances: greedy's plan is valid, and how long does it take?

Run from the repo folder:   .venv/bin/python person2/checks/check_greedy.py
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # the person2 folder
from instances import load_map, random_instance                  # noqa: E402
from scoring import is_valid, key                                # noqa: E402
from greedy import greedy                                        # noqa: E402
from ambulance.model import solve_robust                         # noqa: E402  (Person 1's Gurobi)


def first_worse_goal(k_heur, k_opt):
    """Which goal greedy loses on first (None if it is optimal)."""
    for g in range(3):
        if k_heur[g] != k_opt[g]:
            return f"f{g + 1}: {k_heur[g]} vs {k_opt[g]}"
    if abs(k_heur[3] - k_opt[3]) > 1e-9:
        return f"f4: {-k_heur[3]:.6f} vs {-k_opt[3]:.6f}"
    return None


def small_instances():
    yield from (("madrid", s) for s in range(40))
    yield from (("fez", s) for s in range(15))


def main():
    print("1. Small instances: greedy vs Gurobi optimum")
    maps = {"madrid": load_map("madrid"), "fez": load_map("fez", case=1)}
    n_valid = n_opt = n = 0
    for name, seed in small_instances():
        rng = np.random.default_rng(seed)
        if name == "madrid":
            inst = random_instance(maps[name], int(rng.integers(2, 7)), seed, n_sleeping=int(rng.integers(0, 3)),
                                   capacity=int(rng.integers(1, 3)), T=float(rng.choice([5, 8, 10])),
                                   M=int(rng.integers(0, 3)), shift_max=120)
        else:
            inst = random_instance(maps[name], int(rng.integers(2, 5)), seed, n_sleeping=int(rng.integers(0, 3)),
                                   capacity=1, T=30, M=int(rng.integers(0, 2)), shift_max=200)
        plan = greedy(inst)
        opt = solve_robust(inst, time_limit=30)
        if opt["assignment"] is None:
            print(f"  {name} seed {seed}: Gurobi gave no plan ({opt['status']}), skipped")
            continue
        n += 1
        n_valid += is_valid(inst, plan)
        lost = first_worse_goal(key(inst, plan), key(inst, opt["assignment"]))
        n_opt += lost is None
        if lost:
            print(f"  {name:6s} seed {seed:2d} |I|={inst.nI}: greedy worse on {lost}")
    print(f"  valid: {n_valid}/{n}   optimal: {n_opt}/{n}")

    print("\n2. Medium instances: validity and runtime")
    for name, case, nI, cap in [("fez", 1, 18, 2), ("fez", 2, 22, 2), ("fez", 3, 33, 2), ("edmonton", 1, 20, None)]:
        region = load_map(name, case)
        for seed in range(3):
            inst = random_instance(region, nI, seed, n_sleeping=2, capacity=cap, T=30 if name == "fez" else 10)
            t0 = time.perf_counter()
            plan = greedy(inst)
            secs = time.perf_counter() - t0
            print(f"  {name} case {case} |J|={inst.nJ} |I|={nI} seed {seed}: valid={is_valid(inst, plan)}  "
                  f"key={tuple(round(x, 4) for x in key(inst, plan))}  {secs:.2f}s")


if __name__ == "__main__":
    main()
