"""Construction phase of GRASP for Model R.

Start with no ambulance placed. At each step:
  1. list every (ambulance, base) placement that keeps the plan valid,
  2. score each with key() of the partial plan it would create,
  3. keep the best ones: the Restricted Candidate List (RCL),
  4. pick one placement from the RCL at random.
Repeat until every free ambulance has a base.

    construct(inst, beta, rng) -> plan {ambulance i: base j}
    greedy(inst)               -> construct with beta = 0 (no randomness)

The RCL is CARDINALITY-based: it holds the best 1 + beta * (number of candidates - 1)
placements. beta = 0 keeps only the best (pure greedy), beta = 1 keeps all (pure random).
A value-based RCL (score >= best - beta * range) needs one number per candidate,
but Model R's key has four goals compared in order, so there is no single range.
"""
import numpy as np

from scoring import ambulances_per_base, key


def open_bases(inst, plan):
    """Bases that can still take one more free ambulance: awake and below capacity."""
    n = ambulances_per_base(inst, plan)
    return [j for j in range(inst.nJ) if j not in inst.S and n[j] < inst.C[j]]


def candidates(inst, plan):
    """Every valid next placement as (key of the partial plan, i, j), best first."""
    result = []
    for j in open_bases(inst, plan):
        for i in range(inst.nI):
            if i not in plan:
                result.append((key(inst, {**plan, i: j}), i, j))
    return sorted(result)


def rcl_size(n_candidates, beta):
    """How many of the best candidates go in the RCL."""
    return 1 + int(beta * (n_candidates - 1))


def construct(inst, beta, rng):
    plan = {}
    while len(plan) < inst.nI:
        cands = candidates(inst, plan)
        rcl = cands[:rcl_size(len(cands), beta)]
        _, i, j = rcl[rng.integers(len(rcl))]
        plan[i] = j
    return plan


def greedy(inst):
    return construct(inst, beta=0.0, rng=np.random.default_rng(0))
