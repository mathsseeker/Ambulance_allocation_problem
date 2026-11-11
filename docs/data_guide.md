# Ambulance relocation project: data guide

11 Nov 2026 · Ricardo

## Indexing

| Index | Set | Meaning |
|---|---|---|
| i | I | Free ambulances at the moment of the decision |
| j | J | Bases, where ambulances can wait |
| v | V | Areas, where emergencies happen |
| k | K = {1, …, \|I\| + Σ_j e_j} | Coverage level: "area v is covered by at least k ambulances" |

The main decision variable is x_ij = 1 if free ambulance i is assigned to base j, and 0 otherwise.

## Source

Fez-Meknes (Morocco) ambulance dataset, Zenodo record 6416058, a single Excel file.
It is stored unchanged and read-only as `data/fez_meknes/raw/fez_meknes_ambulance_dataset.xlsx`
(MD5 `9379043ccfc869664be4b94eb46ec540`, matching Zenodo). Licence: CC BY 4.0.

- Frichi, Y., Jawab, F., & Aboueljinane, L. (2022). *Dataset on ambulance deployment and redeployment* (V1.0). Zenodo. https://doi.org/10.5281/zenodo.6416058
- Frichi, Y., Jawab, F., & Aboueljinane, L. (2022). Dataset on optimizing ambulance deployment and redeployment in Fez-Meknes region, Morocco. *Data in Brief*, 42, 108178. https://doi.org/10.1016/j.dib.2022.108178
- van Buuren, M. et al. (2018). Ambulance Dispatch Center Pilots Proactive Relocation Policies to Enhance Effectiveness. *Interfaces*, 48(3), 235–246.

## Data taken from the dataset

| Symbol | Meaning | Unit | Source (checked) | Processed file |
|---|---|---|---|---|
| V | 199 areas | — | Tables 1 (prefecture), 2 (name, lat/lon) | `areas.csv` |
| J | Bases: 18 / 22 / 40 | — | Table 7 | `bases.csv` |
| d_v | Population share, Σ = 1 | fraction | Table 3 | `areas.csv: d_v` |
| t_jv | Base → area time | minutes | Tables 9 / 10 / 11 | `t_jv_p1.csv`, `t_jv_p2.csv` |
| g_jj' | Base → base time | minutes | Tables 12 / 13 / 14 | `g_jj_p1.csv`, `g_jj_p2.csv` |
| \|I\| options | Fleet size scenarios | count | Table 8 | `data/fez_meknes/processed/fleet_options_table8.csv` |
| T | Response-time limit | minutes | Not in dataset: 15 (paper) | `config/default.yaml` |
| q | Busy probability | fraction | Not in dataset: 0.3 (paper) | `config/default.yaml` |

`areas.csv` also has the optional extras: yearly demand per ALS/BLS and period (Table 4),
arrival rates per hour (Table 5), and service time in minutes (Table 6).

## Data we generate (our choices, `config/default.yaml`)

| Symbol | How it is generated (`src/ambulance/data/generate.py`) |
|---|---|
| δ_i | Random base that has no sleeping crew |
| h_i | `even`: round-robin over a random order of the bases (or `random`) |
| s_i | Uniform integer 0..480 minutes |
| S | Empty by day; at night, 1 to 3 random bases |
| e_j | 1 for each base in S, 0 elsewhere |
| C_j | Uniform 1..2, then raised at random awake bases until all \|I\| free ambulances fit |
| M, λ, P | Model parameters, not generated: set them when solving |

Default instances: 5 seeds × {day, night} × 3 fleet sizes × 3 cases = 90 instances.

## Values computed from the data (`src/ambulance/data/derived.py`)

- a_jv = 1 if t_jv ≤ T
- c_ij = g_{δ_i j}, 0 when j = δ_i (teleportation assumption)
- r_ij = c_ij + g_{j h_i}

## What we found when opening the file

- **Units.** Times are in minutes, rounded to whole minutes. The article says they came from the Bing Maps API.
  It mentions **no lights-and-sirens adjustment**, so these are normal driving times, which is pessimistic for emergency driving.
- **Site order.** Tables 9–14 list the sites in the same order as Table 7, for all three cases.
  The code checks this: every g_jj' equals t_j,area(j') exactly.
- **Case 2 is not "Case 1 plus 4 sites at the end".** The order changes: the 4 added sites are
  Saiss (Fez), Fès-Médina, Missour and Ghafsai. Base j = 2 is a different place in each case.
- **Diagonal.** g_jj = 3 min in period 1 (the within-area driving time). We set it to 0 for c_ij and r_ij.
- **Periods.** Period 1 = 7h–22h, period 2 = 22h–7h. Every period-2 time is **exactly period-1 time minus 3 min**,
  so period 2 adds little. We use period 1 by default (`period: 1`).
- **Asymmetry.** g is not symmetric: 526 of 780 base pairs differ, but only 2 pairs by more than 10 min.
- **T = 15 is tight here.** The region is large and rural. The table below shows the areas that no base reaches within T (period 1).

| T (min) | Case 1 uncovered / demand covered | Case 2 | Case 3 |
|---|---|---|---|
| 10 | 176 / 34.0% | 172 / 41.3% | 153 / 58.9% |
| 15 | 161 / 43.9% | 154 / 50.6% | 124 / 67.5% |
| 20 | 151 / 57.6% | 145 / 60.3% | 110 / 72.1% |
| 30 | 100 / 75.7% | 94 / 77.4% | 63 / 85.3% |

  With T = 15, most areas can never be covered, whatever the relocation. They add a constant to the objective,
  or a constant P-penalty if P > 0. Consider T = 20 or 30 as well (just change `T` in the config).
- **Fleet size.** Table 8 scenarios use 57 ambulances in period 1 (38 at night) at the smallest option, up to 342.
  They are deployment scenarios (ALS + BLS), so they are far larger than C_j ∈ {1, 2} × 18 bases allows.
  Our default \|I\| values are about 0.5, 1 and 1.5 ambulances per base. Using Table 8 sizes would need larger C_j.
- **Estimating q.** The expected busy ambulances in period 1 are Σ_v (λ_ALS + λ_BLS) × service time ≈ 3.97.
  This gives q = 3.97 / \|I\|, for example 0.22 for \|I\| = 18 (stored as `q_estimated_from_data` in every instance).
  The paper's 0.3 is in the same range.

## Checklist

- [x] Travel times in minutes? Yes, they are in minutes. They do not assume lights and sirens.
- [x] Sites in Tables 9–14 in Table 7 order? Yes, the code checks this.
- [x] Is T = 15 sensible? It is restrictive here: see the table above.
- [x] Ambulances per Table 8 scenario: Option 1–4 = 57 / 133 / 209 / 342 (period 1), 38 / 95 / 152 / 266 (period 2).
