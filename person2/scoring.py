"""Score a plan for Model R (no Gurobi needed).

`inst` is Person 1's Instance (src/ambulance/instance.py): it holds the map,
the situation, the settings and the derived parameters (a, b, V2, c, ot).
A plan is a dict {ambulance i: base j}, numbered from 0.

    is_valid(inst, plan) -> True if the 3 hard rules hold
    goals(inst, plan)    -> (f1, f2, f3, f4), the four goals of Model R
    key(inst, plan)      -> (f1, f2, f3, -f4); a SMALLER key is a BETTER plan

Python compares tuples element by element, so comparing two keys
compares goal 1 first, then goal 2, then goal 3, then goal 4,
exactly the lexicographic order of Model R.
"""
import numpy as np


def ambulances_per_base(inst, plan):
    """n_j: free ambulances placed at base j plus the fixed ones (e_j)."""
    n = inst.e.copy()
    for i, j in plan.items():
        n[j] += 1
    return n


def is_valid(inst, plan):
    """The 3 hard rules of Model R: (1) one base each, (6) no sleeping base, (3) capacity."""
    if sorted(plan) != list(range(inst.nI)):           # (1) every ambulance exactly once
        return False
    for j in plan.values():
        if not 0 <= j < inst.nJ or j in inst.S:         # (6) no sleeping base
            return False
    n = ambulances_per_base(inst, plan)
    return bool(np.all(n <= inst.C))                    # (3) capacity


def goals(inst, plan):
    """Return (f1, f2, f3, f4) for a valid plan."""
    n = ambulances_per_base(inst, plan)

    # Goal 1: areas in V2 with no ambulance within 2T (b_jv = 1).
    reach_2T = inst.b.T @ n                             # for each area: ambulances within 2T
    f1 = int(sum(1 for v in inst.V2 if reach_2T[v] == 0))

    # Goal 2: overtime minutes.
    f2 = int(sum(inst.ot[i, j] for i, j in plan.items()))

    # Goal 3: moves above the free allowance M.
    moves = sum(1 for i, j in plan.items() if j != inst.delta[i])
    f3 = max(0, moves - inst.M)

    # Goal 4: expected coverage within T, minus moving cost and uncovered penalty.
    k = inst.a.T @ n                                    # for each area: ambulances within T
    coverage = float(np.sum(inst.d * (1 - inst.q ** k)))
    moving = float(sum(inst.c[i, j] for i, j in plan.items()))
    uncovered = int(np.sum(k == 0))
    f4 = coverage - inst.lam * moving - inst.P * uncovered

    return f1, f2, f3, f4


def key(inst, plan):
    """Sort key: smaller is better (goal 4 is maximised, so it is negated)."""
    f1, f2, f3, f4 = goals(inst, plan)
    return (f1, f2, f3, -f4)
