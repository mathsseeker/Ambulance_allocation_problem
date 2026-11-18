
from pathlib import Path
from functools import lru_cache
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ambulance.instance import (
    generate_instance,
    build_instance,
    draw_state,
)
from ambulance.madrid import generate_madrid_instance


@lru_cache(maxsize=1)
def load_edmonton():
    """Load Edmonton's processed geographical data."""
    folder = ROOT / "data" / "edmonton" / "processed"

    areas = pd.read_csv(folder / "areas.csv").sort_values("v")
    bases = pd.read_csv(folder / "bases.csv").sort_values("j")

    J = bases["j"].tolist()
    V = areas["v"].tolist()

    t = (
        pd.read_csv(folder / "t_base_area.csv")
        .pivot(index="j", columns="v", values="t_min")
        .loc[J, V]
        .to_numpy(float)
    )

    g = (
        pd.read_csv(folder / "g_base_base.csv")
        .pivot(index="j", columns="j2", values="g_min")
        .loc[J, J]
        .to_numpy(float)
        .copy()
    )

    np.fill_diagonal(g, 0.0)

    d = areas["d_v"].to_numpy(float)
    d = d / d.sum()

    C = bases["C_j"].to_numpy(int)

    return d, t, g, C


def create_instance(
    region,
    n_ambulances,
    seed,
    n_sleeping=2,
    T=30,
    capacity=None,
    case=1,
    M=2,
    q=0.3,
    alpha=0.97,
    cv=0.2,
    lam=0.0,
    P=0.0,
    shift_mode="heading_home",
):
    """Return a Model R Instance for any supported region."""

    params = dict(
        T=T, M=M, q=q, alpha=alpha,
        cv=cv, lam=lam, P=P
    )

    if region == "fez":
        return generate_instance(
            case=case,
            n_ambulances=n_ambulances,
            seed=seed,
            n_sleeping=n_sleeping,
            capacity=2 if capacity is None else capacity,
            shift_mode=shift_mode,
            **params,
        )

    if region == "madrid":
        return generate_madrid_instance(
            n_ambulances=n_ambulances,
            seed=seed,
            n_sleeping=n_sleeping,
            capacity=capacity,
            shift_mode=shift_mode,
            **params,
        )

    if region == "edmonton":
        d, t, g, native_C = load_edmonton()

        # Separate RNG namespace for Edmonton
        rng = np.random.default_rng(
            [2000, n_ambulances, n_sleeping, seed]
        )

        delta, h, s, S, e = draw_state(
            g, rng, n_ambulances,
            n_sleeping, 480, shift_mode
        )

        C = (
            native_C.copy()
            if capacity is None
            else np.full(len(native_C), capacity, dtype=int)
        )

        return build_instance(
            d=d, t=t, g=g,
            delta=delta, h=h, s=s,
            S=S, e=e, C=C,
            name=f"edmonton_I{n_ambulances}_S{n_sleeping}_seed{seed}",
            **params,
        )

    raise ValueError(f"Unknown region: {region}")
