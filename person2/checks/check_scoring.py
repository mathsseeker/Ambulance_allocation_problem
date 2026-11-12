"""Check that scoring.py measures exactly what Gurobi's Model R optimises.

For each small random instance:
  1. brute force: try EVERY valid plan, keep the one with the smallest key
  2. Gurobi: Person 1's solve_robust gives its optimal plan
  3. both must have the same four goal values, and our goals for Gurobi's
     plan must match the values Gurobi itself reports.

Run from the repo folder:   .venv/bin/python person2/checks/check_scoring.py
"""
import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # the person2 folder
from instances import load_map, random_instance                  # noqa: E402
from scoring import is_valid, goals, key                         # noqa: E402
from ambulance.model import solve_robust                         # noqa: E402  (Person 1's Gurobi)


def brute_force_best_key(inst):
    best = None
    for bases in itertools.product(range(inst.nJ), repeat=inst.nI):
        plan = dict(enumerate(bases))
        if is_valid(inst, plan) and (best is None or key(inst, plan) < best):
            best = key(inst, plan)
    return best


def same_key(k1, k2):
    return k1[:3] == k2[:3] and abs(k1[3] - k2[3]) < 1e-9


def check(inst):
    res = solve_robust(inst, time_limit=30)
    plan = res["assignment"]
    f1, f2, f3, f4 = goals(inst, plan)
    reported = (res["n_violated"], res["overtime_minutes"], res["extra_moves"])
    ok = (is_valid(inst, plan)
          and same_key(key(inst, plan), brute_force_best_key(inst))
          and (f1, f2, f3) == reported and abs(f4 - res["regular"]) < 1e-9)
    print(f"  {inst.name:8s} |I|={inst.nI} S={inst.S} T={inst.T:g} M={inst.M}  "
          f"goals={(f1, f2, f3, round(f4, 6))}  {'OK' if ok else 'MISMATCH'}")
    return ok


def main():
    results = []

    print("Madrid (8 bases, 8 areas):")
    region = load_map("madrid")
    for seed in range(40):
        rng = np.random.default_rng(1000 + seed)
        inst = random_instance(region, n_ambulances=int(rng.integers(2, 6)), seed=seed,
                               n_sleeping=int(rng.integers(0, 3)), capacity=int(rng.integers(1, 3)),
                               T=float(rng.choice([5, 8, 10])), M=int(rng.integers(0, 3)),
                               lam=float(rng.choice([0, 1e-4])), shift_max=120)
        results.append(check(inst))

    print("Fez-Meknes case 1 (18 bases, 199 areas; goal 1 is active here):")
    region = load_map("fez", case=1)
    for seed in range(15):
        rng = np.random.default_rng(seed)
        inst = random_instance(region, n_ambulances=int(rng.integers(2, 4)), seed=seed,
                               n_sleeping=int(rng.integers(0, 3)), capacity=1,
                               T=30, M=int(rng.integers(0, 2)), shift_max=200)
        results.append(check(inst))

    print(f"\n{sum(results)} OK, {len(results) - sum(results)} mismatches")


if __name__ == "__main__":
    main()
