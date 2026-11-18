
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "person2"))

from ambulance.instance import generate_instance
from grasp import grasp
from scoring import is_valid, goals

# Generate one of your official scenarios
inst = generate_instance(
    case=1,
    n_ambulances=6,
    seed=0,
    n_sleeping=2,
    capacity=2,
    T=30,
    M=2,
    q=0.3,
    alpha=0.97,
    cv=0.2,
    shift_mode="heading_home",
)

# Solve using Person 2's heuristic
result = grasp(
    inst,
    beta=0.25,
    iterations=10,
    seed=42
)

plan = result["plan"]

# Verify that the solution is valid
assert is_valid(inst, plan)

print("Instance:", inst.name)
print("Assignment:", plan)
print("Objective values:", goals(inst, plan))
print("Runtime:", result["runtime"], "seconds")
print("Iterations:", result["iterations"])
print("Valid assignment:", is_valid(inst, plan))
