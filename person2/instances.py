"""Build Model R instances for testing the heuristic.

TEMPORARY: this is only so Person 2 can test. Person 3 will build the
official instances; they must be the same `Instance` object (Person 1's
`src/ambulance/instance.py`), so the heuristic will not need to change.

    load_map("madrid" | "edmonton" | "fez", case=1)  -> the map: d, t, g, C
    random_instance(map, n_ambulances, seed, ...)    -> an Instance with a random situation
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
from ambulance.instance import build_instance  # noqa: E402  (Person 1's Instance)

DATA = REPO / "data"


def load_map(dataset, case=1):
    """Return dict(d, t, g, C) for one dataset. C is None when the data has no capacities."""
    if dataset == "madrid":
        folder = DATA / "madrid" / "processed"
        d = pd.read_csv(folder / "areas.csv").d_v.values
        t = pd.read_csv(folder / "t_base_area.csv").pivot(index="j", columns="v", values="t_min").values
        g = pd.read_csv(folder / "g_base_base.csv").pivot(index="j", columns="j2", values="g_min").values
        C = pd.read_csv(folder / "bases.csv").C_j.values
    elif dataset == "edmonton":
        folder = DATA / "edmonton" / "processed"
        d = pd.read_csv(folder / "areas.csv").d_v.values
        t = pd.read_csv(folder / "t_base_area.csv").pivot(index="j", columns="v", values="t_min").values
        g = pd.read_csv(folder / "g_base_base.csv").pivot(index="j", columns="j2", values="g_min").values
        C = pd.read_csv(folder / "bases.csv").C_j.values
    elif dataset == "fez":
        folder = DATA / "fez_meknes" / "processed" / f"case{case}"
        d = pd.read_csv(folder / "areas.csv").d_v.values
        t = pd.read_csv(folder / "t_jv_p1.csv", index_col=0).values      # period 1
        g = pd.read_csv(folder / "g_jj_p1.csv", index_col=0).values
        C = None                                                       # not in the dataset
    else:
        raise ValueError(f"unknown dataset {dataset!r}")

    g = np.array(g, dtype=float)
    np.fill_diagonal(g, 0)      # Model R: g_jj = 0 (the Fez-Meknes file has 3 min)
    d = d / d.sum()             # shares must add up to 1
    return {"d": d, "t": t, "g": g, "C": C}


def random_instance(region, n_ambulances, seed, n_sleeping=0, capacity=None,
                    T=30.0, M=2, lam=0.0, cv=0.2, shift_max=480):
    """A random situation on a map.

    - S: `n_sleeping` random bases have a sleeping crew (one fixed ambulance each: e_j = 1)
    - delta_i: random base (may be a sleeping base: that ambulance is then forced to move)
    - h_i: random base without a sleeping crew
    - s_i: random minutes left in the shift, 0 .. shift_max
    - C_j: `capacity` if given, else the map's capacities, else 2 (Model R default)
    """
    rng = np.random.default_rng(seed)
    nJ = region["t"].shape[0]

    S = [int(j) for j in rng.choice(nJ, n_sleeping, replace=False)]
    awake = [j for j in range(nJ) if j not in S]
    e = np.zeros(nJ, int)
    e[S] = 1

    delta = rng.choice(nJ, n_ambulances)
    h = rng.choice(awake, n_ambulances)
    s = rng.integers(0, shift_max + 1, n_ambulances)

    if capacity is not None:
        C = np.full(nJ, capacity)
    elif region["C"] is not None:
        C = np.array(region["C"])
    else:
        C = np.full(nJ, 2)

    return build_instance(region["d"], region["t"], region["g"], delta, h, s, S=S, e=e, C=C,
                          name=f"seed{seed}", T=T, M=M, lam=lam, cv=cv)
