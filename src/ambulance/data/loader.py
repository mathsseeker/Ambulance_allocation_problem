"""Read the raw Fez-Meknes Excel workbook (Frichi, Jawab & Aboueljinane, 2022).

The workbook is never modified. Every reader returns plain pandas objects with
1-based dataset indices kept as the index, so they can be cross-checked against
the Excel file by eye.

Sheet layout (checked on the real file, 11 Nov 2026):
    sheet 1  Table 1  prefecture -> area index ranges
    sheet 2  Table 2  area index, name, latitude, longitude
    sheet 3  Table 3  area index, population
    sheet 4  Table 4  yearly demand per area, ALS/BLS x period 1/2
    sheet 5  Table 5  arrival rate per hour, ALS/BLS x period 1/2
    sheet 6  Table 6  service time per area (minutes)
    sheet 7  Table 7  candidate sites for the 3 cases (j index -> area index)
    sheet 8  Table 8  ambulance-number scenarios
    sheets 9-11  Tables 9-11   site -> area travel times, period 1 and 2 (minutes)
    sheets 12-14 Tables 12-14  site -> site travel times, period 1 and 2 (minutes)
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

N_AREAS = 199
CASE_SIZES = {1: 18, 2: 22, 3: 40}
# Sheet positions of the travel-time tables per case.
SITE_AREA_SHEET = {1: 9, 2: 10, 3: 11}
SITE_SITE_SHEET = {1: 12, 2: 13, 3: 14}
# Column groups of Table 7 per case: (name col, j col, i col).
TABLE7_COLS = {1: ("C", "D", "E"), 2: ("G", "H", "I"), 3: ("K", "L", "M")}


@lru_cache(maxsize=2)
def _workbook(path: str) -> openpyxl.Workbook:
    return openpyxl.load_workbook(path, data_only=True, read_only=False)


def _rows(path: Path, sheet: int):
    ws = _workbook(str(path)).worksheets[sheet]
    for row in ws.iter_rows():
        yield [c for c in row if c.value is not None]


def _int_label(value) -> int | None:
    """'i=12' -> 12, 'j=3' -> 3, 12 -> 12."""
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        m = re.fullmatch(r"\s*[ijIJ]?\s*=?\s*(\d+)\s*", value)
        if m:
            return int(m.group(1))
    return None


# --------------------------------------------------------------------------- areas
def read_prefectures(path: Path) -> pd.Series:
    """Table 1: area index -> prefecture/province name."""
    out: dict[int, str] = {}
    current = None
    for cells in _rows(path, 1):
        by_col = {c.column_letter: c.value for c in cells}
        e = by_col.get("E")
        if not isinstance(e, (str, int)) or not re.fullmatch(r"[\d;\s]+", str(e)):
            continue
        if "C" in by_col:
            current = str(by_col["C"]).strip()
        for tok in str(by_col["E"]).split(";"):
            if tok.strip():
                out[int(tok)] = current
    s = pd.Series(out, name="prefecture").sort_index()
    s.index.name = "v"
    return s


def read_areas(path: Path) -> pd.DataFrame:
    """Table 2: index, name, latitude, longitude."""
    recs = []
    for cells in _rows(path, 2):
        by_col = {c.column_letter: c.value for c in cells}
        idx = _int_label(by_col.get("C"))
        if idx is None or "E" not in by_col:
            continue
        recs.append({"v": idx, "name": str(by_col["D"]).strip(),
                     "lat": float(by_col["E"]), "lon": float(by_col["F"])})
    return pd.DataFrame(recs).set_index("v").sort_index()


def read_population(path: Path) -> pd.Series:
    """Table 3: area index -> population."""
    out = {}
    for cells in _rows(path, 3):
        by_col = {c.column_letter: c.value for c in cells}
        idx = _int_label(by_col.get("D"))
        pop = by_col.get("E")
        if idx is not None and isinstance(pop, (int, float)):
            out[idx] = int(pop)
    s = pd.Series(out, name="population").sort_index()
    s.index.name = "v"
    return s


def read_demand(path: Path) -> pd.DataFrame:
    """Table 4: yearly demand (requests/year) per area, ALS/BLS x period."""
    recs = []
    for cells in _rows(path, 4):
        by_col = {c.column_letter: c.value for c in cells}
        idx = _int_label(by_col.get("C"))
        if idx is None or not isinstance(by_col.get("E"), (int, float)):
            continue
        recs.append({"v": idx, "demand_als_p1": by_col["E"], "demand_als_p2": by_col["F"],
                     "demand_bls_p1": by_col["G"], "demand_bls_p2": by_col["H"]})
    return pd.DataFrame(recs).set_index("v").sort_index()


def read_arrival_rates(path: Path) -> pd.DataFrame:
    """Table 5: arrival rate (requests/hour) per area, ALS/BLS x period."""
    recs = []
    for cells in _rows(path, 5):
        by_col = {c.column_letter: c.value for c in cells}
        idx = _int_label(by_col.get("B"))
        if idx is None or not isinstance(by_col.get("C"), (int, float)):
            continue
        recs.append({"v": idx, "lambda_als_p1": by_col["C"], "lambda_als_p2": by_col["D"],
                     "lambda_bls_p1": by_col["E"], "lambda_bls_p2": by_col["F"]})
    return pd.DataFrame(recs).set_index("v").sort_index()


def read_service_time(path: Path) -> pd.Series:
    """Table 6: service time per area (minutes)."""
    out = {}
    for cells in _rows(path, 6):
        by_col = {c.column_letter: c.value for c in cells}
        idx = _int_label(by_col.get("C"))
        if idx is not None and isinstance(by_col.get("E"), (int, float)):
            out[idx] = float(by_col["E"])
    s = pd.Series(out, name="service_time_min").sort_index()
    s.index.name = "v"
    return s


# --------------------------------------------------------------------------- sites
def read_sites(path: Path, case: int) -> pd.DataFrame:
    """Table 7: candidate sites of one case. Index j (1-based) -> name, area index."""
    name_c, j_c, i_c = TABLE7_COLS[case]
    recs = []
    for cells in _rows(path, 7):
        by_col = {c.column_letter: c.value for c in cells}
        j = _int_label(by_col.get(j_c))
        i = _int_label(by_col.get(i_c))
        if j is not None and i is not None:
            recs.append({"j": j, "name": str(by_col[name_c]).strip(), "area_v": i})
    df = pd.DataFrame(recs).set_index("j").sort_index()
    assert len(df) == CASE_SIZES[case], f"case {case}: {len(df)} sites"
    return df


def read_fleet_options(path: Path) -> pd.DataFrame:
    """Table 8: ambulance-number scenarios per option and period."""
    recs, option = [], None
    for cells in _rows(path, 8):
        by_col = {c.column_letter: c.value for c in cells}
        if isinstance(by_col.get("B"), str) and re.fullmatch(r"\s*Option\s+\d+\s*", by_col["B"]):
            option = int(by_col["B"].split()[-1])
        if option and isinstance(by_col.get("C"), int) and isinstance(by_col.get("F"), int):
            recs.append({"option": option, "period": by_col["C"], "als": by_col["D"],
                         "bls": by_col["E"], "total": by_col["F"]})
    return pd.DataFrame(recs)


# --------------------------------------------------------------------- travel times
def _read_period_matrix(path: Path, sheet: int, n_rows: int, n_cols: int):
    """Generic reader for the travel-time sheets.

    The header row holds the column indices 1..n_cols twice (period 1 block then
    period 2 block). Data rows start with the row index and the row name.
    Returns (period1, period2, row_names, col_names) as DataFrames/lists.
    """
    rows = list(_rows(path, sheet))
    header_pos = None
    for k, cells in enumerate(rows):
        ints = [c for c in cells if _int_label(c.value) is not None and not isinstance(c.value, str)]
        if len(ints) == 2 * n_cols:
            header_pos = k
            break
    if header_pos is None:
        raise ValueError(f"sheet {sheet}: header with {2*n_cols} indices not found")

    header = [c for c in rows[header_pos] if isinstance(c.value, (int, float))]
    labels = [int(c.value) for c in header]
    expected = list(range(1, n_cols + 1)) * 2
    if labels != expected:
        raise ValueError(f"sheet {sheet}: unexpected header order")
    cols_p1 = [c.column for c in header[:n_cols]]
    cols_p2 = [c.column for c in header[n_cols:]]
    col_names_cells = {c.column: c.value for c in rows[header_pos + 1]}
    col_names = [str(col_names_cells.get(c, "")).strip() for c in cols_p1]

    ws = _workbook(str(path)).worksheets[sheet]
    p1, p2, row_names, row_idx = [], [], [], []
    for cells in rows[header_pos + 2:]:
        if len(row_idx) == n_rows:
            break
        first = cells[0]
        idx = _int_label(first.value)
        if idx is None:
            continue
        r = first.row
        row_idx.append(idx)
        row_names.append(str(ws.cell(r, first.column + 1).value).strip())
        p1.append([ws.cell(r, c).value for c in cols_p1])
        p2.append([ws.cell(r, c).value for c in cols_p2])
    if row_idx != list(range(1, n_rows + 1)):
        raise ValueError(f"sheet {sheet}: row indices are not 1..{n_rows}")

    idx = pd.Index(row_idx, name="j")
    cols = pd.Index(range(1, n_cols + 1))
    m1 = pd.DataFrame(np.array(p1, dtype=float), index=idx, columns=cols)
    m2 = pd.DataFrame(np.array(p2, dtype=float), index=idx, columns=cols)
    return m1, m2, row_names, col_names


def read_site_area_times(path: Path, case: int):
    """Tables 9-11: t_jv in minutes. Returns (period1, period2, site_names)."""
    m1, m2, rn, _ = _read_period_matrix(path, SITE_AREA_SHEET[case], CASE_SIZES[case], N_AREAS)
    m1.columns.name = m2.columns.name = "v"
    return m1, m2, rn


def read_site_site_times(path: Path, case: int):
    """Tables 12-14: g_jj' in minutes. Returns (period1, period2, site_names)."""
    n = CASE_SIZES[case]
    m1, m2, rn, _ = _read_period_matrix(path, SITE_SITE_SHEET[case], n, n)
    m1.columns.name = m2.columns.name = "j2"
    return m1, m2, rn
