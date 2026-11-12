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
"""
from construction import open_bases
from scoring import key


def neighbours(inst, plan):
    """Every plan reachable with one move or one swap. All of them are valid."""
    bases = open_bases(inst, plan)               # awake bases with a free spot
    for i in range(inst.nI):                     # MOVE
        for j in bases:
            if j != plan[i]:
                yield {**plan, i: j}
    for i1 in range(inst.nI):                    # SWAP
        for i2 in range(i1 + 1, inst.nI):
            if plan[i1] != plan[i2]:
                yield {**plan, i1: plan[i2], i2: plan[i1]}


def local_search(inst, plan, mode="first"):
    current, current_key = dict(plan), key(inst, plan)
    improved = True
    while improved:
        improved = False
        best, best_key = None, current_key
        for candidate in neighbours(inst, current):
            k = key(inst, candidate)
            if k < best_key:
                best, best_key = candidate, k
                if mode == "first":
                    break
        if best is not None:
            current, current_key = best, best_key
            improved = True
    return current
