
from pathlib import Path
from itertools import product
import pandas as pd
import numpy as np

from official_instances import create_instance

ROOT = Path(__file__).resolve().parents[1]

# Region, case, fleet sizes, time limits, capacity
CONFIGURATIONS = [
    ("fez", 1, [4, 8], [20, 30], 2),
    ("fez", 2, [4, 8], [20, 30], 2),
    ("fez", 3, [4, 8], [20, 30], 2),
    ("madrid", 1, [4, 8], [10, 15], None),
    ("edmonton", 1, [4, 8], [8, 12], None),
]

rows = []

for region, case, fleets, time_limits, capacity in CONFIGURATIONS:

    for n, T, sleeping, seed in product(
        fleets,
        time_limits,
        [0, 2],
        range(5),
    ):
        inst = create_instance(
            region=region,
            case=case,
            n_ambulances=n,
            seed=seed,
            n_sleeping=sleeping,
            T=T,
            capacity=capacity,
        )

        # Basic validation
        assert np.isclose(inst.d.sum(), 1.0)
        assert inst.t.shape == (inst.nJ, inst.nV)
        assert inst.g.shape == (inst.nJ, inst.nJ)
        assert inst.robust_guaranteed_feasible()

        scenario_id = (
            f"{region}_case{case}_I{n}_"
            f"T{T}_S{sleeping}_seed{seed}"
        )

        rows.append({
            "scenario_id": scenario_id,
            "region": region,
            "case": case,
            "n_ambulances": n,
            "n_bases": inst.nJ,
            "n_areas": inst.nV,
            "T": T,
            "n_sleeping": sleeping,
            "seed": seed,
            "capacity": (
                "native" if capacity is None
                else str(capacity)
            ),
            "M": inst.M,
            "q": inst.q,
            "alpha": inst.alpha,
            "cv": inst.cv,
            "lam": inst.lam,
            "P": inst.P,
            "shift_mode": "heading_home",
            "feasible": inst.robust_guaranteed_feasible(),
        })

df = pd.DataFrame(rows)

assert df["scenario_id"].is_unique

output = ROOT / "person3" / "scenarios_multiregion.csv"
df.to_csv(output, index=False)

print("Total scenarios:", len(df))
print("\nScenarios by region:")
print(df.groupby("region").size())
print("\nAll scenarios valid:", df["feasible"].all())
print("\nSaved to:", output)
