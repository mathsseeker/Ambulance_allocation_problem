"""Checks on the prepared data. Run: pytest  (after scripts/prepare_data.py)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ambulance.data import derived  # noqa: E402

PROCESSED = ROOT / "data" / "fez_meknes" / "processed"
SIZES = {1: 18, 2: 22, 3: 40}


@pytest.mark.parametrize("case", [1, 2, 3])
def test_case_shapes(case):
    d = PROCESSED / f"case{case}"
    areas = pd.read_csv(d / "areas.csv", index_col=0)
    t = pd.read_csv(d / "t_jv_p1.csv", index_col=0)
    g = pd.read_csv(d / "g_jj_p1.csv", index_col=0)
    assert len(areas) == 199
    assert abs(areas["d_v"].sum() - 1) < 1e-12
    assert t.shape == (SIZES[case], 199)
    assert g.shape == (SIZES[case], SIZES[case])
    assert not t.isna().any().any()


def test_derived_costs():
    g = derived.base_travel_matrix(np.array([[3, 5, 9], [6, 3, 2], [8, 1, 3]]))
    c = derived.move_cost(g, [1, 3])
    r = derived.move_and_return(g, [1, 3], [2, 2])
    assert c.tolist() == [[0, 5, 9], [8, 1, 0]]
    assert r.tolist() == [[5, 5, 10], [13, 1, 1]]
