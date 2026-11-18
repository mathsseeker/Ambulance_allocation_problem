
from pathlib import Path
import sys
import csv
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ambulance.instance import generate_instance

rows = []

for n_ambulances in [4, 6, 8, 10]:
    for seed in range(5):

        inst = generate_instance(
            case=1,
            n_ambulances=n_ambulances,
            seed=seed,
            n_sleeping=2,
            capacity=2,
            T=30,
            M=2,
            q=0.3,
            alpha=0.97,
            cv=0.2,
            shift_mode="heading_home",
        )

        # Validate the instance
        assert np.isclose(inst.d.sum(), 1.0)
        assert inst.t.shape == (inst.nJ, inst.nV)
        assert inst.g.shape == (inst.nJ, inst.nJ)
        assert inst.robust_guaranteed_feasible()

        rows.append({
            "name": inst.name,
            "case": 1,
            "n_ambulances": inst.nI,
            "seed": seed,
            "n_sleeping": 2,
            "capacity": 2,
            "T": inst.T,
            "M": inst.M,
            "q": inst.q,
            "alpha": inst.alpha,
            "cv": inst.cv,
            "shift_mode": "heading_home",
            "feasible": True,
        })

output = ROOT / "person3" / "scenarios.csv"

with output.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} valid scenarios")
print(f"Saved scenario catalog to {output}")
