"""Shared setup for Person 2's tests: import path and a tiny hand-made map.

The tiny map is small enough to check every number by hand:

    bases 0, 1, 2        areas 0, 1      demand d = [0.6, 0.4]

    driving time base -> area (min)     base 0: [10, 50]
                                        base 1: [50, 10]
                                        base 2: [35, 35]

    With T = 30: base 0 covers area 0, base 1 covers area 1, base 2 covers nothing within T.
    With 2T = 60, cv = 0.2, alpha = 0.97 (z = 1.881): a time t counts as "within 2T" if
    t * (1 + 1.881 * 0.2) = 1.376 t <= 60, i.e. t <= 43.6. So base 0 does NOT reach area 1
    within 2T (50 min), base 1 does NOT reach area 0, and base 2 reaches both (35 min).

    driving time base -> base (min)     0-1: 30,  0-2: 10,  1-2: 10
"""
import sys
from pathlib import Path

import numpy as np

PERSON2 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PERSON2))
sys.path.insert(0, str(PERSON2.parent / "src"))

from ambulance.instance import build_instance  # noqa: E402  (Person 1's Instance)

D = [0.6, 0.4]
TIMES = [[10, 50], [50, 10], [35, 35]]
G = [[0, 30, 10], [30, 0, 10], [10, 10, 0]]


def tiny(delta, home, shift, S=(), C=(2, 2, 2), M=2, lam=0.0):
    """The tiny map with a given situation. Sleeping bases get one fixed ambulance (e_j = 1)."""
    e = np.zeros(3, int)
    e[list(S)] = 1
    return build_instance(D, TIMES, G, delta, home, shift, S=list(S), e=e, C=list(C),
                          T=30, q=0.3, alpha=0.97, cv=0.2, M=M, lam=lam)
