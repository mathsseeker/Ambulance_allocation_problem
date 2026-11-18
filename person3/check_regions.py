
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "person2"))

from official_instances import create_instance
from grasp import grasp
from scoring import is_valid

regions = [
    ("fez", 20),
    ("madrid", 15),
    ("edmonton", 10),
]

for region, T in regions:
    inst = create_instance(
        region=region,
        n_ambulances=4,
        seed=0,
        n_sleeping=2,
        T=T,
    )

    result = grasp(
        inst,
        beta=0.25,
        iterations=10,
        seed=42,
    )

    assert is_valid(inst, result["plan"])

    print(f"\nRegion: {region}")
    print("Valid plan:", True)
    print("Objectives:", result["goals"])
    print("Runtime:", round(result["runtime"], 3), "seconds")

print("\nAll three regions passed!")
