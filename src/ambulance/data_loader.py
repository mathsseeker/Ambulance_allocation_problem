"""Region data for one base case: V, J, d, t, g (spec section 6a).

Reads the raw Excel file once per case (cached). Workbook findings (units, order) are
in docs/data_guide.md: times are minutes, site order of Tables 9-14 equals Table 7.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from .data import loader, prepare

ROOT = Path(__file__).resolve().parents[2]
RAW_FILE = ROOT / "data" / "raw" / "fez_meknes_ambulance_dataset.xlsx"


@dataclass(frozen=True)
class RegionData:
    case: int
    V: list[int]          # dataset area ids (1..199); position = model index v
    J: list[int]          # dataset base ids (1..|J|); position = model index j
    d: np.ndarray         # |V|, sums to 1
    t: np.ndarray         # |J| x |V| minutes
    g: np.ndarray         # |J| x |J| minutes, zero diagonal
    area_names: list[str]
    base_names: list[str]


@lru_cache(maxsize=None)
def load_case(case: int, period: int = 1, path: str = str(RAW_FILE)) -> RegionData:
    if case not in loader.CASE_SIZES:
        raise ValueError(f"case must be 1, 2 or 3, got {case}")
    cd = prepare.load_case(Path(path), case)
    g = cd.g[period].values.astype(float)
    np.fill_diagonal(g, 0.0)   # dataset stores 3 min (within-area time); staying costs nothing
    return RegionData(
        case=case,
        V=list(cd.areas.index), J=list(cd.bases.index),
        d=cd.areas["d_v"].values.astype(float),
        t=cd.t[period].values.astype(float), g=g,
        area_names=list(cd.areas["name"]), base_names=list(cd.bases["name"]),
    )
