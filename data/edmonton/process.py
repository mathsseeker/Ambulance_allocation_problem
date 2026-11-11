import sys, os, json, csv, statistics as st

base = sys.argv[1]
raw, out = os.path.join(base, "raw"), os.path.join(base, "processed")

def matrix(name):
    rows = {}
    for line in open(os.path.join(raw, name)).read().splitlines()[2:]:
        tok = line.split()
        if not tok:
            continue
        if not tok[0].isdigit():
            tok = tok[1:]  # drop "Demand"/"node" label
        assert len(tok) == 17, (name, line)
        rows[int(tok[0])] = [float(x) for x in tok[1:]]
    assert sorted(rows) == list(range(1, 181)), name
    return rows

mean_s = matrix("average_of_response_times_in_seconds.txt")
sd_s = matrix("stdev_of_response_times_in_seconds.txt")
det = matrix("deterministic_coverage_for_8_minute_threshold.txt")
prob = matrix("probabilistic_coverage_for_8_minute_threshold.txt")
V, J = list(range(1, 181)), list(range(1, 17))

# demand
lines = open(os.path.join(raw, "numberofcallsdemanddata.txt")).read().splitlines()
TOTAL = int(lines[1].strip()); URGENT = int(lines[3].strip())
frac = {int(a): float(b) for a, b in (l.split() for l in lines[6:] if l.strip())}
assert sorted(frac) == V
calls = {v: round(frac[v] * TOTAL) for v in V}
assert sum(calls.values()) == TOTAL
max_dev = max(abs(frac[v] * TOTAL - calls[v]) for v in V)
with open(os.path.join(out, "areas.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["v", "calls", "d_v", "frac_raw", "method"])
    for v in V:
        w.writerow([v, calls[v], f"{calls[v]/TOTAL:.10f}", f"{frac[v]:.6f}",
                    "calls=round(frac_raw*total_calls); d_v=calls/total_calls"])

# capacities
cap = {}
for l in open(os.path.join(raw, "station_capacities.txt")).read().splitlines()[1:]:
    if l.strip():
        a, b = l.split(); cap[int(a)] = int(b)
assert sorted(cap) == J
with open(os.path.join(out, "bases.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["j", "C_j"])
    for j in J: w.writerow([j, cap[j]])

# travel times (min)
t = {(j, v): mean_s[v][j-1] / 60 for j in J for v in V}
s = {(j, v): sd_s[v][j-1] / 60 for j in J for v in V}
with open(os.path.join(out, "t_base_area.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["j", "v", "t_min", "sigma_min"])
    for j in J:
        for v in V: w.writerow([j, v, f"{t[j,v]:.6f}", f"{s[j,v]:.6f}"])

# base-base approx
nearest = {j2: min(V, key=lambda v: t[j2, v]) for j2 in J}
with open(os.path.join(out, "g_base_base.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["j", "j2", "g_min", "method", "proxy_node_v"])
    for j in J:
        for j2 in J:
            g = 0.0 if j == j2 else t[j, nearest[j2]]
            w.writerow([j, j2, f"{g:.6f}", "zero_diagonal" if j == j2 else "approx_nearest_node",
                        "" if j == j2 else nearest[j2]])

busy_s = float(open(os.path.join(raw, "average_busy_time_for_ambulances_in_seconds.txt")).read().strip())
json.dump({"mean_busy_time_min": busy_s / 60, "mean_busy_time_s_raw": busy_s,
           "n_areas": len(V), "n_bases": len(J), "total_capacity": sum(cap.values()),
           "total_calls": TOTAL, "urgent_calls": URGENT,
           "model_r": {
               "c_v": round(st.median(s[k] / t[k] for k in t), 4),
               "c_v_method": "derived: median of sigma_min/t_min over all 2880 base-area pairs",
               "T_recommended_min": [8, 10],
               "T_method": "recommendation, not data: T=30 (Model R default) makes a_jv and b_jv almost all 1 on this instance; see README",
               "C_j_source": "use bases.csv (real capacities 1-3), not the Model R default C_j=2",
               "q": None,
               "q_method": "not derivable: the source does not state the period covered by total_calls; must be set as an assumption",
               "t_jv_note": "source gives response time, which may include pre-travel delay; Model R expects driving time",
           }},
          open(os.path.join(out, "params.json"), "w"), indent=2)

# ---- checks ----
R = {}
R["sum_d_v"] = sum(calls[v]/TOTAL for v in V)
R["sum_frac_raw"] = sum(frac.values())
R["max_round_dev"] = max_dev
tv, sv = list(t.values()), list(s.values())
R["t_bad"] = sum(1 for x in tv if not (x > 0)); R["s_bad"] = sum(1 for x in sv if not (x > 0))
R["t_zero"] = sum(1 for x in tv if x == 0); R["s_zero"] = sum(1 for x in sv if x == 0)
cv = [s[k]/t[k] for k in t]
R["t_stats"] = (min(tv), st.median(tv), max(tv))
R["s_stats"] = (min(sv), st.median(sv), max(sv))
R["cv_stats"] = (min(cv), st.median(cv), max(cv))
d = {v: calls[v]/TOTAL for v in V}
R["cov"] = {}
for T in (8, 15, 30):
    n = {v: sum(1 for j in J if t[j, v] <= T) for v in V}
    R["cov"][T] = (100*sum(1 for v in V if n[v] > 0)/len(V), 100*sum(d[v] for v in V if n[v] > 0),
                   st.mean(n.values()), sum(1 for v in V if n[v] == 16), 100*sum(d[v]*n[v] for v in V)/16/1)
R["prob"] = {}
for z in (1.645, 1.881, 2.326):
    n = {v: sum(1 for j in J if t[j, v] + z*s[j, v] <= 30) for v in V}
    R["prob"][z] = (sum(1 for v in V if n[v] > 0), 100*sum(d[v] for v in V if n[v] > 0), st.mean(n.values()))
mism = [(j, v, t[j, v], det[v][j-1]) for j in J for v in V if (t[j, v] <= 8) != (det[v][j-1] == 1)]
R["det_mismatch"] = mism
R["det_ones"] = sum(1 for v in V for x in det[v] if x == 1)
R["det_values"] = sorted({x for v in V for x in det[v]})
R["nearest"] = nearest
R["prob_range"] = (min(x for v in V for x in prob[v]), max(x for v in V for x in prob[v]))
R["base_nearest_t"] = {j: t[j, nearest[j]] for j in J}
for k, val in R.items(): print(k, val)
