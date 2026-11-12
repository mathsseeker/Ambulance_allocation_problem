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

Check the scorer (about a minute):

```bash
.venv/bin/python person2/checks/check_scoring.py
```

## Data notes

- Fez-Meknes has no base capacities: `instances.py` uses C_j = 2 (Model R default) unless told otherwise.
- The Fez-Meknes base-to-base file gives 3 min from a base to itself; Model R needs 0, so `load_map` sets it to 0.
- Gurobi's free pip licence is size-limited (2000 variables or constraints): enough for small checks only.
