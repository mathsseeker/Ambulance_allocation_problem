"""Values computed from data before solving (not decisions)."""
from __future__ import annotations

import numpy as np


def base_travel_matrix(g_raw: np.ndarray) -> np.ndarray:
    """g_jj' with a zero diagonal.

    The dataset stores 3 min (period 1) on the diagonal: the within-area driving
    time. Staying at your own base costs no move, so we set it to 0.
    """
    g = np.array(g_raw, dtype=float)
    np.fill_diagonal(g, 0.0)
    return g


def move_cost(g: np.ndarray, delta: list[int]) -> np.ndarray:
    """c_ij = g[delta_i, j]  (teleportation assumption), |I| x |J|."""
    return g[np.asarray(delta) - 1, :]


def move_and_return(g: np.ndarray, delta: list[int], home: list[int]) -> np.ndarray:
    """r_ij = c_ij + g[j, h_i], |I| x |J|."""
    c = move_cost(g, delta)
    return c + g[:, np.asarray(home) - 1].T


def coverage_levels(n_ambulances: int, e: list[int]) -> list[int]:
    """K = {1, ..., |I| + sum_j e_j}."""
    return list(range(1, n_ambulances + sum(e) + 1))
