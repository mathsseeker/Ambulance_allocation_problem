"""Check the construction phase (greedy and randomized with the RCL).

1. Small instances: greedy vs Gurobi's optimum.
2. Randomness: for each beta, are plans always valid, how many different plans
   do 20 runs give, and does the best of 20 runs reach the optimum more often?
3. Medium instances: validity and runtime of one construction.

Run from the repo folder:   .venv/bin/python person2/checks/check_construction.py
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # the person2 folder
from instances import load_map, random_instance                  # noqa: E402
from scoring import is_valid, key                                # noqa: E402
from construction import construct, greedy                       # noqa: E402
from ambulance.model import solve_robust                         # noqa: E402  (Person 1's Gurobi)

BETAS = [0.0, 0.25, 0.5, 0.75, 1.0]
RUNS = 20


def same_key(k1, k2):
    return k1[:3] == k2[:3] and abs(k1[3] - k2[3]) < 1e-9


def small_instances():
    """55 small instances (40 Madrid, 15 Fez-Meknes case 1) with their Gurobi optimum key."""
    madrid, fez = load_map("madrid"), load_map("fez", case=1)
    for seed in range(40):
        rng = np.random.default_rng(seed)
        inst = random_instance(madrid, int(rng.integers(2, 7)), seed, n_sleeping=int(rng.integers(0, 3)),
                               capacity=int(rng.integers(1, 3)), T=float(rng.choice([5, 8, 10])),
                               M=int(rng.integers(0, 3)), shift_max=120)
        inst.name = f"madrid{seed}"
        yield inst
    for seed in range(15):
        rng = np.random.default_rng(seed)
        inst = random_instance(fez, int(rng.integers(2, 5)), seed, n_sleeping=int(rng.integers(0, 3)),
                               capacity=1, T=30, M=int(rng.integers(0, 2)), shift_max=200)
        inst.name = f"fez{seed}"
        yield inst


def main():
    insts = list(small_instances())
    optimum = {inst.name: key(inst, solve_robust(inst, time_limit=30)["assignment"]) for inst in insts}

    print("1. Greedy (beta = 0) vs Gurobi optimum")
    n_opt = sum(same_key(key(inst, greedy(inst)), optimum[inst.name]) for inst in insts)
    print(f"  optimal on {n_opt}/{len(insts)} instances")

    print(f"\n2. Randomized construction, {RUNS} runs per instance")
    print("  beta  | all valid | avg different plans | best of runs optimal")
    for beta in BETAS:
        all_valid, n_diff, n_best_opt = True, [], 0
        for inst in insts:
            rng = np.random.default_rng(42)
            plans = [construct(inst, beta, rng) for _ in range(RUNS)]
            all_valid &= all(is_valid(inst, p) for p in plans)
            n_diff.append(len({tuple(sorted(p.items())) for p in plans}))
            n_best_opt += same_key(min(key(inst, p) for p in plans), optimum[inst.name])
        print(f"  {beta:4.2f}  | {str(all_valid):9s} | {np.mean(n_diff):19.1f} | {n_best_opt}/{len(insts)}")

    # beta = 0 must give the same plan as greedy, whatever the random seed
    same = all(construct(inst, 0.0, np.random.default_rng(s)) == greedy(inst) for inst in insts for s in range(3))
    print(f"\n  beta = 0 equals greedy for every seed: {same}")

    print("\n3. Medium instances: one construction (beta = 0.25)")
    for name, case, nI, cap in [("fez", 1, 18, 2), ("fez", 2, 22, 2), ("fez", 3, 33, 2), ("edmonton", 1, 20, None)]:
        inst = random_instance(load_map(name, case), nI, 0, n_sleeping=2, capacity=cap,
                               T=30 if name == "fez" else 10)
        t0 = time.perf_counter()
        plan = construct(inst, 0.25, np.random.default_rng(0))
        print(f"  {name} case {case} |J|={inst.nJ} |I|={nI}: valid={is_valid(inst, plan)}  "
              f"{time.perf_counter() - t0:.2f}s")


if __name__ == "__main__":
    main()
