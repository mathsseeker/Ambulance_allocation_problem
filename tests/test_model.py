"""Spec section 8 tests."""
import itertools

import numpy as np
import pytest
from scipy.stats import norm

from ambulance.data_loader import load_case
from ambulance.evaluate import evaluate
from ambulance.instance import build_instance, generate_instance
from ambulance.model import solve_elastic, solve_exact, solve_hard


def tiny(**kw):
    """3 areas, 2 bases, 2 ambulances, no S, lam = 0 (by default)."""
    t = np.array([[5, 12, 40], [40, 12, 5]], float)
    g = np.array([[0, 20], [20, 0]], float)
    params = dict(d=[0.5, 0.3, 0.2], t=t, g=g, delta=[0, 0], h=[0, 1], s=[480, 480],
                  C=[2, 2], M=2, T=15, q=0.3)
    params.update(kw)
    return build_instance(**params)


def best_by_enumeration(inst, model="base"):
    best = None
    for combo in itertools.product(range(inst.nJ), repeat=inst.nI):
        ev = evaluate(inst, dict(enumerate(combo)), model)
        if ev["feasible"] and (best is None or ev["objective"] > best):
            best = ev["objective"]
    return best


@pytest.mark.parametrize("case", [1, 2, 3])
def test_d_sums_to_one(case):
    assert abs(load_case(case).d.sum() - 1) < 1e-9


@pytest.mark.parametrize("solver,model", [(solve_exact, "base"), (solve_hard, "hard"), (solve_elastic, "elastic")])
@pytest.mark.parametrize("seed", range(5))
def test_evaluate_matches_gurobi(solver, model, seed):
    inst = generate_instance(1, 6, seed, n_sleeping=seed % 2 * 2, M=6, lam=1e-4, P=1e-3)
    res = solver(inst)
    if res["status"] == "OPTIMAL":
        ev = evaluate(inst, res["assignment"], model)
        assert ev["feasible"]
        assert abs(ev["objective"] - res["objective"]) < 1e-6
        assert abs(ev["coverage_term"] - res["coverage_term"]) < 1e-6
    else:
        assert res["status"] == "INFEASIBLE" and res["message"]


@pytest.mark.parametrize("lam,P", [(0, 0), (0.001, 0), (0, 0.01)])
def test_tiny_enumeration(lam, P):
    inst = tiny(lam=lam, P=P)
    res = solve_exact(inst)
    assert res["status"] == "OPTIMAL"
    assert abs(res["objective"] - best_by_enumeration(inst)) < 1e-9


def test_M_zero_nobody_moves():
    inst = tiny(M=0, delta=[1, 0])
    res = solve_exact(inst)
    assert res["status"] == "OPTIMAL"
    assert all(res["assignment"][i] == inst.delta[i] for i in range(inst.nI))


def test_large_lam_nobody_moves():
    inst = tiny(lam=1e6, delta=[0, 0])
    res = solve_exact(inst)
    assert res["n_moves"] == 0


@pytest.mark.parametrize("q", [0.1, 0.3, 0.7])
@pytest.mark.parametrize("n", [0, 1, 2, 5])
def test_coverage_identity(q, n):
    assert abs(sum((1 - q) * q ** (k - 1) for k in range(1, n + 1)) - (1 - q ** n)) < 1e-12


def test_z_values():
    assert [round(norm.ppf(a), 3) for a in (0.95, 0.97, 0.99)] == [1.645, 1.881, 2.326]


@pytest.mark.parametrize("case", [1, 3])
def test_b_monotone(case):
    rd = load_case(case)
    def b(alpha, cv):
        return build_instance(rd.d, rd.t, rd.g, [0], [0], [480], alpha=alpha, cv=cv).b
    for lo, hi in [(0.95, 0.97), (0.97, 0.99)]:
        assert np.all(b(hi, 0.2) <= b(lo, 0.2))
    for lo, hi in [(0.1, 0.2), (0.2, 0.3)]:
        assert np.all(b(0.97, hi) <= b(0.97, lo))


def _relationships(inst):
    base, hard, el = solve_exact(inst), solve_hard(inst), solve_elastic(inst)
    if base["status"] == "OPTIMAL":
        assert el["status"] == "OPTIMAL"                       # E feasible whenever section 5 is
    if hard["status"] == "OPTIMAL":
        assert el["n_violated"] == 0
        assert abs(el["objective"] - hard["objective"]) < 1e-6
    if hard["status"] == "INFEASIBLE" and el["status"] == "OPTIMAL":
        assert el["n_violated"] >= 1
    return hard["status"]


def test_H_E_relationships_on_real_data():
    seen = set()
    for case, n, ns, seed in itertools.product([1, 2], [2, 12], [0, 2], range(3)):
        seen.add(_relationships(generate_instance(case, n, seed, n_sleeping=ns, M=n)))
    # Model H needs ~17 of the 18 Case-1 bases occupied, so use a full fleet with long shifts
    rd = load_case(1)
    rng = np.random.default_rng(0)
    for n in (18, 24, 30):
        for _ in range(3):
            delta = rng.integers(0, 18, n)
            inst = build_instance(rd.d, rd.t, rd.g, delta=delta, h=delta, s=np.full(n, 480),
                                  C=np.full(18, 2), M=n, lam=1e-4)
            seen.add(_relationships(inst))
    assert {"OPTIMAL", "INFEASIBLE"} <= seen                   # both outcomes were exercised


def test_H_infeasible_by_construction():
    t = np.array([[5, 100], [100, 5]], float)
    g = np.array([[0, 100], [100, 0]], float)
    inst = build_instance(d=[0.5, 0.5], t=t, g=g, delta=[0], h=[0], s=[480], e=[0, 0], C=[2, 2], M=1)
    assert inst.V2 == [0, 1]
    hard = solve_hard(inst)
    assert hard["status"] == "INFEASIBLE" and "(9H)" in hard["iis_families"]
    el = solve_elastic(inst)
    assert el["status"] == "OPTIMAL" and el["n_violated"] == 1


def test_always_returns_a_status():
    inst = tiny(C=[0, 0])                                      # capacity pre-check fails
    for solver in (solve_exact, solve_hard, solve_elastic):
        res = solver(inst)
        assert res["status"] == "PRECHECK_FAILED" and "capacity" in res["message"]
