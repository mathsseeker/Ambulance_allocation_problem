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

from scoring import PlanState


def open_bases(inst, n):
    """Bases that can still take one more free ambulance: awake and below capacity.
    n[j] = ambulances at base j now."""
    return [j for j in range(inst.nJ) if j not in inst.S and n[j] < inst.C[j]]


def candidates(state):
    """Every valid next placement as (key of the partial plan, i, j), best first."""
    inst, result = state.inst, []
    for j in open_bases(inst, state.n):
        for i in range(inst.nI):
            if i not in state.plan:
                result.append((state.key_after([(i, j)]), i, j))
    return sorted(result)


def rcl_size(n_candidates, beta):
    """How many of the best candidates go in the RCL."""
    return 1 + int(beta * (n_candidates - 1))


def construct(inst, beta, rng):
    state = PlanState(inst, {})                         # empty plan
    while len(state.plan) < inst.nI:
        cands = candidates(state)
        rcl = cands[:rcl_size(len(cands), beta)]
        _, i, j = rcl[rng.integers(len(rcl))]
        state.apply([(i, j)])
    return state.plan


def greedy(inst):
    return construct(inst, beta=0.0, rng=np.random.default_rng(0))
