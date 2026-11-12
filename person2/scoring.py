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

For speed, the heuristic uses PlanState: it remembers the counts of a plan
(ambulances per base, per area within T and within 2T, overtime, moves), so
the key after a small change (a move or a swap) only updates what changed.
It gives exactly the same key as key(), because both finish with goals_from().
"""
import math

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


def first_three_goals(inst, reach_2T, overtime, moves):
    """Goals 1-3, given: reach_2T[v] = ambulances within 2T of area v,
    overtime = total overtime minutes, moves = ambulances not at their current base."""
    f1 = int(np.count_nonzero(reach_2T[inst.V2] == 0))      # goal 1: areas out of 2T reach
    f2 = int(overtime)                                     # goal 2: overtime minutes
    f3 = max(0, moves - inst.M)                            # goal 3: moves above M
    return f1, f2, f3


def goal4(inst, plan, k):
    """Goal 4, given k[v] = ambulances within T of area v."""
    coverage = float(np.sum(inst.d * (1 - inst.q ** k)))   # expected coverage within T ...
    f4 = coverage
    if inst.lam:                                           # ... minus moving cost
        f4 -= inst.lam * math.fsum(inst.c[i, j] for i, j in plan.items())
    if inst.P:                                             # ... minus uncovered-area penalty
        f4 -= inst.P * int(np.count_nonzero(k == 0))
    return f4


def goals_from(inst, plan, reach_2T, k, overtime, moves):
    """The four goals, given the counts of the plan."""
    return (*first_three_goals(inst, reach_2T, overtime, moves), goal4(inst, plan, k))


def goals(inst, plan):
    """Return (f1, f2, f3, f4), computed from scratch."""
    n = ambulances_per_base(inst, plan)
    reach_2T = inst.b.T @ n                             # for each area: ambulances within 2T
    k = inst.a.T @ n                                    # for each area: ambulances within T
    overtime = sum(int(inst.ot[i, j]) for i, j in plan.items())
    moves = sum(1 for i, j in plan.items() if j != inst.delta[i])
    return goals_from(inst, plan, reach_2T, k, overtime, moves)


def key(inst, plan):
    """Sort key: smaller is better (goal 4 is maximised, so it is negated)."""
    f1, f2, f3, f4 = goals(inst, plan)
    return (f1, f2, f3, -f4)


class PlanState:
    """A plan (possibly partial) together with its counts, for fast scoring of small changes.

    A change is a list of (ambulance i, new base j): a MOVE is [(i, j)], a SWAP is
    [(i1, base of i2), (i2, base of i1)], placing a new ambulance is [(i, j)].
    """

    def __init__(self, inst, plan):
        self.inst = inst
        self.plan = dict(plan)
        self.n = ambulances_per_base(inst, plan)
        self.reach_2T = inst.b.T @ self.n
        self.k = inst.a.T @ self.n
        self.overtime = sum(int(inst.ot[i, j]) for i, j in plan.items())
        self.moves = sum(1 for i, j in plan.items() if j != inst.delta[i])

    def _counts_after(self, change):
        inst = self.inst
        plan, n = dict(self.plan), self.n.copy()
        reach_2T, k = self.reach_2T.copy(), self.k.copy()
        overtime, moves = self.overtime, self.moves
        for i, j in change:
            if i in plan:                               # take ambulance i away from its base
                old = plan[i]
                n[old] -= 1
                reach_2T -= inst.b[old]
                k -= inst.a[old]
                overtime -= int(inst.ot[i, old])
                moves -= old != inst.delta[i]
            plan[i] = j                                 # put it at base j
            n[j] += 1
            reach_2T += inst.b[j]
            k += inst.a[j]
            overtime += int(inst.ot[i, j])
            moves += j != inst.delta[i]
        return plan, n, reach_2T, k, overtime, moves

    def key_after(self, change, to_beat=None):
        """Key of the plan after the change, without changing this state.

        If `to_beat` is a key and goals 1-3 already show the change is worse,
        return None without computing goal 4 (it could not win anyway)."""
        plan, _, reach_2T, k, overtime, moves = self._counts_after(change)
        f1, f2, f3 = first_three_goals(self.inst, reach_2T, overtime, moves)
        if to_beat is not None and (f1, f2, f3) > to_beat[:3]:
            return None
        return (f1, f2, f3, -goal4(self.inst, plan, k))

    def apply(self, change):
        """Make the change permanent."""
        self.plan, self.n, self.reach_2T, self.k, self.overtime, self.moves = self._counts_after(change)
