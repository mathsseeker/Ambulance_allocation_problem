
from pathlib import Path
import sys

# Connect to Person 1's existing implementation
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ambulance.instance import generate_instance

# Generate one synthetic scenario
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

print("Instance name:", inst.name)
print("Free ambulances:", inst.nI)
print("Bases:", inst.nJ)
print("Demand areas:", inst.nV)

print("Current ambulance bases:", inst.delta)
print("Home bases:", inst.h)
print("Remaining shift times:", inst.s)
print("Sleeping bases:", inst.S)

print("Feasible:", inst.robust_guaranteed_feasible())
