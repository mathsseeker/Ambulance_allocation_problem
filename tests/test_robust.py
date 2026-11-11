"""Model R tests (robust task, section 4.3) plus a port-vs-reference equivalence check."""
import itertools
import random
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference"))
import robust_model_reference as ref  # noqa: E402

from ambulance.evaluate import evaluate  # noqa: E402
from ambulance.instance import build_instance, generate_instance  # noqa: E402
from ambulance.model import solve_elastic, solve_hard, solve_robust  # noqa: E402


def from_ref(d: dict):
    """Reference dict instance (ids 0..n-1) -> our Instance."""
    I, J, V = d["I"], d["J"], d["V"]
    assert I == list(range(len(I))) and J == list(range(len(J))) and V == list(range(len(V)))
    t = np.array([[d["t"][j, v] for v in V] for j in J])
    g = np.array([[d["g"][j, k] for k in J] for j in J])
    return build_instance(
        d=[d["d"][v] for v in V], t=t, g=g, delta=[d["delta"][i] for i in I], h=[d["h"][i] for i in I],
        s=[d["s"][i] for i in I], S=sorted(d["S"]), e=[d["e"][j] for j in J], C=[d["C"][j] for j in J],
        M=d["M"], lam=d["lam"], P=d["P"], T=d["T"], q=d["q"], alpha=d["alpha"], cv=d["cv"])


def ref_instances(n=80):
    rng = random.Random(7)
    return [ref.random_instance(rng, night=(k % 2 == 1)) for k in range(n)]


def real_instances():
    """Real-data instances that fit the size-limited licence, M = 2 (where strict models struggle)."""
    for case, n, ns, seed in itertools.product([1, 2, 3], [2, 6, 12], [0, 2], range(3)):
        yield generate_instance(case, n, seed, n_sleeping=ns, M=2)
    for case, n, seed in itertools.product([1, 2], [18, 22], range(2)):
        yield generate_instance(case, n, seed, n_sleeping=2, M=n)


ALL = lambda: [from_ref(d) for d in ref_instances()] + list(real_instances())  # noqa: E731


def test_port_matches_reference():
    for d in ref_instances(60):
        mine, theirs = solve_robust(from_ref(d)), ref.solve_robust(d)
        assert theirs["feasible"] == (mine["status"] == "OPTIMAL")
        if theirs["feasible"]:
            assert mine["overtime_minutes"] == theirs["overtime_minutes"]
            assert mine["n_violated"] == theirs["violations"]
            assert mine["extra_moves"] == theirs["extra_moves"]
            assert abs(mine["regular"] - theirs["regular"]) < 1e-6
        se_mine, se_ref = solve_elastic(from_ref(d)), ref.solve_strict_elastic(d)
        assert se_ref["feasible"] == (se_mine["status"] == "OPTIMAL")
        if se_ref["feasible"]:
            assert abs(se_mine["coverage_term"] - se_ref["coverage"]) < 1e-6


def test_robust_feasible_hard_rules_and_o():
    for inst in ALL():
        res = solve_robust(inst)
        if not inst.robust_guaranteed_feasible():
            assert res["status"] == "PRECHECK_FAILED"
            continue
        assert res["status"] == "OPTIMAL", f"{inst.name}: {res['message']}"
        ev = evaluate(inst, res["assignment"], "robust")
        assert ev["feasible"], ev["violations"]                         # (1), (3), (6) hold
        assert res["o_var"] == max(0, ev["n_moves"] - inst.M) == ev["extra_moves"]


def test_robust_vs_strict_E():
    strict_ok = tied = 0
    for inst in ALL():
        se = solve_elastic(inst)
        if se["status"] != "OPTIMAL":
            continue
        strict_ok += 1
        se_ev = evaluate(inst, se["assignment"], "elastic")
        ro = solve_robust(inst)
        assert ro["n_violated"] <= se_ev["n_violated_9"]               # never more violations
        if se_ev["overtime_minutes"] == 0 and ro["n_violated"] == se_ev["n_violated_9"]:
            assert ro["overtime_minutes"] == 0
            assert ro["extra_moves"] == 0
            assert abs(ro["regular"] - se_ev["regular"]) < 1e-6
            tied += 1
    assert strict_ok > 20 and tied > 10


def test_tiny_conflict_instance():
    inst = from_ref(ref.tiny_conflict_instance())
    assert solve_elastic(inst)["status"] == "INFEASIBLE"
    ro = solve_robust(inst)
    assert ro["status"] == "OPTIMAL"
    assert (ro["n_moves"], ro["extra_moves"], ro["overtime_minutes"]) == (1, 0, 5)


def test_guarantee_condition():
    t = np.array([[5.0], [5.0]])
    g = np.array([[0.0, 10.0], [10.0, 0.0]])
    ok = build_instance([1.0], t, g, delta=[0, 1], h=[0, 1], s=[480, 480], C=[1, 1])
    full = build_instance([1.0], t, g, delta=[0, 1], h=[0, 0], s=[480, 480], S=[1], e=[0, 1], C=[1, 1])
    over = build_instance([1.0], t, g, delta=[0], h=[0], s=[480], e=[2, 0], C=[1, 1])
    assert ok.robust_guaranteed_feasible()
    assert not full.robust_guaranteed_feasible() and not over.robust_guaranteed_feasible()
    assert solve_robust(full)["status"] == "PRECHECK_FAILED"
    assert generate_instance(1, 6, 0, n_sleeping=2).meta["robust_guarantee_ok"] is True


@pytest.mark.parametrize("T", [10, 15, 30])
def test_T2_is_2T_in_every_model(T):
    """One area at 25 min from base 0 only. With cv = 0 it is in V2 iff 25 <= 2T.
    One ambulance is forced to sit at base 1, so H is infeasible and E/R violate iff 25 <= 2T."""
    t = np.array([[25.0], [100.0]])
    g = np.array([[0.0, 100.0], [100.0, 0.0]])
    inst = build_instance([1.0], t, g, delta=[1], h=[1], s=[0], C=[2, 2], M=0, T=T, cv=0.0)
    assert inst.T2 == 2 * T and ref.derived(ref_dict_of(inst))["T2"] == 2 * T
    in_V2 = 25 <= 2 * T
    assert inst.V2 == ([0] if in_V2 else [])
    assert solve_hard(inst)["status"] == ("INFEASIBLE" if in_V2 else "OPTIMAL")
    assert solve_elastic(inst)["n_violated"] == int(in_V2)
    # Model R may move the ambulance (soft M, overtime 100 + 100 - 0), violations come first
    ro = solve_robust(inst)
    assert ro["n_violated"] == 0 and ro["extra_moves"] == (1 if in_V2 else 0)
    with pytest.raises(TypeError):
        build_instance([1.0], t, g, delta=[1], h=[1], s=[0], T2=99)   # T2 is not an input


def ref_dict_of(inst):
    """Our Instance -> reference dict (inverse of from_ref)."""
    I, J, V = range(inst.nI), range(inst.nJ), range(inst.nV)
    return dict(I=list(I), J=list(J), V=list(V), S=set(inst.S), d={v: inst.d[v] for v in V}, q=inst.q,
                T=inst.T, alpha=inst.alpha, cv=inst.cv, lam=inst.lam, P=inst.P, M=inst.M,
                t={(j, v): inst.t[j, v] for j in J for v in V}, g={(j, k): inst.g[j, k] for j in J for k in J},
                delta={i: int(inst.delta[i]) for i in I}, h={i: int(inst.h[i]) for i in I},
                s={i: inst.s[i] for i in I}, e={j: int(inst.e[j]) for j in J}, C={j: int(inst.C[j]) for j in J})


def test_port_matches_reference_on_real_data():
    for inst in list(real_instances())[::4]:
        mine, theirs = solve_robust(inst), ref.solve_robust(ref_dict_of(inst))
        assert theirs["feasible"] and mine["status"] == "OPTIMAL"
        assert (mine["n_violated"], mine["overtime_minutes"], mine["extra_moves"]) == \
               (theirs["violations"], theirs["overtime_minutes"], theirs["extra_moves"])
        assert abs(mine["regular"] - theirs["regular"]) < 1e-6


@pytest.mark.parametrize("case,n,ns,seed", [(1, 18, 2, 0), (2, 22, 0, 1), (3, 20, 2, 2), (1, 6, 0, 3)])
def test_heading_home_shifts_have_no_forced_overtime(case, n, ns, seed):
    inst = generate_instance(case, n, seed, n_sleeping=ns)
    assert inst.meta["shift_mode"] == "heading_home"
    assert all(inst.ot[i, inst.h[i]] == 0 for i in range(inst.nI))          # going home is never late
    old = generate_instance(case, n, seed, n_sleeping=ns, shift_mode="uniform")
    late = old.s < old.g[old.delta, old.h]
    assert np.array_equal(inst.delta, np.where(late, old.h, old.delta))      # only late crews change
    assert np.array_equal(inst.s, old.s) and np.array_equal(inst.h, old.h)
