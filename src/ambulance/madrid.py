"""Madrid region (data/madrid/processed): one district + neighbouring SAMUR-PC bases.

    load_madrid() -> MadridData (d, t, g, C as numpy arrays, 0-based positions)
    generate_madrid_instance(n_ambulances, seed, ...) -> Instance (same rules as generate_instance)

Indices in the CSVs are 1-based (j, v); here position p = id - 1. Times are OSRM free-flow car
minutes. C_j is an ESTIMATE (see data/madrid/README.md); pass capacity=k to override it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .instance import Instance, draw_state

ROOT = Path(__file__).resolve().parents[2]
MADRID_DIR = ROOT / "data" / "madrid" / "processed"
SEED_TAG = 1000   # first rng key, so Madrid states never coincide with Fez-Meknes cases 1-3


@dataclass(frozen=True)
class MadridData:
    district: str
    V: list[int]
    J: list[int]
    d: np.ndarray        # |V|, sums to 1
    t: np.ndarray        # |J| x |V| minutes
    g: np.ndarray        # |J| x |J| minutes, zero diagonal
    C: np.ndarray        # |J| estimated capacity
    area_names: list[str]
    base_names: list[str]


@lru_cache(maxsize=None)
def load_madrid(path: str = str(MADRID_DIR)) -> MadridData:
    p = Path(path)
    areas = pd.read_csv(p / "areas.csv").sort_values("v")
    bases = pd.read_csv(p / "bases.csv").sort_values("j")
    tb = pd.read_csv(p / "t_base_area.csv")
    gb = pd.read_csv(p / "g_base_base.csv")
    params = json.loads((p / "params.json").read_text())
    V, J = areas["v"].tolist(), bases["j"].tolist()
    t = tb.pivot(index="j", columns="v", values="t_min").loc[J, V].to_numpy(float)
    g = gb.pivot(index="j", columns="j2", values="g_min").loc[J, J].to_numpy(float).copy()
    if np.isnan(t).any() or np.isnan(g).any():
        raise ValueError("missing travel times in data/madrid/processed")
    if bases["C_j"].isna().any():
        raise ValueError("C_j missing in bases.csv; pass capacity= to generate_madrid_instance")
    np.fill_diagonal(g, 0.0)
    d = areas["d_v"].to_numpy(float)
    return MadridData(district=params["district"], V=V, J=J, d=d / d.sum(), t=t, g=g,
                      C=bases["C_j"].to_numpy(int), area_names=areas["barrio"].tolist(),
                      base_names=bases["name"].tolist())


def generate_madrid_instance(n_ambulances: int, seed: int, n_sleeping: int = 0, capacity: int | None = None,
                             shift_max: int = 480, shift_mode: str = "heading_home", **params) -> Instance:
    """Same generator rules as generate_instance (spec 6b). capacity=None uses the C_j column."""
    md = load_madrid()
    rng = np.random.default_rng([SEED_TAG, n_ambulances, n_sleeping, seed])
    delta, h, s, S, e = draw_state(md.g, rng, n_ambulances, n_sleeping, shift_max, shift_mode)
    C = md.C.copy() if capacity is None else np.full(len(md.J), capacity)
    cap = "est" if capacity is None else str(capacity)
    name = f"madrid_I{n_ambulances}_S{n_sleeping}_C{cap}_seed{seed}"
    inst = Instance(name=name, d=md.d, t=md.t, g=md.g, delta=delta, h=h, s=s, S=S, e=e, C=C,
                    meta={"region": "madrid", "district": md.district, "n_ambulances": n_ambulances,
                          "n_sleeping": n_sleeping, "seed": seed, "shift_mode": shift_mode,
                          "capacity": cap}, **params)
    inst.meta["robust_guarantee_ok"] = inst.robust_guaranteed_feasible()
    return inst
