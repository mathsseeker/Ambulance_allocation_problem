"""Local search phase of GRASP for Model R.

Start from a valid plan and try small changes (the neighbourhood):
  - MOVE: send one ambulance to another base that is awake and not full
  - SWAP: two ambulances at different bases exchange bases
          (base counts stay the same, but overtime and moves can change,
           because they depend on WHICH ambulance is where)
Keep a change only if it gives a strictly smaller key (= a better plan).
Stop when no change improves the plan: a local optimum.

    local_search(inst, plan, mode="first") -> improved plan

mode="first": take the first improving change found, then scan again.
mode="best":  check all changes, take the best one, then scan again.

Changes are scored with PlanState.key_after, which only updates what the
change touches (same key as scoring.key, much faster).
"""
from construction import open_bases
from scoring import PlanState


def neighbours(state):
    """Every change (one move or one swap) from the current plan. All keep the plan valid."""
    inst, plan = state.inst, state.plan
    bases = open_bases(inst, state.n)            # awake bases with a free spot
    for i in range(inst.nI):                     # MOVE
        for j in bases:
            if j != plan[i]:
                yield [(i, j)]
    for i1 in range(inst.nI):                    # SWAP
        for i2 in range(i1 + 1, inst.nI):
            if plan[i1] != plan[i2]:
                yield [(i1, plan[i2]), (i2, plan[i1])]


def local_search(inst, plan, mode="first"):
    state = PlanState(inst, plan)
    current_key = state.key_after([])
    improved = True
    while improved:
        improved = False
        best_change, best_key = None, current_key
        for change in neighbours(state):
            k = state.key_after(change, to_beat=best_key)
            if k is not None and k < best_key:
                best_change, best_key = change, k
                if mode == "first":
                    break
        if best_change is not None:
            state.apply(best_change)
            current_key = best_key
            improved = True
    return state.plan
