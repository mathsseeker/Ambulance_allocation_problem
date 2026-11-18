
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "person2"))

from person3.catalog import (
    read_catalog,
    instance_from_row,
    load_instance,
)
from grasp import grasp
from scoring import is_valid

catalog = read_catalog()

# Part A: Validate every catalog entry
for _, row in catalog.iterrows():
    inst = instance_from_row(row)

    assert inst.nI == int(row["n_ambulances"])
    assert inst.nJ == int(row["n_bases"])
    assert inst.nV == int(row["n_areas"])
    assert np.isclose(inst.d.sum(), 1.0)

    # Check reconstruction through the public interface
    repeated = load_instance(row["scenario_id"])
    assert np.array_equal(inst.delta, repeated.delta)
    assert np.array_equal(inst.h, repeated.h)
    assert np.array_equal(inst.s, repeated.s)

print(f"PASS: {len(catalog)} scenarios reconstructed")

# Part B: Test GRASP in each region
for region in ["fez", "madrid", "edmonton"]:
    subset = catalog[
        (catalog["region"] == region)
        & (catalog["n_ambulances"] == 4)
    ]

    row = subset.iloc[0]
    inst = load_instance(row["scenario_id"])

    result = grasp(
        inst,
        beta=0.25,
        iterations=10,
        seed=42,
    )

    assert is_valid(inst, result["plan"])

    print(f"PASS: {region}")
    print("  Scenario:", row["scenario_id"])
    print("  Goals:", result["goals"])
    print("  Runtime:", round(result["runtime"], 3), "s")

print("\nFINAL HANDOFF CHECK PASSED")
