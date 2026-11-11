"""Model R on the Edmonton instance (Ingolfsson data, data/edmonton/processed).

Reuses the project's Model R code unchanged:
    ambulance.instance.build_instance  -> a, b, V2, c, r, ot, kbar (= ymax)
    ambulance.model.solve_robust       -> Gurobi hierarchical multi-objective
    ambulance.evaluate.evaluate        -> independent check of every solution

This file only (1) loads the Edmonton region data and (2) draws the ambulance state
(I, delta, h, s, S, e) with the same rules as ambulance.instance.generate_instance,
but with Edmonton's real capacities C_j instead of the default C_j = 2.
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ambulance.instance import Instance, build_instance  # noqa: E402

DATA = ROOT / "data" / "edmonton" / "processed"


@dataclass(frozen=True)
class Edmonton:
    d: np.ndarray        # |V|        demand share, sums to 1
    t: np.ndarray        # |J| x |V|  mean response time (min)
    sigma: np.ndarray    # |J| x |V|  std. dev. of response time (min)
    g: np.ndarray        # |J| x |J|  base-to-base (min), approx_nearest_node, zero diagonal
    C: np.ndarray        # |J|        real station capacities
    cv: float            # median sigma / t (params.json)
    params: dict

    @property
    def nJ(self) -> int: return self.t.shape[0]
    @property
    def nV(self) -> int: return self.t.shape[1]


@lru_cache(maxsize=1)
def load_edmonton() -> Edmonton:
    def rows(name):
        with open(DATA / name, newline="") as f:
            return list(csv.DictReader(f))

    areas = rows("areas.csv")
    bases = rows("bases.csv")
    nV, nJ = len(areas), len(bases)
    assert [int(r["v"]) for r in areas] == list(range(1, nV + 1))
    assert [int(r["j"]) for r in bases] == list(range(1, nJ + 1))
    d = np.array([float(r["d_v"]) for r in areas])
    C = np.array([int(r["C_j"]) for r in bases])
    t = np.full((nJ, nV), np.nan)
    sigma = np.full((nJ, nV), np.nan)
    for r in rows("t_base_area.csv"):
        j, v = int(r["j"]) - 1, int(r["v"]) - 1
        t[j, v], sigma[j, v] = float(r["t_min"]), float(r["sigma_min"])
    g = np.full((nJ, nJ), np.nan)
    for r in rows("g_base_base.csv"):
        g[int(r["j"]) - 1, int(r["j2"]) - 1] = float(r["g_min"])
    assert not np.isnan(t).any() and not np.isnan(sigma).any() and not np.isnan(g).any()
    assert abs(d.sum() - 1) < 1e-9 and np.all(np.diag(g) == 0)
    params = json.loads((DATA / "params.json").read_text())
    return Edmonton(d=d, t=t, sigma=sigma, g=g, C=C, cv=float(params["model_r"]["c_v"]), params=params)


def draw_state(ed: Edmonton, n_ambulances: int, seed: int, n_sleeping: int = 0,
               shift_max: int = 480, shift_mode: str = "heading_home"):
    """Same rules as ambulance.instance.generate_instance (spec 6b):
    S random (|S| = n_sleeping), e_j = 1 on S, delta uniform over all bases (may be in S),
    h uniform over awake bases, s uniform integer in [0, shift_max];
    'heading_home': a crew that cannot reach home before its shift ends has delta = h."""
    nJ = ed.nJ
    rng = np.random.default_rng([2008, n_ambulances, n_sleeping, seed])   # 2008: Edmonton stream
    S = sorted(int(j) for j in rng.choice(nJ, size=n_sleeping, replace=False)) if n_sleeping else []
    e = np.array([1 if j in S else 0 for j in range(nJ)])
    awake = [j for j in range(nJ) if j not in S]
    delta = rng.integers(0, nJ, size=n_ambulances)
    h = rng.choice(awake, size=n_ambulances, replace=True)
    s = rng.integers(0, shift_max + 1, size=n_ambulances)
    if shift_mode == "heading_home":
        delta = np.where(s < ed.g[delta, h], h, delta)
    elif shift_mode != "uniform":
        raise ValueError(shift_mode)
    return delta, h, s, S, e


def edmonton_instance(n_ambulances: int, seed: int, n_sleeping: int = 0, T: float = 8.0,
                      q: float = 0.3, alpha: float = 0.97, M: int = 2, lam: float = 0.0,
                      P: float = 0.0, cv: float | None = None, sigma_mode: str = "cv",
                      shift_mode: str = "heading_home") -> Instance:
    """sigma_mode='cv'        : b_jv = 1 if t_jv (1 + z cv) <= 2T   (Model R as formulated)
       sigma_mode='empirical' : b_jv = 1 if t_jv + z sigma_jv <= 2T (Edmonton's own sigma)"""
    ed = load_edmonton()
    cv = ed.cv if cv is None else cv
    delta, h, s, S, e = draw_state(ed, n_ambulances, seed, n_sleeping, shift_mode=shift_mode)
    name = f"edmonton_T{T:g}_I{n_ambulances}_S{n_sleeping}_seed{seed}_{sigma_mode}"
    inst = build_instance(ed.d, ed.t, ed.g, delta, h, s, S=S, e=e, C=ed.C, name=name,
                          T=T, q=q, alpha=alpha, M=M, lam=lam, P=P, cv=cv,
                          meta={"n_ambulances": n_ambulances, "n_sleeping": n_sleeping, "seed": seed,
                                "T": T, "sigma_mode": sigma_mode, "shift_mode": shift_mode})
    if sigma_mode == "empirical":
        inst.b = (ed.t + inst.z * ed.sigma <= inst.T2).astype(int)
        inst.V2 = [int(v) for v in np.flatnonzero(inst.b.any(axis=0))]
    elif sigma_mode != "cv":
        raise ValueError(sigma_mode)
    inst.meta["robust_guarantee_ok"] = inst.robust_guaranteed_feasible()
    return inst
