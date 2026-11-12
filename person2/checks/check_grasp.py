"""Check the full GRASP.

1. Basics: the plan is valid, the same seed gives the same result,
   and the time limit stops the search.
2. Quality: how many of the 55 small instances reach Gurobi's optimum,
   for different numbers of iterations (beta = 0.25).
3. Medium instances: runtime of 100 iterations.

Run from the repo folder:   .venv/bin/python person2/checks/check_grasp.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # the person2 folder
from instances import load_map, random_instance                  # noqa: E402
from scoring import is_valid, key                                # noqa: E402
from grasp import grasp                                          # noqa: E402
from check_construction import small_instances, same_key         # noqa: E402
from ambulance.model import solve_robust                         # noqa: E402  (Person 1's Gurobi)


def main():
    insts = list(small_instances())
    optimum = {inst.name: key(inst, solve_robust(inst, time_limit=30)["assignment"]) for inst in insts}

    print("1. Basics")
    results = [grasp(inst, iterations=20, seed=1) for inst in insts]
    print(f"  valid plans: {sum(is_valid(i, r['plan']) for i, r in zip(insts, results))}/{len(insts)}")
    again = [grasp(inst, iterations=20, seed=1) for inst in insts]
    print(f"  same seed, same plan: {all(a['plan'] == b['plan'] for a, b in zip(results, again))}")
    big = random_instance(load_map("fez", 3), 33, 0, n_sleeping=2, capacity=2)
    r = grasp(big, iterations=10_000, time_limit=2.0)
    print(f"  time limit 2 s on Fez case 3: stopped after {r['runtime']:.2f} s, {r['iterations']} iterations")

    print("\n2. Optimal on the 55 small instances (beta = 0.25), 3 seeds each")
    for iterations in (1, 5, 10, 20, 50):
        counts = []
        for seed in range(3):
            counts.append(sum(same_key(key(inst, grasp(inst, iterations=iterations, seed=seed)["plan"]),
                                       optimum[inst.name]) for inst in insts))
        print(f"  {iterations:3d} iterations: optimal {counts[0]}, {counts[1]}, {counts[2]} of {len(insts)}")

    print("\n3. Medium instances: 100 iterations (beta = 0.25)")
    for name, case, nI, cap in [("fez", 1, 18, 2), ("fez", 2, 22, 2), ("fez", 3, 33, 2), ("edmonton", 1, 20, None)]:
        inst = random_instance(load_map(name, case), nI, 0, n_sleeping=2, capacity=cap,
                               T=30 if name == "fez" else 10)
        t0 = time.perf_counter()
        r = grasp(inst, iterations=100)
        print(f"  {name} case {case} |I|={nI}: valid={is_valid(inst, r['plan'])}  "
              f"goals={tuple(round(x, 4) for x in r['goals'])}  best at iteration {r['best_iteration']}  "
              f"{time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
