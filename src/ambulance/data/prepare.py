"""Build the per-case processed data from the raw workbook.

Output per case (data/processed/case{c}/):
    areas.csv        v, name, prefecture, lat, lon, population, d_v, demand, lambda, service time
    bases.csv        j, name, area_v, lat, lon
    t_jv_p1.csv / t_jv_p2.csv   base -> area travel time (minutes)
    g_jj_p1.csv / g_jj_p2.csv   base -> base travel time (minutes)
    a_jv.csv         1 if t_jv <= T (chosen period)
    summary.json     checks and headline numbers
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import loader


@dataclass
class CaseData:
    case: int
    areas: pd.DataFrame          # index v (1..199)
    bases: pd.DataFrame          # index j (1..|J|)
    t: dict[int, pd.DataFrame]   # period -> |J| x |V|
    g: dict[int, pd.DataFrame]   # period -> |J| x |J|

    @property
    def d(self) -> pd.Series:
        return self.areas["d_v"]


def build_areas(raw: Path) -> pd.DataFrame:
    areas = loader.read_areas(raw)
    areas.insert(1, "prefecture", loader.read_prefectures(raw))
    areas["population"] = loader.read_population(raw)
    areas["d_v"] = areas["population"] / areas["population"].sum()
    areas = areas.join(loader.read_demand(raw)).join(loader.read_arrival_rates(raw))
    areas["service_time_min"] = loader.read_service_time(raw)
    if areas.isna().any().any():
        raise ValueError("missing values after joining area tables")
    if len(areas) != loader.N_AREAS:
        raise ValueError(f"expected {loader.N_AREAS} areas, got {len(areas)}")
    return areas


def load_case(raw: Path, case: int, areas: pd.DataFrame | None = None) -> CaseData:
    areas = build_areas(raw) if areas is None else areas
    bases = loader.read_sites(raw, case)
    bases = bases.join(areas[["lat", "lon"]], on="area_v")
    t1, t2, t_names = loader.read_site_area_times(raw, case)
    g1, g2, g_names = loader.read_site_site_times(raw, case)

    # Consistency: base-to-base time must equal base-to-(area of other base) time.
    # This confirms that Tables 9-14 list the sites in the order of Table 7.
    for t, g in ((t1, g1), (t2, g2)):
        tt = t.loc[:, bases["area_v"].values].values
        if not np.array_equal(tt, g.values):
            raise ValueError(f"case {case}: g_jj' does not match t_j,area(j')")
    return CaseData(case, areas, bases, {1: t1, 2: t2}, {1: g1, 2: g2})


def coverage_matrix(t: pd.DataFrame, T: float) -> pd.DataFrame:
    """a_jv = 1 if base j reaches area v within T minutes."""
    return (t <= T).astype(int)


def coverage_summary(cd: CaseData, period: int, T_values) -> list[dict]:
    rows = []
    for T in T_values:
        covered = coverage_matrix(cd.t[period], T).values.any(axis=0)
        rows.append({"T": T, "areas_uncovered": int((~covered).sum()),
                     "demand_covered": round(float(cd.d.values[covered].sum()), 4)})
    return rows


def estimate_q(areas: pd.DataFrame, n_ambulances: int, period: int = 1) -> float:
    """Region-specific busy fraction: expected busy ambulances / |I|.

    expected load = sum_v (lambda_ALS + lambda_BLS)[per hour] * service time[h].
    """
    lam = areas[f"lambda_als_p{period}"] + areas[f"lambda_bls_p{period}"]
    load = float((lam * areas["service_time_min"] / 60.0).sum())
    return load / n_ambulances


def write_case(cd: CaseData, out_dir: Path, period: int, T: float, T_values) -> dict:
    out = out_dir / f"case{cd.case}"
    out.mkdir(parents=True, exist_ok=True)
    cd.areas.to_csv(out / "areas.csv")
    cd.bases.to_csv(out / "bases.csv")
    for p in (1, 2):
        cd.t[p].to_csv(out / f"t_jv_p{p}.csv")
        cd.g[p].to_csv(out / f"g_jj_p{p}.csv")
    a = coverage_matrix(cd.t[period], T)
    a.to_csv(out / "a_jv.csv")

    covered = a.values.any(axis=0)
    g = cd.g[period].values
    summary = {
        "case": cd.case,
        "n_bases": len(cd.bases),
        "n_areas": len(cd.areas),
        "period": period,
        "T": T,
        "sum_d_v": float(cd.d.sum()),
        "areas_without_base_within_T": int((~covered).sum()),
        "uncovered_area_ids": [int(v) for v in cd.areas.index[~covered]],
        "demand_share_covered": float(cd.d.values[covered].sum()),
        "coverage_by_T": coverage_summary(cd, period, T_values),
        "t_min_max": [float(cd.t[period].values.min()), float(cd.t[period].values.max())],
        "g_diagonal_raw": sorted({float(x) for x in np.diag(g)}),
        "g_max_asymmetry_min": float(np.abs(g - g.T).max()),
        "period2_minus_period1_min": sorted({float(x) for x in np.unique(cd.t[2].values - cd.t[1].values)}),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary
