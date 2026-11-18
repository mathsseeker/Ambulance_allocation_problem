
from pathlib import Path
import numpy as np
import pandas as pd

from official_instances import create_instance

ROOT = Path(__file__).resolve().parents[1]

# Load the 200 generated scenarios
catalog = pd.read_csv(
    ROOT / "person3" / "scenarios_multiregion.csv"
)

results = []

for row in catalog.itertuples(index=False):

    # Reconstruct the scenario using its saved parameters
    capacity = (
        None if row.capacity == "native"
        else int(row.capacity)
    )

    params = dict(
        region=row.region,
        case=int(row.case),
        n_ambulances=int(row.n_ambulances),
        seed=int(row.seed),
        n_sleeping=int(row.n_sleeping),
        T=float(row.T),
        capacity=capacity,
        M=int(row.M),
        q=float(row.q),
        alpha=float(row.alpha),
        cv=float(row.cv),
        lam=float(row.lam),
        P=float(row.P),
        shift_mode=row.shift_mode,
    )

    inst = create_instance(**params)

    # VALIDATION 1: Correct matrix dimensions
    assert inst.d.shape == (inst.nV,)
    assert inst.t.shape == (inst.nJ, inst.nV)
    assert inst.g.shape == (inst.nJ, inst.nJ)

    # VALIDATION 2: Valid demand probabilities
    assert np.isclose(inst.d.sum(), 1.0)
    assert np.all(inst.d >= 0)

    # VALIDATION 3: Valid travel times
    assert np.all(np.isfinite(inst.t))
    assert np.all(np.isfinite(inst.g))
    assert np.all(inst.t >= 0)
    assert np.all(inst.g >= 0)
    assert np.allclose(np.diag(inst.g), 0)

    # VALIDATION 4: Ambulances and bases
    assert np.all((inst.delta >= 0) & (inst.delta < inst.nJ))
    assert np.all((inst.h >= 0) & (inst.h < inst.nJ))
    assert np.all(inst.s >= 0)
    assert np.all(inst.e <= inst.C)

    # VALIDATION 5: Model R feasibility
    assert inst.robust_guaranteed_feasible()

    # VALIDATION 6: Reproducibility
    repeat = create_instance(**params)

    assert np.array_equal(inst.delta, repeat.delta)
    assert np.array_equal(inst.h, repeat.h)
    assert np.array_equal(inst.s, repeat.s)
    assert inst.S == repeat.S

    # ANALYSIS: Areas reachable from at least one base
    reachable_T = np.any(inst.a == 1, axis=0)

    reachable_2T = np.any(inst.b == 1, axis=0)

    # Total free capacity at non-sleeping bases
    available_capacity = sum(
        int(inst.C[j] - inst.e[j])
        for j in range(inst.nJ)
        if j not in inst.S
    )

    results.append({
        "scenario_id": row.scenario_id,
        "region": row.region,
        "n_ambulances": inst.nI,
        "n_bases": inst.nJ,
        "n_areas": inst.nV,
        "T": inst.T,
        "seed": row.seed,
        "n_sleeping": len(inst.S),
        "available_capacity": available_capacity,
        "capacity_utilization": (
            inst.nI / available_capacity
        ),
        "areas_reachable_T": int(reachable_T.sum()),
        "areas_reachable_2T": int(reachable_2T.sum()),
        "potential_demand_T": float(
            inst.d[reachable_T].sum()
        ),
        "feasible": inst.robust_guaranteed_feasible(),
    })

# Save detailed statistics
df = pd.DataFrame(results)

output = ROOT / "person3" / "scenario_statistics.csv"
df.to_csv(output, index=False)

# Print summary
print("\nVALIDATION COMPLETED")
print("Total scenarios:", len(df))
print("All feasible:", df.feasible.all())

print("\nREGIONAL SUMMARY")

summary = df.groupby("region").agg(
    scenarios=("scenario_id", "count"),
    avg_ambulances=("n_ambulances", "mean"),
    avg_capacity_utilization=("capacity_utilization", "mean"),
    avg_reachable_T=("areas_reachable_T", "mean"),
    avg_potential_demand=("potential_demand_T", "mean"),
)

print(summary.round(3))

print("\nSaved to:", output)
