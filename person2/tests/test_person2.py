"""Tests for Person 2's GRASP (no Gurobi needed).

Run from the repo folder:   .venv/bin/python -m pytest person2/tests -v

Most tests use the tiny hand-made map from conftest.py, where every number
can be checked by hand. The last tests compare GRASP with brute force
(trying every plan) on many small random instances.
"""
import itertools

import numpy as np
import pytest

from conftest import tiny
from scoring import PlanState, goals, has_valid_plan, is_valid, key
from construction import construct, greedy
from local_search import local_search
from grasp import grasp
from instances import load_map, random_instance

LONG_SHIFT = 1000          # minutes: no overtime possible


def brute_force_best_key(inst):
    best = None
    for bases in itertools.product(range(inst.nJ), repeat=inst.nI):
        plan = dict(enumerate(bases))
        if is_valid(inst, plan) and (best is None or key(inst, plan) < best):
            best = key(inst, plan)
    return best


# ---------- the scorer, checked by hand ----------

def test_goals_by_hand_spread_out():
    # one ambulance at base 0 (covers area 0), one at base 1 (covers area 1), nobody moves
    inst = tiny(delta=[0, 1], home=[0, 1], shift=[LONG_SHIFT] * 2)
    f1, f2, f3, f4 = goals(inst, {0: 0, 1: 1})
    assert (f1, f2, f3) == (0, 0, 0)
    assert f4 == pytest.approx(0.6 * (1 - 0.3) + 0.4 * (1 - 0.3))          # 0.70


def test_goals_by_hand_both_at_base_0():
    # both at base 0: area 0 has 2 ambulances within T, area 1 has none and none within 2T
    inst = tiny(delta=[0, 1], home=[0, 1], shift=[LONG_SHIFT] * 2)
    f1, f2, f3, f4 = goals(inst, {0: 0, 1: 0})
    assert f1 == 1                                   # area 1 out of 2T reach
    assert f3 == 0                                   # 1 move, allowance M = 2
    assert f4 == pytest.approx(0.6 * (1 - 0.3 ** 2))  # 0.546


def test_overtime_by_hand():
    # ambulance at base 0, home base 1, 15 min of shift left: going to base 2 then home = 10 + 10 = 20 min
    inst = tiny(delta=[0], home=[1], shift=[15])
    assert goals(inst, {0: 2})[1] == 5               # 20 - 15 = 5 overtime minutes
    assert goals(inst, {0: 1})[1] == 15              # 30 min to base 1 (home), 30 - 15 = 15


def test_extra_moves_by_hand():
    inst = tiny(delta=[0, 0, 0], home=[0, 0, 0], shift=[LONG_SHIFT] * 3, C=(3, 3, 3), M=1)
    assert goals(inst, {0: 0, 1: 1, 2: 2})[2] == 1   # 2 moves, 1 free -> 1 extra


def test_validity_rules():
    inst = tiny(delta=[0, 1], home=[0, 1], shift=[LONG_SHIFT] * 2, S=[2], C=(1, 2, 2))
    assert is_valid(inst, {0: 0, 1: 1})
    assert not is_valid(inst, {0: 0})                # rule 1: ambulance 1 has no base
    assert not is_valid(inst, {0: 0, 1: 2})          # rule 6: base 2 has a sleeping crew
    assert not is_valid(inst, {0: 0, 1: 0})          # rule 3: base 0 holds only 1


def test_fast_scorer_equals_key():
    inst = tiny(delta=[0, 1, 2], home=[1, 2, 0], shift=[15, 40, 5], C=(2, 2, 2), M=0, lam=0.001)
    for bases in itertools.product(range(3), repeat=3):
        plan = dict(enumerate(bases))
        if is_valid(inst, plan):
            state = PlanState(inst, {0: 0, 1: 1, 2: 2})
            change = [(i, j) for i, j in plan.items()]
            assert state.key_after(change) == key(inst, plan)


# ---------- Model R's strict order ----------

def test_goal_1_beats_overtime():
    # The ambulance is at base 0 and its shift is over (0 min left). Staying leaves area 1
    # out of 2T reach (f1 = 1). Moving to base 2 reaches both areas (f1 = 0) but costs overtime.
    # Goal 1 comes first, so GRASP must move it.
    inst = tiny(delta=[0], home=[0], shift=[0])
    plan = grasp(inst, iterations=5)["plan"]
    assert plan == {0: 2}
    assert goals(inst, plan)[:2] == (0, 20)          # 10 min there + 10 min back home


def test_overtime_beats_coverage():
    # Both ambulances at base 2 (their home), which reaches both areas within 2T, so goal 1 is 0.
    # Ambulance 0 has no shift left, so any move is overtime; ambulance 1 has plenty.
    # Best coverage (0.70) would put one at base 0 and one at base 1, which needs ambulance 0
    # to move. Goal 2 (overtime) comes before goal 4 (coverage): ambulance 0 must stay home.
    inst = tiny(delta=[2, 2], home=[2, 2], shift=[0, LONG_SHIFT])
    plan = grasp(inst, iterations=10)["plan"]
    assert plan[0] == 2
    assert goals(inst, plan)[1] == 0


# ---------- edge cases ----------

def test_no_free_ambulances():
    inst = tiny(delta=[], home=[], shift=[])
    result = grasp(inst, iterations=3)
    assert result["plan"] == {}


def test_one_ambulance_is_optimal():
    inst = tiny(delta=[1], home=[0], shift=[25])
    assert key(inst, grasp(inst, iterations=5)["plan"]) == brute_force_best_key(inst)


def test_never_uses_sleeping_base_and_counts_forced_move():
    # ambulance 0 sits at base 2, which has a sleeping crew: it must leave, and that move counts
    inst = tiny(delta=[2, 0], home=[0, 0], shift=[LONG_SHIFT] * 2, S=[2], M=0)
    plan = grasp(inst, iterations=10)["plan"]
    assert 2 not in plan.values()
    assert goals(inst, plan)[2] >= 1


def test_only_one_spot_left():
    # bases 0 and 1 are full of fixed ambulances except one spot at base 1
    inst = tiny(delta=[1], home=[1], shift=[LONG_SHIFT], S=[0, 2], C=(1, 2, 1))
    assert grasp(inst, iterations=3)["plan"] == {0: 1}


def test_no_valid_plan_raises():
    inst = tiny(delta=[0, 1, 2], home=[0, 1, 2], shift=[LONG_SHIFT] * 3, C=(1, 1, 0))
    assert not has_valid_plan(inst)
    with pytest.raises(ValueError):
        grasp(inst)


def test_bad_parameters_raise():
    inst = tiny(delta=[0], home=[0], shift=[LONG_SHIFT])
    with pytest.raises(ValueError):
        grasp(inst, beta=1.5)
    with pytest.raises(ValueError):
        grasp(inst, mode="fastest")


def test_tied_scores_are_handled():
    # two identical ambulances at base 2 with identical options: many placements tie
    inst = tiny(delta=[2, 2], home=[2, 2], shift=[LONG_SHIFT] * 2)
    plan = greedy(inst)
    assert is_valid(inst, plan)
    assert greedy(inst) == plan                      # ties broken the same way every time


# ---------- GRASP behaviour ----------

def test_beta_zero_is_greedy():
    inst = random_instance(load_map("madrid"), 5, seed=3, n_sleeping=1, capacity=2, T=8)
    for seed in range(3):
        assert construct(inst, 0.0, np.random.default_rng(seed)) == greedy(inst)


def test_same_seed_same_result():
    inst = random_instance(load_map("madrid"), 5, seed=4, n_sleeping=1, capacity=2, T=8)
    assert grasp(inst, iterations=10, seed=7)["plan"] == grasp(inst, iterations=10, seed=7)["plan"]


def test_local_search_never_worse():
    inst = random_instance(load_map("madrid"), 6, seed=5, n_sleeping=2, capacity=2, T=8)
    rng = np.random.default_rng(0)
    for _ in range(10):
        start = construct(inst, 1.0, rng)
        assert not key(inst, start) < key(inst, local_search(inst, start))


def test_time_limit_stops_the_search():
    inst = random_instance(load_map("fez", 1), 18, seed=0, n_sleeping=2, capacity=2)
    result = grasp(inst, iterations=100_000, time_limit=1.0)
    assert result["runtime"] < 3.0
    assert result["iterations"] < 100_000


@pytest.mark.parametrize("seed", range(30))
def test_grasp_matches_brute_force(seed):
    rng = np.random.default_rng(seed)
    inst = random_instance(load_map("madrid"), int(rng.integers(1, 6)), seed, n_sleeping=int(rng.integers(0, 3)),
                           capacity=int(rng.integers(1, 3)), T=float(rng.choice([5, 8, 10])),
                           M=int(rng.integers(0, 3)), shift_max=120)
    result = grasp(inst, iterations=50, seed=seed)
    assert is_valid(inst, result["plan"])
    assert key(inst, result["plan"]) == brute_force_best_key(inst)
