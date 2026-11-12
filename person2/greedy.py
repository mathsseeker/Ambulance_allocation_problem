"""Greedy construction for Model R.

Start with no ambulance placed. At each step, try every (ambulance, base)
placement that keeps the plan valid, score the partial plan with key(),
and keep the best one. Repeat until every free ambulance has a base.

    greedy(inst) -> plan {ambulance i: base j}

This is GRASP with beta = 0 (no randomness). It is also a baseline
that Person 4 can compare against.
"""
from scoring import ambulances_per_base, key


def open_bases(inst, plan):
    """Bases that can still take one more free ambulance: awake and below capacity."""
    n = ambulances_per_base(inst, plan)
    return [j for j in range(inst.nJ) if j not in inst.S and n[j] < inst.C[j]]


def candidates(inst, plan):
    """Every valid next placement, with the key of the partial plan it would create."""
    result = []
    for j in open_bases(inst, plan):
        for i in range(inst.nI):
            if i not in plan:
                result.append((key(inst, {**plan, i: j}), i, j))
    return result


def greedy(inst):
    plan = {}
    while len(plan) < inst.nI:
        best_key, i, j = min(candidates(inst, plan))
        plan[i] = j
    return plan
