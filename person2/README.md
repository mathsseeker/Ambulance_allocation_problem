# Person 2: GRASP heuristic for Model R

Everything Person 2 builds lives in this folder. It uses only two things from
the rest of the repo:

- **the data** in `data/` (Madrid, Edmonton, Fez-Meknes)
- **Person 1's Model R code**: the `Instance` object (`src/ambulance/instance.py`)
  and, for checking only, the Gurobi solver (`src/ambulance/model.py`, `solve_robust`)

The model itself is in `reports/Model_R_Formulation.pdf`.

## Files

| File | What it does | Status |
|---|---|---|
| `scoring.py` | Scores a plan: the four goals of Model R and the 3 hard rules | ✅ done, checked |
| `instances.py` | Loads a map and draws a random situation, for testing only (Person 3 will make the official instances) | ✅ done |
| `checks/check_scoring.py` | Proves `scoring.py` agrees with Gurobi and with brute force | ✅ 55/55 OK |
| `construction.py` | GRASP construction: place ambulances one at a time, picking at random from the RCL of the best placements. `greedy()` = β = 0 | ✅ done |
| `checks/check_construction.py` | Greedy vs Gurobi; validity, diversity and best-of-20 for each β; runtime on medium instances | ✅ always valid, greedy optimal 26/55, < 1 s |
| `local_search.py` | Local search: MOVE one ambulance or SWAP two, keep only improvements, stop at a local optimum. First or best improvement | ✅ done |
| `checks/check_local_search.py` | Valid / never worse / true local optimum; greedy + local search vs Gurobi; best-of-20 per β; medium runtime | ✅ 660/660 correct, optimal 50/55, < 0.5 s |
| `grasp.py` | **The heuristic**: `grasp(inst, beta, iterations, time_limit, seed, mode)` repeats construction + local search and returns the best plan, its goals, runtime and an improvement history | ✅ done (slow on Fez case 3, see below) |
| `checks/check_grasp.py` | Valid, reproducible, time limit; optimal vs number of iterations; medium runtime | ✅ 55/55 optimal from 50 iterations |

## Construction results (55 small instances, 20 runs each)

| β | different plans (of 20) | best of 20 optimal |
|---|---|---|
| 0 (greedy) | 1.0 | 26/55 |
| 0.25 | 15.9 | 25/55 |
| 0.5 | 18.3 | 13/55 |
| 0.75 | 19.0 | 6/55 |
| 1 (random) | 19.3 | 4/55 |

Randomness alone does not beat greedy: the RCL brings in variety, but also worse placements.
That is expected in GRASP: construction gives **different starting points**, and local search
(next step) turns them into good plans. Whether β > 0 then pays off is the β sensitivity
experiment.

## Local search results (same 55 instances)

| Method | optimal |
|---|---|
| greedy | 26/55 |
| greedy + local search (first improvement) | 50/55 |
| greedy + local search (best improvement) | 49/55 |
| best of 20 × (construction + local search), β = 0.25 | **55/55** |
| same, β = 0.5 / 0.75 / 1 | 51 / 54 / 52 of 55 |

With local search, a little randomness (β = 0.25) beats pure greedy: this is why GRASP repeats
construction + local search from different random starts.

## GRASP results (β = 0.25)

Optimal on the 55 small instances, 3 seeds:

| iterations | 1 | 5 | 10 | 20 | 50 |
|---|---|---|---|---|---|
| optimal (of 55) | 45, 44, 45 | 52, 52, 52 | 54, 54, 53 | 54, 55, 55 | 55, 55, 55 |

Runtime of 100 iterations on medium instances: Fez case 1 (18 ambulances) 17 s, case 2 (22) 38 s,
case 3 (33 ambulances, 40 bases) **304 s**, Edmonton (20) 10 s.

**Known issue:** every candidate plan is scored from scratch, so one iteration on Fez case 3
takes about 3 s, and the time limit can only stop between iterations. To fix next:
score only what a move or swap changes (incremental evaluation).

## Key ideas

**A plan** is a dict `{ambulance i: base j}`, numbered from 0. Example: `{0: 4, 1: 4, 2: 7}`.

**Valid plan** = the 3 hard rules of Model R hold:
(1) every ambulance has one base, (6) no ambulance goes to a sleeping base, (3) no base over capacity.

**Better plan** = smaller `key(inst, plan) = (f1, f2, f3, -f4)`:

| Goal | Meaning | Direction |
|---|---|---|
| f1 | areas in V2 with no ambulance within 2T (60 min) | minimise |
| f2 | overtime minutes | minimise |
| f3 | moves above the free allowance M | minimise |
| f4 | expected coverage within T, minus moving cost and uncovered penalty | maximise |

Python compares tuples element by element, so `key(A) < key(B)` compares goal 1 first,
then goal 2, and so on: exactly Model R's strict order.

**Naming:** the GRASP greediness parameter is called **β** (0 = pure greedy, 1 = pure random),
because α is already used in Model R for the 2T reliability (0.97).

## Run

From the repo folder, once:

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Run the checks (a few minutes each):

```bash
.venv/bin/python person2/checks/check_scoring.py
```

```bash
.venv/bin/python person2/checks/check_construction.py
```

```bash
.venv/bin/python person2/checks/check_local_search.py
```

```bash
.venv/bin/python person2/checks/check_grasp.py
```

## Data notes

- Fez-Meknes has no base capacities: `instances.py` uses C_j = 2 (Model R default) unless told otherwise.
- The Fez-Meknes base-to-base file gives 3 min from a base to itself; Model R needs 0, so `load_map` sets it to 0.
- Gurobi's free pip licence is size-limited (2000 variables or constraints): enough for small checks only.
