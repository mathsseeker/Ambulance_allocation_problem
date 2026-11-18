
from pathlib import Path
import sys
import csv
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ambulance.instance import generate_instance

# Read the scenario catalog
with open(ROOT / "person3" / "scenarios.csv") as f:
    scenarios = list(csv.DictReader(f))

print(f"Validating {len(scenarios)} scenarios...\n")

for row in scenarios:
    params = dict(
        case=int(row["case"]),
        n_ambulances=int(row["n_ambulances"]),
        seed=int(row["seed"]),
        n_sleeping=int(row["n_sleeping"]),
        capacity=int(row["capacity"]),
        T=float(row["T"]),
        M=int(row["M"]),
        q=float(row["q"]),
        alpha=float(row["alpha"]),
        cv=float(row["cv"]),
        shift_mode=row["shift_mode"],
    )

    # Reconstruct the original instance
    inst = generate_instance(**params)

    # 1. Demand probabilities sum to 1
    assert np.isclose(inst.d.sum(), 1.0)
    assert np.all(inst.d >= 0)

    # 2. Travel-time matrix dimensions
    assert inst.t.shape == (inst.nJ, inst.nV)
    assert inst.g.shape == (inst.nJ, inst.nJ)

    # 3. Valid, non-negative travel times
    assert np.all(np.isfinite(inst.t))
    assert np.all(np.isfinite(inst.g))
    assert np.all(inst.t >= 0)
    assert np.all(inst.g >= 0)

    # 4. Staying at the same base takes zero time
    assert np.allclose(np.diag(inst.g), 0)

    # 5. Correct ambulance state
    assert len(inst.delta) == inst.nI
    assert len(inst.h) == inst.nI
    assert len(inst.s) == inst.nI

    # 6. Model R capacity feasibility
    assert inst.robust_guaranteed_feasible()

    # 7. Same seed reproduces the same state
    repeat = generate_instance(**params)
    assert np.array_equal(inst.delta, repeat.delta)
    assert np.array_equal(inst.h, repeat.h)
    assert np.array_equal(inst.s, repeat.s)
    assert inst.S == repeat.S

    print(f"PASS: {inst.name}")

print("\nAll scenarios passed validation!")
