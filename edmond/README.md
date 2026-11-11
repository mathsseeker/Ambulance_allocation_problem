# Model R on the Edmonton instance

This folder applies Model R (`reports/Model_R_Formulation.pdf`) to the Edmonton EMS data in `data/edmonton/processed/` (Ingolfsson; see `data/edmonton/README.md`). The model code is **not** rewritten here. It reuses the project's implementation as it is:

| Piece | Where |
|---|---|
| a_jv, b_jv, V₂, c_ij, r_ij, ot_ij, k̄_v | `src/ambulance/instance.py` (`Instance.__post_init__`) |
| Model R (Gurobi hierarchical multi-objective) | `src/ambulance/model.py` (`solve_robust`) |
| Gurobi-free re-scoring of every solution | `src/ambulance/evaluate.py` (`evaluate(..., "robust")`) |
| Edmonton data loader + scenario generator | `edmond/edmonton.py` |
| Demo and experiment grid | `edmond/run_model_r.py` |

```bash
.venv/bin/python edmond/run_model_r.py demo --n 8 --seed 0 --sleeping 2 --T 8
```

```bash
.venv/bin/python edmond/run_model_r.py grid
```

---

## 1. Model R stated for Edmonton

### Sets

| Symbol | Edmonton | Source |
|---|---|---|
| J | 16 stations, j = 1..16 | `bases.csv` |
| V | 180 demand nodes, v = 1..180 | `areas.csv` |
| I | free ambulances at the decision moment, \|I\| ∈ {4, 8, 12, 16} | generator (§2) |
| S ⊆ J | stations with a sleeping crew, \|S\| ∈ {0, 2} | generator (§2) |

### Parameters

| Symbol | Value on Edmonton | Status |
|---|---|---|
| d_v | `areas.csv: d_v` (calls_v / 45,264), Σ d_v = 1 | derived exactly from the original fractions |
| t_jv | `t_base_area.csv: t_min`, 3.0–41.1 min (median 16.3) | original. **Response time**, possibly including the delay before leaving (open question) |
| g_jj′ | `g_base_base.csv: g_min`; g_jj = 0 | **approximation**: g(j, j′) = t(j, v*(j′)) with v*(j′) = argmin_v t(j′, v). Not symmetric |
| C_j | `bases.csv: C_j` = 1,1,1,2,2,3,3,2,3,3,1,1,1,1,1,1 (Σ = 27) | original (replaces the Model R default C_j = 2) |
| c_v (travel-time CV) | **0.2636** = median σ_jv / t_jv | derived from the data (replaces "an assumption") |
| T | **8 min** (main), 10 min (sensitivity), 30 min (Model R default, for comparison) | modelling choice |
| 2T | 16 / 20 / 60 min | computed |
| q | 0.3 (Model R default) | **assumption**: cannot be derived (the call period is unknown) |
| α | 0.97 → z_α = 1.881 | modelling choice (Model R default) |
| M | 2 | modelling choice (Model R default) |
| λ, P | 0, 0 | modelling choice (moving cost and the no-coverage penalty switched off) |
| δ_i, h_i, s_i, e_j | random per seed | generator (§2) |

### Derived parameters (computed before solving)

- a_jv = 1 if t_jv ≤ T
- b_jv = 1 if t_jv (1 + z_α c_v) ≤ 2T (as formulated; the `empirical` variant uses t_jv + z_α σ_jv ≤ 2T, see §3)
- V₂ = {v : Σ_j b_jv ≥ 1}
- c_ij = g_{δ_i j}
- r_ij = c_ij + g_{j h_i}
- ot_ij = ⌈max(0, r_ij − s_i)⌉
- k̄_v = min(|I| + Σ_j e_j, Σ_j a_jv C_j)

On Edmonton with T = 8 and c_v = 0.2636: |V₂| = 170, so 10 areas cannot be reached within 16 min with probability 0.97 from any station, and the 2T rule is not applied to them. On average 1.41 stations reach an area within T (a_jv), and 3.22 within 2T (b_jv).

### Decision variables

x_ij ∈ {0,1}; y_vk ∈ {0,1} for k = 1..k̄_v; w_v ∈ {0,1} for v ∈ V₂; u_v ∈ {0,1} (only if P > 0); o ∈ ℤ≥0.
Write n_j = Σ_i x_ij + e_j.

### Objective (lexicographic)

lex min ( f₁, f₂, f₃, −f₄ ) with

- f₁ = Σ_{v∈V₂} w_v (2T-rule violations)
- f₂ = Σ_{i,j} ot_ij x_ij (overtime minutes)
- f₃ = o (moves above M)
- f₄ = Σ_v Σ_{k=1}^{k̄_v} d_v (1−q) q^{k−1} y_vk − λ Σ_{i,j} c_ij x_ij − P Σ_v u_v

### Constraints

| # | Constraint |
|---|---|
| (1) | Σ_j x_ij = 1 ∀ i |
| (2) | Σ_k y_vk ≤ Σ_j a_jv n_j ∀ v |
| (3) | n_j ≤ C_j ∀ j |
| (4′) | Σ_i (1 − x_{iδ_i}) ≤ M + o |
| (6) | x_ij = 0 ∀ i, j ∈ S |
| (7) | u_v ≥ 1 − Σ_j a_jv n_j ∀ v (only if P > 0; off here) |
| (9E) | Σ_j b_jv n_j ≥ 1 − w_v ∀ v ∈ V₂ |

**Feasibility.** Model R is feasible if and only if e_j ≤ C_j ∀ j and Σ_{j∉S} (C_j − e_j) ≥ |I|. For Edmonton the worst case in the grid is |I| = 16 with two sleeping 3-capacity stations: 27 − 3 − 3 = 21 ≥ 16, so every instance in the grid satisfies it (checked per instance: `robust_guarantee_ok`).

**Solution method.** Gurobi `setObjectiveN` with priorities f₁ > f₂ > f₃ > f₄, reltol = 0, MIPGap = 0, time limit 60 s.

## 2. Scenario generator

`edmond/edmonton.py: draw_state` uses the same rules as the project's `generate_instance` (spec 6b), with its own random stream (`[2008, |I|, |S|, seed]`):

- S: |S| stations drawn without replacement; e_j = 1 on S, 0 elsewhere.
- δ_i: uniform over all 16 stations (it may fall in S, or on a station that is already full).
- h_i: uniform over the stations not in S.
- s_i: uniform integer in [0, 480] min.
- "heading_home": if s_i < g_{δ_i h_i}, the crew is already driving home, so δ_i = h_i.

The only change from the Fez-Meknes generator is C_j: Edmonton uses its real capacities, not a constant 2.

## 3. Results (`results/`)

The grid has T ∈ {8, 10, 30} × |I| ∈ {4, 8, 12, 16} × |S| ∈ {0, 2} × 10 seeds × σ-mode ∈ {cv, empirical}, giving **480 instances, solved in 11 s in total**. The other settings are fixed: q = 0.3, α = 0.97, M = 2, λ = P = 0.

- **380 OPTIMAL, 100 SIZE_LIMIT, 0 infeasible, 0 errors.**
- `evaluate()` re-scores every optimal plan from the formulas, with no Gurobi. It agrees with Gurobi on all 380 (f₁, f₂ and f₄ identical), and all 380 plans satisfy (1), (3) and (6).
- Each solve takes 13–51 ms. Models have at most 1,749 variables (T = 30, |I| = 8, |S| = 0).

Mean over the 10 seeds of each row, with σ-mode = cv (the full table, with the empirical-σ rows too, is in `results/report.txt`):

| T | \|I\| | \|S\| | f₁ 2T viol. | f₂ overtime (min) | f₃ extra moves | f₄ coverage | moves |
|---|---|---|---|---|---|---|---|
| 8 | 4 | 0 | 31.0 | 0.9 | 1.3 | 0.286 | 3.3 |
| 8 | 4 | 2 | 11.0 | 0.9 | 1.0 | 0.486 | 3.0 |
| 8 | 8 | 0 | 0 | 0 | 2.2 | 0.560 | 4.2 |
| 8 | 8 | 2 | 0 | 0.2 | 1.8 | 0.638 | 3.8 |
| 8 | 12 | 0 | 0 | 1.9 | 1.3 | 0.701 | 3.3 |
| 8 | 12 | 2 | 0 | 0 | 1.8 | 0.790 | 3.8 |
| 8 | 16 | 0 | 0 | 0 | 1.2 | 0.849 | 3.2 |
| 8 | 16 | 2 | 0 | 1.5 | 4.3 | 0.896 | 6.3 |
| 10 | 4 | 0 | 9.0 | 0.9 | 1.0 | 0.442 | 3.0 |
| 10 | 8 | 0 | 0 | 0 | 0.9 | 0.852 | 2.9 |
| 10 | 16 | 0 | 0 | 0 | 1.1 | 0.967 | 3.1 |
| 30 | 4 | 0 | 0 | 0 | 0 | 0.992 | 1.9 |
| 30 | 8 | 0 | 0 | 0 | 0.2 | 0.9999 | 2.2 |
| 30 | ≥ 8 with \|S\| = 2, or ≥ 12 | | SIZE_LIMIT | | | | |

### What the results show

1. **T = 30 is trivial on Edmonton, as predicted.** Every solved T = 30 instance has 0 violations, 0 overtime and coverage ≥ 0.992, and the status quo is already 0.9917. The larger T = 30 instances cannot even be built under the pip licence: with a_jv ≈ 1, k̄_v = |I| + Σe for every area, which gives up to 2,093 y variables. **Use T = 8 (main) or T = 10.**
2. **At T = 8 all four goals do real work.** With 4 ambulances the city cannot meet the 2T rule: 31 of 170 areas are violated with |S| = 0, and 11 with |S| = 2, because the two fixed sleeping-crew ambulances help. From 8 ambulances on, f₁ = 0, and the model trades extra moves for coverage.
3. **c_v assumption vs. real σ.** The `cv` and `empirical` rows are almost identical: |V₂| is 170 vs 171, and f₁ differs by at most 1 area on average. This supports using a constant c_v = 0.2636 on this instance.
4. **R vs. status quo.** When nobody moving is feasible, R cuts 2T violations sharply (for example T = 8, |I| = 4: 66 → 31). It sometimes does this at a cost in coverage (0.333 → 0.286), because the priority order puts f₁ first. With more ambulances, R matches or beats the status quo coverage (T = 8, |I| = 16: 0.852 → 0.875).
5. **Overtime has two sources.** 18 of the 380 solved instances have overtime (at most 19 min). Each was re-solved with the experimental overtime-first order (`solve_robust_overtime_first`):
   - **Chosen, 12 instances.** Model R accepts 2–15 min of overtime to remove 1–4 more 2T violations (for example T = 8, |I| = 4, |S| = 2, seed 8: 3 min of overtime and 9 violations, against 0 min and 13 under overtime-first). This is the priority order f₁ > f₂ working as designed, the same effect seen on Fez-Meknes.
   - **Unavoidable, 6 instances.** The overtime-first order gives the same overtime (15 or 19 min). The starting state forces ambulances off their station: the generator draws δ_i without regard to C_j, and 9 Edmonton stations have C_j = 1.
6. **The status quo is often infeasible.** Of the 80 distinct ambulance states (|I| × |S| × seed), 57 cannot simply stay put. In 55 of them some station starts over capacity, and in 31 an ambulance starts at a sleeping station (some have both). Model R handles these through the soft move limit (4′). The Fez-Meknes generator rarely hit this because C_j = 2 there.

## 4. Caveats

- **g_jj′ is an approximation** (nearest-node proxy). It feeds c_ij and r_ij, and therefore f₂ (overtime) and the λ moving-cost term of f₄ (switched off here, λ = 0). f₁, f₃ and the coverage term of f₄ do not use g.
- **t_jv may include the delay before leaving.** If it does, both t and g are slightly overstated, which makes a_jv, b_jv slightly conservative and r_ij slightly high.
- **q = 0.3 is an assumption.** The data cannot give the busy probability without the period length.
- **The generator draws δ_i without regard to capacity.** On Edmonton this is the main source of forced moves, and of the overtime that cannot be avoided. A capacity-respecting δ draw would be a generator change. It was not made here, so the scenarios stay comparable with the Fez-Meknes ones.
- **Licence size limit.** The pip Gurobi licence (2,000 variables) is not a problem for T = 8 or 10 (≤ 1,261 variables). It only blocks the trivial T = 30 instances.
