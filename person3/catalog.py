
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from person3.official_instances import create_instance

CATALOG_PATH = ROOT / "person3" / "scenarios_multiregion.csv"


def read_catalog():
    """Read and validate the official scenario catalog."""
    df = pd.read_csv(CATALOG_PATH)

    if df["scenario_id"].duplicated().any():
        raise ValueError("Duplicate scenario IDs found.")

    return df


def instance_from_row(row):
    """Reconstruct a Model R instance from a catalog row."""

    capacity = (
        None if str(row["capacity"]) == "native"
        else int(row["capacity"])
    )

    inst = create_instance(
        region=row["region"],
        case=int(row["case"]),
        n_ambulances=int(row["n_ambulances"]),
        seed=int(row["seed"]),
        n_sleeping=int(row["n_sleeping"]),
        T=float(row["T"]),
        capacity=capacity,
        M=int(row["M"]),
        q=float(row["q"]),
        alpha=float(row["alpha"]),
        cv=float(row["cv"]),
        lam=float(row["lam"]),
        P=float(row["P"]),
        shift_mode=row["shift_mode"],
    )

    if not inst.robust_guaranteed_feasible():
        raise ValueError(
            f"Scenario {row['scenario_id']} is infeasible."
        )

    return inst


def load_instance(scenario_id):
    """Load one official scenario by its unique identifier."""
    df = read_catalog()

    matches = df[df["scenario_id"] == scenario_id]

    if len(matches) != 1:
        raise ValueError(
            f"Scenario '{scenario_id}' not found uniquely."
        )

    return instance_from_row(matches.iloc[0])
