"""Check that the fast scorer (PlanState) gives EXACTLY the same keys as key().

On small and medium instances (with the moving cost lambda and the penalty P switched
on, so every part of goal 4 is used), start from random plans, then apply many random
moves, swaps and placements. After each change compare:
  PlanState.key_after(change)   vs   key(plan after the change), computed from scratch
They must be identical (same numbers, not just close). The state after apply() is
also compared with a state built from scratch.

Run from the repo folder:   .venv/bin/python person2/checks/check_fast_scoring.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # the person2 folder
from instances import load_map, random_instance                  # noqa: E402
from scoring import PlanState, key                               # noqa: E402
from construction import construct                               # noqa: E402
from local_search import neighbours                              # noqa: E402


def same_state(s1, s2):
    return (s1.plan == s2.plan and np.array_equal(s1.n, s2.n) and np.array_equal(s1.reach_2T, s2.reach_2T)
            and np.array_equal(s1.k, s2.k) and s1.overtime == s2.overtime and s1.moves == s2.moves)


def main():
    n_checks = n_ok = 0
    for name, case, nI, cap, T in [("madrid", 1, 5, 2, 8), ("fez", 1, 18, 2, 30),
                                   ("fez", 3, 33, 2, 30), ("edmonton", 1, 20, None, 10)]:
        region = load_map(name, case)
        for seed in range(3):
            inst = random_instance(region, nI, seed, n_sleeping=2, capacity=cap, T=T, M=3, lam=1e-4)
            inst.P = 0.01                                      # switch the uncovered penalty on too
            rng = np.random.default_rng(seed)

            # placements, as in the construction
            state = PlanState(inst, {})
            for _ in range(nI):
                i = next(i for i in range(nI) if i not in state.plan)
                j = int(rng.choice([j for j in range(inst.nJ) if j not in inst.S and state.n[j] < inst.C[j]]))
                n_checks += 1
                n_ok += state.key_after([(i, j)]) == key(inst, {**state.plan, i: j})
                state.apply([(i, j)])

            # moves and swaps, as in the local search
            state = PlanState(inst, construct(inst, 1.0, rng))
            for _ in range(200):
                changes = list(neighbours(state))
                change = changes[rng.integers(len(changes))]
                n_checks += 1
                n_ok += state.key_after(change) == key(inst, {**state.plan, **dict(change)})
                state.apply(change)
                n_checks += 1
                n_ok += same_state(state, PlanState(inst, state.plan))
    print(f"fast key == key() and state after apply() == fresh state: {n_ok}/{n_checks}")


if __name__ == "__main__":
    main()
