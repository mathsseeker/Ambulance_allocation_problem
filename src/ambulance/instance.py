"""Relocation instance: region data + ambulance state + computed parameters (spec 3, 6b).

All indices are 0-based positions: i in range(nI), j in range(nJ), v in range(nV).
`build_instance` takes raw arrays (used by tests); `generate_instance` draws the
ambulance state for a real case with a fixed seed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm


@dataclass
class Instance:
    name: str
    # region
    d: np.ndarray           # |V|
    t: np.ndarray           # |J| x |V|
    g: np.ndarray           # |J| x |J|, zero diagonal
    # ambulance state
    delta: np.ndarray       # |I|
    h: np.ndarray           # |I|
    s: np.ndarray           # |I|
    S: list[int]            # bases with a sleeping crew
    e: np.ndarray           # |J|
    C: np.ndarray           # |J|
    # parameters
    M: int = 2
    lam: float = 0.0
    P: float = 0.0
    T: float = 30.0         # response-time limit (minutes)
    q: float = 0.3
    alpha: float = 0.97     # T2 is not an input: T2 = 2 * T (see property below)
    cv: float = 0.2
    meta: dict = field(default_factory=dict)
    # computed in __post_init__
    a: np.ndarray = field(init=False)
    c: np.ndarray = field(init=False)
    r: np.ndarray = field(init=False)
    z: float = field(init=False)
    b: np.ndarray = field(init=False)
    V2: list[int] = field(init=False)
    Kbar: int = field(init=False)
    ymax: np.ndarray = field(init=False)
    allowed: list[list[int]] = field(init=False)
    P2: float = field(init=False)

    def __post_init__(self):
        self.d = np.asarray(self.d, float)
        self.t = np.asarray(self.t, float)
        self.g = np.asarray(self.g, float)
        self.delta = np.asarray(self.delta, int)
        self.h = np.asarray(self.h, int)
        self.s = np.asarray(self.s, float)
        self.e = np.asarray(self.e, int)
        self.C = np.asarray(self.C, int)
        self.S = sorted(int(j) for j in self.S)
        if not 0 < self.q < 1:
            raise ValueError("q must be in (0, 1)")

        self.a = (self.t <= self.T).astype(int)
        self.c = self.g[self.delta, :]                              # c_ij = g[delta_i, j]
        self.r = self.c + self.g[:, self.h].T                       # r_ij = c_ij + g[j, h_i]
        self.z = float(norm.ppf(self.alpha))
        mu, sigma = self.t, self.cv * self.t
        self.b = (mu + self.z * sigma <= self.T2).astype(int)
        self.V2 = [int(v) for v in np.flatnonzero(self.b.any(axis=0))]
        self.Kbar = int(self.nI + self.e.sum())
        self.ymax = np.minimum(self.Kbar, (self.a * self.C[:, None]).sum(axis=0)).astype(int)

        # Allowed bases after (5) shift rule and (6) sleeping bases.
        S = set(self.S)
        self.allowed = [
            [j for j in range(self.nJ)
             if j not in S and (j == self.h[i] or self.r[i, j] <= self.s[i])]
            for i in range(self.nI)
        ]
        self.P2 = 1 + 1 + self.lam * float(self.c.max(axis=1).sum()) + self.P * self.nV
        # Model R: overtime in whole minutes, rounded up (any lateness counts as >= 1 minute)
        self.ot = np.maximum(0, np.ceil(self.r - self.s[:, None] - 1e-9)).astype(int)

    def robust_guaranteed_feasible(self) -> bool:
        """Model R is feasible iff e_j <= C_j for all j and sum_{j not in S} (C_j - e_j) >= |I|."""
        if np.any(self.e > self.C):
            return False
        S = set(self.S)
        return int(sum(self.C[j] - self.e[j] for j in range(self.nJ) if j not in S)) >= self.nI

    @property
    def T2(self) -> float:
        """Outer limit of the 2T rule."""
        return 2 * self.T

    @property
    def nI(self) -> int: return len(self.delta)
    @property
    def nJ(self) -> int: return self.t.shape[0]
    @property
    def nV(self) -> int: return self.t.shape[1]
    @property
    def n_outside_V2(self) -> int: return self.nV - len(self.V2)
    @property
    def forced_moves(self) -> int:
        """Ambulances that may not stay at delta_i (sleeping base or shift rule)."""
        return sum(1 for i in range(self.nI) if int(self.delta[i]) not in self.allowed[i])

    def precheck(self) -> list[str]:
        """Spec 6b feasibility checks. Empty list = OK to solve."""
        problems = []
        S = set(self.S)
        bad_home = [i for i in range(self.nI) if self.h[i] in S]
        if bad_home:
            problems.append(f"home base in S for ambulances {bad_home}")
        if self.C.sum() < self.Kbar:
            problems.append(f"total capacity {self.C.sum()} < |I| + sum e = {self.Kbar}")
        no_base = [i for i in range(self.nI) if not self.allowed[i]]
        if no_base:
            problems.append(f"no allowed base for ambulances {no_base}")
        full_home = [i for i in range(self.nI) if self.C[self.h[i]] - self.e[self.h[i]] <= 0]
        if full_home:
            problems.append(f"home base full (C - e <= 0) for ambulances {full_home}")
        return problems


def build_instance(d, t, g, delta, h, s, S=(), e=None, C=None, name="custom", **params) -> Instance:
    nJ = np.asarray(t).shape[0]
    e = np.zeros(nJ, int) if e is None else e
    C = np.full(nJ, 2) if C is None else C
    return Instance(name=name, d=d, t=t, g=g, delta=delta, h=h, s=s, S=list(S), e=e, C=C, **params)


def generate_instance(case: int, n_ambulances: int, seed: int, n_sleeping: int = 0,
                      capacity: int = 2, shift_max: int = 480, period: int = 1,
                      shift_mode: str = "heading_home", **params) -> Instance:
    """Spec 6b generator. Same (case, |I|, n_sleeping, seed) -> same ambulance state,
    whatever alpha / cv / M / lam / P are, so models can be compared on identical states."""
    from .data_loader import load_case
    rd = load_case(case, period)
    rng = np.random.default_rng([case, n_ambulances, n_sleeping, seed])
    delta, h, s, S, e = draw_state(rd.g, rng, n_ambulances, n_sleeping, shift_max, shift_mode)
    C = np.full(len(rd.J), capacity)
    name = f"case{case}_I{n_ambulances}_S{n_sleeping}_seed{seed}"
    inst = Instance(name=name, d=rd.d, t=rd.t, g=rd.g, delta=delta, h=h, s=s, S=S, e=e, C=C,
                    meta={"case": case, "n_ambulances": n_ambulances, "n_sleeping": n_sleeping,
                          "seed": seed, "shift_mode": shift_mode}, **params)
    inst.meta["robust_guarantee_ok"] = inst.robust_guaranteed_feasible()   # flag, never drop
    return inst


def draw_state(g: np.ndarray, rng: np.random.Generator, n_ambulances: int, n_sleeping: int,
               shift_max: int, shift_mode: str):
    """Random ambulance state (spec 6b) for a region with base-to-base times g.
    Returns delta, h, s, S, e. Shared by every region so all use the same rules."""
    nJ = g.shape[0]
    S = sorted(int(j) for j in rng.choice(nJ, size=n_sleeping, replace=False)) if n_sleeping else []
    e = np.array([1 if j in S else 0 for j in range(nJ)])
    awake = [j for j in range(nJ) if j not in S]
    delta = rng.integers(0, nJ, size=n_ambulances)                 # random base (may be in S)
    h = rng.choice(awake, size=n_ambulances, replace=True)         # random base not in S
    s = rng.integers(0, shift_max + 1, size=n_ambulances)
    if shift_mode == "heading_home":
        # A crew that cannot reach home before its shift ends is not waiting elsewhere:
        # it is already driving home, so its destination base is its home base.
        # Then staying put (= going home) never causes overtime.
        late = s < g[delta, h]
        delta = np.where(late, h, delta)
    elif shift_mode != "uniform":
        raise ValueError(f"shift_mode must be 'heading_home' or 'uniform', got {shift_mode!r}")
    return delta, h, s, S, e
