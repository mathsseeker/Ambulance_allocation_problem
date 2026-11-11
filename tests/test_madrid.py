"""Madrid instance (data/madrid/processed) loads correctly and Model R behaves as on Fez-Meknes."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ambulance.evaluate import evaluate  # noqa: E402
from ambulance.madrid import generate_madrid_instance, load_madrid  # noqa: E402
from ambulance.model import solve_elastic, solve_robust  # noqa: E402


def test_load_madrid_shapes():
    md = load_madrid()
    assert md.t.shape == (len(md.J), len(md.V)) == (8, 8)
    assert md.g.shape == (8, 8) and np.all(np.diag(md.g) == 0)
    assert abs(md.d.sum() - 1) < 1e-9 and (md.d > 0).all()
    assert (md.t > 0).all() and (md.C == 5).all()


def test_same_seed_same_state():
    a = generate_madrid_instance(6, 3, n_sleeping=2)
    b = generate_madrid_instance(6, 3, n_sleeping=2, T=15, alpha=0.99)
    assert (a.delta == b.delta).all() and (a.h == b.h).all() and a.S == b.S


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("T", [10, 15, 30])
def test_robust_never_worse_than_elastic(seed, T):
    inst = generate_madrid_instance(6, seed, n_sleeping=2, M=2, T=T)
    r = solve_robust(inst)
    assert r["status"] == "OPTIMAL"
    ev = evaluate(inst, r["assignment"], "robust")
    assert ev["feasible"] and ev["extra_moves"] == r["o_var"]
    e = solve_elastic(inst)
    if e["assignment"] is not None:
        assert r["n_violated"] <= e["n_violated"]
