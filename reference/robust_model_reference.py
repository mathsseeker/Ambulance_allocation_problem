"""
Reference implementation of the ROBUST ambulance relocation model (Model R).

Model R = Model E (elastic 2T rule) with two more rules made soft:
  * move limit (4)  -> soft: moves above M are allowed but penalised (option b)
  * shift rule (5)  -> soft: any base is allowed, overtime minutes are penalised

The 30-minute rule is now the 2T rule: the outer limit is T2 = 2 * T (T = 30 -> T2 = 60).

Penalties are applied lexicographically with Gurobi's hierarchical multi-objective
(fixed order, highest priority first):
  1. 2T-rule violations        (minimise sum of w[v])
  2. overtime minutes          (minimise)
  3. extra moves above M       (minimise o)
  4. regular objective R       (maximise coverage - lam*moving - P*uncovered)

Why hierarchical and not one weighted sum: the penalties must dominate the coverage
term (coefficients around 1e-5), which needs weights around 1e4 or more. With Gurobi's
default relative MIP gap (1e-4), a single weighted objective of that size would let the
coverage part be solved only approximately. Each level here is optimised on its own.

Hard rules that stay hard: (1) one base each, (3) capacity, (6) sleeping bases.
Feasibility guarantee: Model R is feasible whenever
      e[j] <= C[j] for all j   and   sum_{j not in S} (C[j] - e[j]) >= |I|
because every ambulance can then be placed on a free spot at a non-sleeping base,
and every other variable (y = 0, w = 1, u = 1, o = |I|) can absorb the rest.

Instance format: a dict with keys
  I, J, V          lists of ids
  S                set of sleeping bases (subset of J)
  d[v]             demand share, sums to 1
  q, T, alpha, cv, lam, P, M     (T2 is not an input: T2 = 2 * T)
  t[(j, v)]        travel time base -> area (minutes)
  g[(j, jp)]       travel time base -> base (minutes), g[(j, j)] = 0
  delta[i], h[i]   current/heading base and home base of ambulance i
  s[i]             minutes left in the shift of ambulance i
  e[j], C[j]       non-movable ambulances at base j, capacity of base j

Adapt the loader to your existing instance class; the model code only needs these fields.
Run this file directly for a small self-test (no data file needed).
"""
import math
import random

import gurobipy as gp
from gurobipy import GRB
from scipy.stats import norm

PRIORITY = ("violations", "overtime", "extra_moves", "regular")


# ---------------------------------------------------------------------------
# computed parameters
# ---------------------------------------------------------------------------
def derived(inst):
    I, J, V = inst["I"], inst["J"], inst["V"]
    t, g = inst["t"], inst["g"]
    z = norm.ppf(inst["alpha"])
    T2 = 2 * inst["T"]
    a = {(j, v): int(t[j, v] <= inst["T"]) for j in J for v in V}
    b = {(j, v): int(t[j, v] * (1 + z * inst["cv"]) <= T2) for j in J for v in V}
    V2 = [v for v in V if any(b[j, v] for j in J)]
    c = {(i, j): g[inst["delta"][i], j] for i in I for j in J}
    r = {(i, j): c[i, j] + g[j, inst["h"][i]] for i in I for j in J}
    # overtime in whole minutes, rounded up, so any lateness counts as at least 1
    ot = {(i, j): max(0, math.ceil(r[i, j] - inst["s"][i] - 1e-9)) for i in I for j in J}
    Kbar = len(I) + sum(inst["e"][j] for j in J)
    kmax = {v: min(Kbar, sum(a[j, v] * inst["C"][j] for j in J)) for v in V}
    return dict(T2=T2, z=z, a=a, b=b, V2=V2, c=c, r=r, ot=ot, kmax=kmax)


def robust_is_guaranteed_feasible(inst):
    J, S, e, C = inst["J"], inst["S"], inst["e"], inst["C"]
    if any(e[j] > C[j] for j in J):
        return False
    return sum(C[j] - e[j] for j in J if j not in S) >= len(inst["I"])


# ---------------------------------------------------------------------------
# shared pieces
# ---------------------------------------------------------------------------
def _coverage_part(m, inst, D, x_of_base):
    """Adds y, u, w and constraints (2), (7), (9E). Returns (coverage expr, u, w, y)."""
    V, J, d, q = inst["V"], inst["J"], inst["d"], inst["q"]
    e, a, b = inst["e"], D["a"], D["b"]
    y = {(v, k): m.addVar(vtype=GRB.BINARY, name=f"y[{v},{k}]")
         for v in V for k in range(1, D["kmax"][v] + 1)}
    for v in V:  # (2)
        m.addConstr(gp.quicksum(y[v, k] for k in range(1, D["kmax"][v] + 1))
                    <= gp.quicksum(a[j, v] * (x_of_base[j] + e[j]) for j in J), name=f"cov[{v}]")
    u = {}
    if inst["P"] > 0:  # (7)
        for v in V:
            u[v] = m.addVar(vtype=GRB.BINARY, name=f"u[{v}]")
            if D["kmax"][v] >= 1:
                m.addConstr(u[v] >= 1 - y[v, 1], name=f"unc[{v}]")
            else:
                m.addConstr(u[v] == 1, name=f"unc[{v}]")
    w = {}
    for v in D["V2"]:  # (9E)
        w[v] = m.addVar(vtype=GRB.BINARY, name=f"w[{v}]")
        m.addConstr(gp.quicksum(b[j, v] * (x_of_base[j] + e[j]) for j in J) >= 1 - w[v],
                    name=f"t2[{v}]")
    cov = gp.quicksum(d[v] * (1 - q) * q ** (k - 1) * y[v, k] for (v, k) in y)
    return cov, u, w, y


def _extract(m, inst, D, x, o=None, extra=None):
    res = {"status": m.Status, "runtime": m.Runtime}
    if m.Status != GRB.OPTIMAL:
        res["feasible"] = False
        return res
    assign = {}
    for (i, j), var in x.items():
        if var.X > 0.5:
            assign[i] = j
    res.update(feasible=True, assignment=assign)
    res.update(evaluate(inst, assign, D))
    if o is not None:
        res["o_var"] = round(o.X)
    if extra:
        res.update(extra)
    return res


# ---------------------------------------------------------------------------
# Model R (robust): soft move limit (option b) + soft shift rule
# ---------------------------------------------------------------------------
def solve_robust(inst, time_limit=60, verbose=False):
    I, J, S = inst["I"], inst["J"], inst["S"]
    D = derived(inst)
    m = gp.Model("robust")
    m.Params.OutputFlag = int(verbose)
    m.Params.TimeLimit = time_limit
    m.Params.MIPGap = 0.0

    # x only for non-sleeping bases (6). No shift-rule removal: overtime is penalised instead.
    x = {(i, j): m.addVar(vtype=GRB.BINARY, name=f"x[{i},{j}]") for i in I for j in J if j not in S}
    for i in I:  # (1)
        m.addConstr(gp.quicksum(x[i, j] for j in J if j not in S) == 1, name=f"one[{i}]")
    x_of_base = {j: gp.quicksum(x[i, j] for i in I if (i, j) in x) for j in J}
    for j in J:  # (3)
        m.addConstr(x_of_base[j] + inst["e"][j] <= inst["C"][j], name=f"cap[{j}]")

    # (4-soft): moves <= M + o, o integer >= 0. An ambulance whose current base is a
    # sleeping base has no x[i, delta_i] and always counts as a move.
    o = m.addVar(vtype=GRB.INTEGER, lb=0, name="o")
    moves = gp.quicksum(1 - x[i, inst["delta"][i]] if (i, inst["delta"][i]) in x else 1 for i in I)
    m.addConstr(moves <= inst["M"] + o, name="moves")

    cov, u, w, _ = _coverage_part(m, inst, D, x_of_base)
    moving = gp.quicksum(D["c"][i, j] * x[i, j] for (i, j) in x)
    regular = cov - inst["lam"] * moving - inst["P"] * gp.quicksum(u.values())

    levels = {
        "overtime": gp.quicksum(D["ot"][i, j] * x[i, j] for (i, j) in x),
        "violations": gp.quicksum(w.values()),
        "extra_moves": o + 0,
        "regular": -regular,  # all levels are minimised
    }
    m.ModelSense = GRB.MINIMIZE
    n = len(PRIORITY)
    for idx, name in enumerate(PRIORITY):
        m.setObjectiveN(levels[name], index=idx, priority=n - idx, weight=1.0,
                        abstol=1e-9, reltol=0.0, name=name)
    m.optimize()
    return _extract(m, inst, D, x, o)


# ---------------------------------------------------------------------------
# current strict Model E (for comparison): hard move limit + hard shift rule
# ---------------------------------------------------------------------------
def solve_strict_elastic(inst, time_limit=60, verbose=False):
    I, J, S = inst["I"], inst["J"], inst["S"]
    D = derived(inst)
    m = gp.Model("strict_E")
    m.Params.OutputFlag = int(verbose)
    m.Params.TimeLimit = time_limit
    m.Params.MIPGap = 0.0
    allowed = {(i, j) for i in I for j in J
               if j not in S and (j == inst["h"][i] or D["r"][i, j] <= inst["s"][i])}  # (5), (6)
    x = {(i, j): m.addVar(vtype=GRB.BINARY, name=f"x[{i},{j}]") for (i, j) in allowed}
    for i in I:  # (1)
        m.addConstr(gp.quicksum(x[i, j] for j in J if (i, j) in x) == 1, name=f"one[{i}]")
    x_of_base = {j: gp.quicksum(x[i, j] for i in I if (i, j) in x) for j in J}
    for j in J:  # (3)
        m.addConstr(x_of_base[j] + inst["e"][j] <= inst["C"][j], name=f"cap[{j}]")
    moves = gp.quicksum(1 - x[i, inst["delta"][i]] if (i, inst["delta"][i]) in x else 1 for i in I)
    m.addConstr(moves <= inst["M"], name="moves")  # (4) hard
    cov, u, w, _ = _coverage_part(m, inst, D, x_of_base)
    moving = gp.quicksum(D["c"][i, j] * x[i, j] for (i, j) in x)
    P2 = 2 + inst["lam"] * sum(max(D["c"][i, j] for j in J) for i in I) + inst["P"] * len(inst["V"])
    m.setObjective(cov - inst["lam"] * moving - inst["P"] * gp.quicksum(u.values())
                   - P2 * gp.quicksum(w.values()), GRB.MAXIMIZE)
    m.optimize()
    return _extract(m, inst, D, x)


# ---------------------------------------------------------------------------
# evaluation of any assignment, without Gurobi
# ---------------------------------------------------------------------------
def evaluate(inst, assign, D=None):
    D = D or derived(inst)
    I, J, V = inst["I"], inst["J"], inst["V"]
    n_at = {j: inst["e"][j] for j in J}
    for i in I:
        n_at[assign[i]] += 1
    cover_n = {v: sum(D["a"][j, v] * n_at[j] for j in J) for v in V}
    q = inst["q"]
    coverage = sum(inst["d"][v] * (1 - q ** cover_n[v]) for v in V)
    moving = sum(D["c"][i, assign[i]] for i in I)
    uncovered = sum(1 for v in V if cover_n[v] == 0)
    n_moves = sum(1 for i in I if assign[i] != inst["delta"][i])
    violations = sum(1 for v in D["V2"] if sum(D["b"][j, v] * n_at[j] for j in J) == 0)
    overtime = sum(D["ot"][i, assign[i]] for i in I)
    hard_ok = (all(n_at[j] <= inst["C"][j] for j in J)
               and all(assign[i] not in inst["S"] for i in I))
    return dict(
        coverage=coverage, moving_time=moving, uncovered=uncovered,
        regular=coverage - inst["lam"] * moving - inst["P"] * uncovered,
        moves=n_moves, extra_moves=max(0, n_moves - inst["M"]),
        violations=violations, outside_V2=len(V) - len(D["V2"]),
        overtime_minutes=overtime, hard_rules_ok=hard_ok,
    )


# ---------------------------------------------------------------------------
# self-test on synthetic instances (no data file needed)
# ---------------------------------------------------------------------------
def tiny_conflict_instance():
    """Strict models are infeasible here by construction; Model R must still solve it."""
    J, V = [0, 1, 2], list(range(6))
    pos_b = {0: 0.0, 1: 10.0, 2: 20.0}
    pos_v = {v: 4.0 * v for v in V}
    t = {(j, v): abs(pos_b[j] - pos_v[v]) * 1.5 for j in J for v in V}
    g = {(j, k): abs(pos_b[j] - pos_b[k]) * 1.5 for j in J for k in J}
    return dict(I=[0, 1, 2], J=J, V=V, S=set(), d={v: 1 / 6 for v in V}, q=0.3, T=15,
                alpha=0.97, cv=0.2, lam=0.0, P=0.0, M=1, t=t, g=g,
                delta={0: 0, 1: 0, 2: 1}, h={0: 0, 1: 1, 2: 2}, s={0: 300, 1: 10, 2: 300},
                e={0: 0, 1: 0, 2: 0}, C={0: 1, 1: 1, 2: 1})
    # Base 0 holds 2 ambulances but has capacity 1. Ambulance 1 needs 15 min to get home
    # but has 10 min left, so the strict shift rule only allows its home base 1, where
    # ambulance 2 sits: strict needs 2 moves, but M = 1 -> strict is infeasible.
    # Model R sees that ambulance 1 is 5 min late whether it stays or goes home, so it
    # keeps it at base 0, moves ambulance 0 instead: 1 move, 5 overtime minutes.


def random_instance(rng, nV=30, nJ=6, nI=6, night=False):
    J, V = list(range(nJ)), list(range(nV))
    pb = {j: (rng.uniform(0, 60), rng.uniform(0, 60)) for j in J}
    pv = {v: (rng.uniform(0, 60), rng.uniform(0, 60)) for v in V}
    dist = lambda p, q: math.dist(p, q)
    t = {(j, v): dist(pb[j], pv[v]) for j in J for v in V}
    g = {(j, k): dist(pb[j], pb[k]) for j in J for k in J}
    pop = {v: rng.randint(500, 8000) for v in V}
    tot = sum(pop.values())
    S = set(rng.sample(J, 2)) if night else set()
    I = list(range(nI))
    free = [j for j in J if j not in S]
    return dict(I=I, J=J, V=V, S=S, d={v: pop[v] / tot for v in V}, q=0.3, T=30,
                alpha=0.97, cv=0.2, lam=0.0, P=0.0, M=rng.choice([1, 2, nI]), t=t, g=g,
                delta={i: rng.choice(J) for i in I}, h={i: rng.choice(free) for i in I},
                s={i: rng.randint(0, 480) for i in I},
                e={j: (1 if j in S else 0) for j in J}, C={j: 2 for j in J})


def _check(cond, msg):
    if not cond:
        raise AssertionError(msg)


if __name__ == "__main__":
    inst = tiny_conflict_instance()
    se = solve_strict_elastic(inst)
    ro = solve_robust(inst)
    print("tiny conflict instance")
    print("  strict E feasible:", se["feasible"])
    print("  robust  feasible:", ro["feasible"], "| moves", ro["moves"], "| extra moves", ro["extra_moves"],
          "| overtime min", ro["overtime_minutes"], "| violations", ro["violations"])
    _check(not se["feasible"] and ro["feasible"] and ro["extra_moves"] == 0
           and ro["overtime_minutes"] == 5, "tiny instance check failed")

    rng = random.Random(1)
    n = strict_ok = same = 0
    for it in range(300):
        inst = random_instance(rng, night=(it % 2 == 1))
        if not robust_is_guaranteed_feasible(inst):
            continue
        n += 1
        ro = solve_robust(inst)
        _check(ro["feasible"], f"robust infeasible on instance {it}")
        _check(ro["hard_rules_ok"], "robust broke a hard rule")
        _check(ro["o_var"] == ro["extra_moves"], "o does not equal the extra moves")
        se = solve_strict_elastic(inst)
        if se["feasible"]:
            strict_ok += 1
            # robust can only do better on violations (it may buy overtime or extra moves)
            _check(ro["violations"] <= se["violations"], "robust has more violations than strict")
            if se["overtime_minutes"] == 0 and ro["violations"] == se["violations"]:
                # with violations tied, it must match strict exactly on the rest
                _check(ro["overtime_minutes"] == 0, "robust has overtime where strict did not")
                _check(ro["extra_moves"] == 0, "robust used extra moves needlessly")
                _check(abs(ro["regular"] - se["regular"]) < 1e-6,
                       f"regular objective differs: {ro['regular']} vs {se['regular']}")
                same += 1
    print(f"random instances: {n} solved by robust (all feasible), strict E feasible on {strict_ok}, "
          f"identical regular objective on {same} comparable cases")
    print("ALL CHECKS PASSED")
