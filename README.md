# Ambulance relocation (Opti 3 project)

Proactive ambulance relocation in the style of van Buuren et al. (2018), using MEXCLP coverage.
It is extended with shift times, home bases, sleeping crews, a move limit, and a 30-minute
chance-constrained bound (Model H = hard, Model E = elastic). We test it on the public Fez-Meknes dataset.

## Layout

```
config/default.yaml          data-preparation settings
data/raw/                    original Zenodo Excel file (read-only)
data/processed/case{1,2,3}/  clean CSVs per base case + summary.json
docs/data_guide.md           symbols, sources, and what we found in the data
src/ambulance/
  data/                      Excel readers and CSV preparation
  data_loader.py             load_case(case) -> V, J, d, t, g
  instance.py                generate_instance(...) / build_instance(...): state + a, c, r, b, V2, P2
  model.py                   solve_exact / solve_hard / solve_elastic / solve_robust (gurobipy)
  evaluate.py                evaluate(inst, assignment, model): objective + constraint check, no Gurobi
scripts/
  prepare_data.py            rebuilds data/processed
  main.py                    one Case-1 instance, all three models
  feasibility_experiment.py  grid definition (H vs E, superseded T = 15 run)
  robust_comparison.py       base / H / E / R grid -> results/robust_comparison*.csv
  madrid_robust.py           same comparison on the Madrid instance -> results/madrid_robust*.csv
reference/                 robust_model_reference.py (given, self-test: ALL CHECKS PASSED)
tests/                       pytest (spec section 8 + data checks)
```

## Run

```bash
.venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python -m pytest
```

```bash
.venv/bin/python scripts/main.py --n 6 --seed 0
```

```bash
.venv/bin/python scripts/robust_comparison.py
```

Solve functions never raise and never hang. Each returns a `status` and a one-line `message`:
`OPTIMAL`, `TIME_LIMIT` (with the best plan found), `INFEASIBLE` (Model H also gives IIS families),
`PRECHECK_FAILED`, `SIZE_LIMIT` (pip licence: at most 2000 variables/constraints) or `ERROR`.

## Settings

T = 30 min (response-time limit, a parameter). T2 = 2T = 60 min is computed, not an input.
Model R's priority order is fixed: 2T violations, then overtime minutes, then extra moves, then coverage.
Shift times: `generate_instance(..., shift_mode="heading_home")` (default) sends a crew that cannot reach home
before its shift ends to its home base (δ = h); `"uniform"` is the old fully random version.
Older results: `results/superseded_T15_T2_30/` and `results/superseded_uniform_shifts/`.

## Four-model comparison (results/robust_comparison.csv, 6480 instances, 76 s)

The grid covers cases 1–3, α ∈ {.95, .97, .99}, cv ∈ {.1, .2, .3}, |I| ∈ {2, 4, 6, ≈0.5/1/1.5 per base},
|S| ∈ {0, 2}, 10 seeds, M ∈ {2, |I|}. The licence skipped 720 Case-3 instances; the means below use the 5760 that fit.

| Mean | Base M=2 | E M=2 | R M=2 | E M=\|I\| | R M=\|I\| | R overtime-first |
|---|---|---|---|---|---|---|
| plan found | 80% | 80% | 100% | 99.7% | 100% | 100% |
| 2T violations | 71.8 | 60.6 | 40.1 | 42.7 | 40.1 | 42.6 |
| overtime (min) | 0 | 0 | 43 | 0 | 43 | 0.5 |
| worst single ambulance overtime (min) | 0 | 0 | 404 | 0 | 404 | 160 |

Model H has a plan in under 1% of instances (M = 2) and 26% (M = |I|).
With realistic shifts, all of R's overtime comes from ranking violations first
(`scripts/priority_experiment.py` runs the overtime-first order as an experiment).
See the progress report doc for the full write-up and the Model R formulation.

## Madrid instance (SAMUR-PC, Fuencarral – El Pardo)

`data/madrid/` holds a second real instance: 8 barrios, 8 SAMUR-PC bases (district + neighbours),
OSRM travel times, estimated `C_j = 5`. Sources, checks and limitations are in `data/madrid/README.md`.

```bash
.venv/bin/python scripts/madrid_robust.py
```

Runs Base / H / E / R over T ∈ {10, 15, 20, 30} (17,280 instances, ~30 s). Model R finds a plan on every
instance that meets the capacity guarantee; at M = 2 it solves 1,620 that strict E cannot (forced moves > M).
At T = 30 the instance is nearly trivial (every base covers every area); use T = 10–20.
# Ambulance_reallocation_problem
# Ambulance_reallocation_problem
# Ambulance_reallocation_problem
