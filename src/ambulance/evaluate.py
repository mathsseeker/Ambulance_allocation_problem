"""Score ANY assignment straight from the formulas (no Gurobi) and check every constraint.

    evaluate(inst, assignment, model="base" | "hard" | "elastic" | "robust")

`model="robust"` treats (4) and (5) as soft and reports extra moves and overtime minutes.
`assignment` maps ambulance i -> base j (0-based). The objective uses the best y, u, w
for that x, which is what the solver chooses, so it equals Gurobi's objective.
"""
from __future__ import annotations

import numpy as np

from .instance import Instance


def evaluate(inst: Instance, assignment: dict[int, int], model: str = "base") -> dict:
    viol: dict[str, list] = {f: [] for f in ("(1)", "(3)", "(4)", "(5)", "(6)", "(9)")}

    # (1) one base each
    for i in range(inst.nI):
        if i not in assignment or not 0 <= int(assignment[i]) < inst.nJ:
            viol["(1)"].append(i)
    x = np.zeros((inst.nI, inst.nJ), int)
    for i, j in assignment.items():
        if 0 <= i < inst.nI and 0 <= int(j) < inst.nJ:
            x[i, int(j)] = 1

    load = x.sum(axis=0) + inst.e
    viol["(3)"] = [int(j) for j in np.flatnonzero(load > inst.C)]
    moves = sum(1 for i, j in assignment.items() if int(j) != inst.delta[i])
    if moves > inst.M:
        viol["(4)"] = [moves]
    S = set(inst.S)
    for i, j in assignment.items():
        j = int(j)
        if j != inst.h[i] and inst.r[i, j] > inst.s[i]:
            viol["(5)"].append((i, j))
        if j in S:
            viol["(6)"].append((i, j))

    # coverage: sum_{k<=n_v} (1-q) q^(k-1) = 1 - q^n_v, with n_v capped at the y variables created
    n = (inst.a * load[:, None]).sum(axis=0)
    n_eff = np.minimum(n, inst.ymax)
    coverage = float((inst.d * (1 - inst.q ** n_eff)).sum())
    minutes = float(sum(inst.c[i, int(j)] for i, j in assignment.items()))
    uncovered = int((n_eff == 0).sum()) if inst.P > 0 else 0

    nb = (inst.b * load[:, None]).sum(axis=0)
    viol["(9)"] = [v for v in inst.V2 if nb[v] < 1]
    n_viol9 = len(viol["(9)"])

    regular = coverage - inst.lam * minutes - inst.P * uncovered
    obj = regular - (inst.P2 * n_viol9 if model == "elastic" else 0.0)
    overtime = int(sum(inst.ot[i, int(j)] for i, j in assignment.items()))

    if model == "robust":   # (4) and (5) are soft in Model R: penalised, not forbidden
        hard_fams = ["(1)", "(3)", "(6)"]
    else:
        hard_fams = ["(1)", "(3)", "(4)", "(5)", "(6)"] + (["(9)"] if model == "hard" else [])
    feasible = all(not viol[f] for f in hard_fams)
    return {
        "model": model, "feasible": feasible, "objective": obj, "regular": regular,
        "coverage_term": coverage, "moving_cost_term": inst.lam * minutes, "moving_minutes": minutes,
        "uncovered_term": inst.P * uncovered, "n_moves": moves, "extra_moves": max(0, moves - inst.M),
        "overtime_minutes": overtime, "n_violated_9": n_viol9,
        "violations": {f: v for f, v in viol.items() if v},
    }
