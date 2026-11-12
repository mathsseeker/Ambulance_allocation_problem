"""GRASP for Model R: repeat (construction + local search), keep the best plan.

    result = grasp(inst, beta=0.25, iterations=100, time_limit=None, seed=0, mode="first")

Each iteration:
  1. construct a plan with the RCL (randomness controlled by beta)
  2. improve it with local search (MOVE + SWAP)
  3. if it is better than the best plan so far, keep it
Stop after `iterations` iterations, or earlier when `time_limit` seconds have passed
(at least one iteration always runs, so there is always a plan).

The result is a dict:
  plan            best plan found {ambulance i: base j}
  goals           its four goals (f1, f2, f3, f4)
  runtime         seconds used
  iterations      iterations done
  best_iteration  iteration where the best plan was found (1 = first)
  history         list of (seconds, iteration, goals) each time the best plan improved,
                  for quality-vs-time plots
"""
import time

import numpy as np

from construction import construct
from local_search import local_search
from scoring import goals, key


def grasp(inst, beta=0.25, iterations=100, time_limit=None, seed=0, mode="first"):
    rng = np.random.default_rng(seed)
    start = time.perf_counter()
    best_plan, best_key, best_iteration = None, None, 0
    history = []

    done = 0
    while done < max(1, iterations):                     # always at least one iteration
        if done > 0 and time_limit is not None and time.perf_counter() - start >= time_limit:
            break
        done += 1
        plan = local_search(inst, construct(inst, beta, rng), mode)
        k = key(inst, plan)
        if best_key is None or k < best_key:
            best_plan, best_key, best_iteration = plan, k, done
            history.append((time.perf_counter() - start, done, goals(inst, plan)))

    return {
        "plan": best_plan,
        "goals": goals(inst, best_plan),
        "runtime": time.perf_counter() - start,
        "iterations": done,
        "best_iteration": best_iteration,
        "history": history,
    }
