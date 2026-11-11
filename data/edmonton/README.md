# Edmonton EMS instance (Ingolfsson data)

## Source

- Page: Armann Ingolfsson, University of Alberta — https://sites.ualberta.ca/~aingolfs/Data.htm
- Files fetched from `https://sites.ualberta.ca/~aingolfs/~/data/<name>.txt`
- Download date: **2026-11-11** (UTC 18:28). All seven URLs returned HTTP 200; files are stored unmodified in `raw/`.

Cite:

- Erkut, E., Ingolfsson, A., & Erdogan, G. (2008). Ambulance deployment for maximum survival. *Naval Research Logistics* 55(1), 42–58.
- Erkut, E., Ingolfsson, A., Sim, T., & Erdogan, G. (2009). Computational comparison of five maximal covering models for locating ambulances. *Geographical Analysis* 41(1), 43–65.

## Raw files (`raw/`)

All files are ASCII with CRLF line endings and use tabs as separators.

| File | Real format | Content |
|---|---|---|
| `average_busy_time_for_ambulances_in_seconds.txt` | 1 line, 1 value: `2691.376819` | Mean ambulance busy time per call (s) |
| `numberofcallsdemanddata.txt` | 4 header lines (`Total number of calls: 45264`, `Number of urgent calls: 13203`), 2-line column header, then 180 rows `node<TAB>fraction` (6 decimals) | Fraction of calls from each demand node. **It has fractions only, not counts.** |
| `average_of_response_times_in_seconds.txt` | 2 header lines (`Station`, station ids 1..16), then 180 rows: optional label (`Demand`/`node` on the first two rows), node id, 16 values | Mean response time (s), rows = demand node, columns = station |
| `stdev_of_response_times_in_seconds.txt` | same layout, 180 × 16 | Std. dev. of response time (s) |
| `deterministic_coverage_for_8_minute_threshold.txt` | same layout, 180 × 16, values in {0, 1} | 1 if node is covered by station within 8 min |
| `probabilistic_coverage_for_8_minute_threshold.txt` | same layout, 180 × 16, values in [0, 0.989626] | Probability of reaching node within 8 min |
| `station_capacities.txt` | header `Station Capacity` + 16 rows | Capacity per station (integer) |

## Dimensions and consistency

- 180 demand nodes (ids 1..180, contiguous) in the demand file and in all four matrices.
- 16 stations (ids 1..16) in all four matrices and in the capacity file.
- All files agree with each other. The expected 180 × 16 instance is confirmed.
- Total capacity = 27 (capacities: 1,1,1,2,2,3,3,2,3,3,1,1,1,1,1,1).
- The files contain **no coordinates** and no station-to-station times.

## Processed files (`processed/`)

Indices: `j` = base/station, `v` = area/demand node. Times are in minutes (raw seconds / 60).

| File | Column | How it was obtained | Original or derived |
|---|---|---|---|
| `areas.csv` | `v` | node id | original |
| | `frac_raw` | fraction from the raw file (6 decimals; adds up to 0.999996) | original |
| | `calls` | `round(frac_raw × 45264)` | **derived** (see `method`) |
| | `d_v` | `calls / 45264`; adds up to exactly 1 | **derived** |
| | `method` | `calls=round(frac_raw*total_calls); d_v=calls/total_calls` | — |
| `bases.csv` | `j`, `C_j` | station capacity | original |
| `t_base_area.csv` | `t_min` | mean response time / 60 | original (unit conversion only) |
| | `sigma_min` | std. dev. of response time / 60 | original (unit conversion only) |
| `g_base_base.csv` | `g_min` | `g(j,j2) = t(j, v*(j2))`, where `v*(j2) = argmin_v t(j2, v)`; `g(j,j) = 0` | **approximation** |
| | `method` | `approx_nearest_node` (off-diagonal), `zero_diagonal` (j = j2) | — |
| | `proxy_node_v` | the node `v*(j2)` used as a proxy for station j2's location | — |
| `params.json` | `mean_busy_time_min` | 2691.376819 / 60 = 44.856 min | original (unit conversion) |
| | `n_areas`, `n_bases`, `total_capacity` | 180, 16, 27 | counted from the raw files |
| | `total_calls`, `urgent_calls` | 45264, 13203 (copied from the header of the demand file) | original |

### About `calls`
The raw demand file gives only fractions. When each fraction is multiplied by the total (45,264), the result is an integer to within ±0.023, and the rounded counts add up to exactly 45,264. The largest gap is what you get from rounding to 6 decimals (0.5·10⁻⁶ × 45,264 ≈ 0.0226). So the counts are recovered exactly, and the fractions are fractions of **all** calls, not of urgent calls. Multiplying by 13,203 instead gives gaps of up to 0.50, which do not fit. This is still a derivation, so it is marked in `method`.

### About `g_base_base.csv`
Proxy nodes `v*(j2)`: 1→42, 2→115, 3→69, 4→101, 5→78, 6→10, 7→62, 8→97, 9→23, 10→2, 11→33, 12→152, 13→64, 14→54, 15→102, 16→76 (no ties). Each station's own time to its proxy node ranges from 3.0 to 5.24 min, so the proxy is not the station's exact location. The matrix is **not symmetric**: the largest |g(j,j2) − g(j2,j)| is 5.88 min. Off-diagonal values range from 5.62 to 30.43 min. Nobody has checked whether it satisfies the triangle inequality.

Reproduce with: `python3 -I data/edmonton/process.py data/edmonton` (the script also prints the checks below).

## Checks

**Demand**: Σ d_v = 1.000000 (the raw fractions add up to 0.999996). No node has zero demand (smallest fraction 2.2·10⁻⁵).

**Response times** (2,880 base–area pairs): no missing, negative or zero values in `t_min` or `sigma_min`.

| | min | median | max |
|---|---|---|---|
| `t_min` | 3.000 | 16.272 | 41.073 |
| `sigma_min` | 1.500 | 4.255 | 11.520 |
| CV = `sigma_min / t_min` | 0.2572 | 0.2636 | 0.5000 |

Without the six 3.0-minute entries (see the oddities below), the CV ranges from 0.2572 to 0.4159. The CV is almost constant around 0.26. This suggests that σ is a modelled function of the mean (as in the Ingolfsson travel-time models) and not an empirical std. dev. per pair.

**Deterministic coverage, `t_min ≤ T`**

| T (min) | % areas with ≥1 base | % demand with ≥1 base | mean # bases covering an area | areas covered by all 16 bases |
|---|---|---|---|---|
| 8 | 79.44 % | 98.44 % | 1.41 | 0 |
| 15 | 100 % | 100 % | 6.86 | 0 |
| 30 | 100 % | 100 % | 15.64 | 144 |

At T = 15 every area is covered, but only by about 6.9 of 16 bases on average and no area by all of them. So the instance is **not trivial** at T = 15 when coverage depends on which bases have an available ambulance. At T = 30 it is close to trivial: 144 of 180 areas are covered by every base.

**Probabilistic coverage, `t_min + z·sigma_min ≤ 30`**

| z | areas with ≥1 base | % demand | mean # bases per area |
|---|---|---|---|
| 1.645 | 180 / 180 | 100 % | 11.86 |
| 1.881 | 180 / 180 | 100 % | 11.24 |
| 2.326 | 180 / 180 | 100 % | 10.08 |

**Comparison with the original 8-minute deterministic coverage file**: `t_min ≤ 8` matches `deterministic_coverage_for_8_minute_threshold.txt` in **all 2,880 cells** (0 mismatches; 253 covered pairs in both).

## Using this instance with Model R

Notes for `reports/Model_R_Formulation.pdf`. The values are also stored under `model_r` in `params.json`.

| Model R symbol | Edmonton source | Status |
|---|---|---|
| `d_v` | `areas.csv: d_v` | derived exactly from the original fractions |
| `t_jv` | `t_base_area.csv: t_min` | original, but see the note on response time below |
| `g_jj'` | `g_base_base.csv: g_min` | **approximation** (`approx_nearest_node`), not symmetric |
| `C_j` | `bases.csv: C_j` (values 1–3, total 27) | original. Use these, **not** the Model R default `C_j = 2` |
| `c_v` | 0.2636 = median of `sigma_min / t_min` | **derived** |
| `T` | — | recommendation: **8 or 10 min**, not the default 30 (see below) |
| `q` | — | **not available** from the data (see below) |
| `α`, `M`, `λ`, `P` | — | modelling choices, not data |
| `I`, `δ_i`, `h_i`, `s_i`, `e_j`, `S` | — | come from the instance generator |

**c_v.** Model R assumes σ = c_v · t. On this instance the per-pair ratio is almost constant (median 0.264; 0.257–0.416 if the six 3-minute entries are left out). The 2T rule computed with the constant c_v = 0.26 and with the real `sigma_min` gives nearly the same results (table below), so the assumption fits.

**T.** The Model R default T = 30 (2T = 60) makes this urban instance trivial. Below, a_jv uses `t_min ≤ T`; b_jv uses α = 0.97 (z = 1.881) and the real `sigma_min`; the last column uses c_v = 0.26 instead.

| T | mean # bases with a_jv=1 | areas with a_jv=1 for all 16 | areas with no base within T | \|V₂\| | areas with b_jv=1 for all 16 | same, c_v = 0.26 |
|---|---|---|---|---|---|---|
| 8 | 1.41 | 0 | 37 | 171 | 0 | 0 |
| 10 | 2.70 | 0 | 13 | 179 | 0 | 0 |
| 12 | 4.22 | 0 | 4 | 180 | 0 | 0 |
| 15 | 6.86 | 0 | 0 | 180 | 11 | 12 |
| 20 | 11.24 | 11 | 0 | 180 | 96 | 105 |
| 30 | 15.64 | 144 | 0 | 180 | 179 | 179 |

With T = 30, any single ambulance at any base satisfies the 2T rule for 179 of 180 areas, so f₁ is always 0. And a_jv is almost all 1s, so f₄ depends almost only on how many ambulances there are, not where they are. T = 8 is Edmonton's real standard and matches the original 8-minute coverage file. T = 10 is a looser alternative. Both leave all four goals with something to do. With T = 8 and z = 1.881, 9 areas fall outside V₂, and Model R does not apply the 2T rule to them.

**q.** In Model R, q is the probability that an ambulance is busy. It could be estimated as (calls per minute × 44.86 min mean busy time) / fleet size. The source gives 45,264 calls but not the period they cover, so the call rate is unknown. q must be set as an assumption (for example, the Model R default 0.3) and reported as such.

**t_jv is response time, not driving time.** Model R defines t_jv and g_jj' as driving times. The source calls them response times, which may include the delay before the ambulance leaves (see the open questions). If they do, t_jv is slightly too high. g_jj', which is built from t_jv, then overstates moving times, and so do the overtime goal f₂ (through r_ij) and the moving cost λ·c_ij. One hint that it does: every station's nearest area is at least 3.0 min away, and the off-diagonal g_jj' is never below 5.6 min, while g_jj = 0.

**Feasibility.** Model R is feasible if and only if e_j ≤ C_j for every j and Σ_{j∉S} (C_j − e_j) ≥ |I|. With 27 spots in total, the generator must respect these limits.

## Oddities

- Stations 11–16 each have exactly one node at **180.000 s mean / 90.000 s std. dev.** (station 11→node 33, 12→152, 13→64, 14→54, 15→102, 16→76). This is the smallest time in the whole matrix and the only place where CV = 0.5. It looks like a hard-coded value for a station located inside that demand node, not an estimate. Stations 1–10 have no such entry; their shortest time is 3.6–5.2 min.
- The demand file gives fractions, not counts (see above).
- There are no coordinates, so `g_base_base` cannot be computed geometrically from these files.

## Open questions

1. Does "response time" include the pre-travel delay (dispatch + chute/turnout time), or is it travel time only? The page does not say. The papers cited above should be checked. This matters for g(j, j2) (relocations have no dispatch delay) and for the 8-minute threshold.
2. The page states no **licence** or terms of use. Ask the author before redistributing the data.
3. Do the six 180 s / 90 s entries mean "station located in this node"? If so, those nodes would be better proxies for the station locations of 11–16, which the current nearest-node rule already picks. Stations 1–10 have no equivalent.
4. Is the busy time (44.86 min) for all calls or only urgent ones, and does it include hospital time?
5. The calls are 45,264 in total, of which 13,203 are urgent. Should the model weight areas by all calls (as here) or by urgent calls? The file gives only one set of fractions.
6. Which period, and which time of day, does the data cover? The page does not say.

## Not included

No scenario data (ambulance positions, home bases, shift minutes, sleeping crews). These come from the instance generator.
