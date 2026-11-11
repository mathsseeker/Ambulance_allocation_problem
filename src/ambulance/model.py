"""Gurobi models: section 5 (solve_exact), Model H (solve_hard), Model E (solve_elastic).

Every solve function ALWAYS returns a result dict and never raises. `status` is one of:
    OPTIMAL          proven optimum
    TIME_LIMIT       time limit hit; `assignment` is the best solution found (None if none)
    INFEASIBLE       proven infeasible (Model H: see `iis_families`)
    PRECHECK_FAILED  spec 6b checks failed; not solved (see `message`)
    SIZE_LIMIT       model too large for the size-limited Gurobi licence
    ERROR            anything else (see `message`)
`message` is always a one-line human-readable explanation.
"""
from __future__ import annotations

import time

import gurobipy as gp
from gurobipy import GRB

from .instance import Instance

FAMILY = {"c1": "(1)", "c2": "(2)", "c3": "(3)", "c4": "(4)", "c7": "(7)", "c9H": "(9H)", "c9E": "(9E)"}


def _base_result(inst: Instance, variant: str) -> dict:
    return {
        "model": variant, "instance": inst.name, "status": None, "infeasible": None, "message": "",
        "assignment": None, "objective": None, "coverage_term": None, "moving_cost_term": None,
        "moving_minutes": None, "uncovered_term": None, "violation_term": None, "n_moves": None,
        "runtime": 0.0, "mip_gap": None, "time_limit_hit": False,
        "n_outside_V2": inst.n_outside_V2, "n_violated": None,
        "iis_families": None, "iis_implied": None, "n_vars": None, "n_constrs": None,
        "forced_moves": inst.forced_moves,
        "overtime_minutes": None, "extra_moves": None, "o_var": None, "regular": None,
        "guarantee_ok": inst.robust_guaranteed_feasible(),
    }


def _build(inst: Instance, variant: str):
    m = gp.Model(f"{variant}_{inst.name}")
    m.Params.OutputFlag = 0
    I, J, V = range(inst.nI), range(inst.nJ), range(inst.nV)

    # x only for allowed pairs: (5) and (6) are enforced by not creating the variable.
    x = {(i, j): m.addVar(vtype=GRB.BINARY, name=f"x[{i},{j}]") for i in I for j in inst.allowed[i]}
    y = {(v, k): m.addVar(vtype=GRB.BINARY, name=f"y[{v},{k}]")
         for v in V for k in range(1, int(inst.ymax[v]) + 1)}
    u = {v: m.addVar(vtype=GRB.BINARY, name=f"u[{v}]") for v in V} if inst.P > 0 else {}
    w = {v: m.addVar(vtype=GRB.BINARY, name=f"w[{v}]") for v in inst.V2} if variant == "elastic" else {}

    at_base = {j: gp.quicksum(x[i, j] for i in I if (i, j) in x) for j in J}

    for i in I:                                                     # (1)
        m.addConstr(gp.quicksum(x[i, j] for j in inst.allowed[i]) == 1, name=f"c1[{i}]")
    for v in V:                                                     # (2)
        if inst.ymax[v] == 0:
            continue  # no base within T: both sides are 0, constraint is empty
        m.addConstr(gp.quicksum(y[v, k] for k in range(1, int(inst.ymax[v]) + 1))
                    <= gp.quicksum(inst.a[j, v] * (at_base[j] + inst.e[j]) for j in J if inst.a[j, v]),
                    name=f"c2[{v}]")
    for j in J:                                                     # (3)
        m.addConstr(at_base[j] + inst.e[j] <= inst.C[j], name=f"c3[{j}]")
    stay = gp.quicksum(x[i, int(inst.delta[i])] for i in I if (i, int(inst.delta[i])) in x)
    m.addConstr(inst.nI - stay <= inst.M, name="c4")                # (4)
    for v in u:                                                     # (7)
        m.addConstr(u[v] >= 1 - (y[v, 1] if (v, 1) in y else 0), name=f"c7[{v}]")
    if variant in ("hard", "elastic"):                              # (9H) / (9E)
        for v in inst.V2:
            lhs = gp.quicksum(inst.b[j, v] * (at_base[j] + inst.e[j]) for j in J if inst.b[j, v])
            if variant == "hard":
                m.addConstr(lhs >= 1, name=f"c9H[{v}]")
            else:
                m.addConstr(lhs >= 1 - w[v], name=f"c9E[{v}]")

    coverage = gp.quicksum(inst.d[v] * (1 - inst.q) * inst.q ** (k - 1) * y[v, k] for (v, k) in y)
    moving = gp.quicksum(inst.c[i, j] * x[i, j] for (i, j) in x)
    obj = coverage - inst.lam * moving - inst.P * gp.quicksum(u.values())
    if w:
        obj -= inst.P2 * gp.quicksum(w.values())
    m.setObjective(obj, GRB.MAXIMIZE)
    return m, x, y, u, w


def _iis(m: gp.Model, inst: Instance, time_left: float):
    try:
        m.Params.TimeLimit = max(1.0, time_left)
        m.computeIIS()
    except gp.GurobiError:
        return None, None
    fams, ambs = set(), []
    for con in m.getConstrs():
        if con.IISConstr:
            prefix = con.ConstrName.split("[")[0]
            fams.add(FAMILY.get(prefix, prefix))
            if prefix == "c1":
                ambs.append(int(con.ConstrName[3:-1]))
    # (5)/(6) remove variables, so they cannot appear in an IIS by name. Flag them when an
    # ambulance in the IIS has its base choice restricted by them.
    implied = set()
    S = set(inst.S)
    for i in ambs:
        if any(j in S for j in range(inst.nJ)):
            implied.add("(6)")
        if any(j not in S and j != inst.h[i] and inst.r[i, j] > inst.s[i] for j in range(inst.nJ)):
            implied.add("(5)")
    return " ".join(sorted(fams)), " ".join(sorted(implied))


def _solve(inst: Instance, variant: str, time_limit: float = 60) -> dict:
    res = _base_result(inst, variant)
    t0 = time.perf_counter()
    try:
        problems = inst.precheck()
        if problems:
            res.update(status="PRECHECK_FAILED", infeasible=True, message="; ".join(problems))
            return res

        m, x, y, u, w = _build(inst, variant)
        m.Params.TimeLimit = time_limit
        m.Params.MIPGap = 0.0
        m.Params.MIPGapAbs = 1e-10
        m.Params.DualReductions = 0       # so infeasible models report INFEASIBLE, not INF_OR_UNBD
        m.update()
        res.update(n_vars=m.NumVars, n_constrs=m.NumConstrs)
        m.optimize()
        st = m.Status
        res["time_limit_hit"] = st == GRB.TIME_LIMIT

        if st == GRB.INFEASIBLE:
            res.update(status="INFEASIBLE", infeasible=True)
            if variant == "hard":
                fams, implied = _iis(m, inst, time_limit - (time.perf_counter() - t0))
                res.update(iis_families=fams, iis_implied=implied)
                res["message"] = f"Model H infeasible; IIS families: {fams or 'n/a'}" + \
                                 (f" (restricted by {implied})" if implied else "")
            elif inst.forced_moves > inst.M:
                res["message"] = (f"{variant} model infeasible: {inst.forced_moves} ambulances must move "
                                  f"(sleeping base or shift rule) but M = {inst.M}")
            else:
                res["message"] = f"{variant} model infeasible (section-5 constraints cannot all hold)"
            return res

        if st not in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL):
            res.update(status="ERROR", message=f"Gurobi status code {st}")
            return res
        if m.SolCount == 0:
            res.update(status="TIME_LIMIT", infeasible=None,
                       message=f"time limit {time_limit}s hit with no feasible solution found")
            return res

        assignment = {i: j for (i, j), var in x.items() if var.X > 0.5}
        cov = sum(inst.d[v] * (1 - inst.q) * inst.q ** (k - 1) for (v, k), var in y.items() if var.X > 0.5)
        minutes = sum(inst.c[i, j] for i, j in assignment.items())
        n_viol = int(round(sum(var.X for var in w.values()))) if variant == "elastic" else None
        res.update(
            status="OPTIMAL" if st == GRB.OPTIMAL else "TIME_LIMIT", infeasible=False,
            assignment=assignment, objective=m.ObjVal, coverage_term=cov,
            moving_cost_term=inst.lam * minutes, moving_minutes=minutes,
            uncovered_term=inst.P * sum(var.X for var in u.values()),
            violation_term=inst.P2 * n_viol if variant == "elastic" else 0.0,
            n_moves=sum(1 for i, j in assignment.items() if j != inst.delta[i]),
            mip_gap=m.MIPGap, n_violated=n_viol,
        )
        res["message"] = ("optimal" if st == GRB.OPTIMAL else f"time limit hit, gap {m.MIPGap:.2%}") + \
            f": objective {m.ObjVal:.6f}, {res['n_moves']} moves" + \
            (f", {n_viol} areas violate the 2T rule" if variant == "elastic" else "")
        return res
    except gp.GurobiError as exc:
        if exc.errno == 10010 or "size-limited" in str(exc):
            res.update(status="SIZE_LIMIT", message=f"model too large for the size-limited Gurobi licence "
                                                    f"({res['n_vars']} vars, {res['n_constrs']} constraints)")
        else:
            res.update(status="ERROR", message=f"Gurobi error {exc.errno}: {exc}")
        return res
    except Exception as exc:  # never let a solve crash an experiment
        res.update(status="ERROR", message=f"{type(exc).__name__}: {exc}")
        return res
    finally:
        res["runtime"] = time.perf_counter() - t0


def solve_exact(inst: Instance, time_limit: float = 60) -> dict:
    """Section 5 model."""
    return _solve(inst, "base", time_limit)


def solve_hard(inst: Instance, time_limit: float = 60) -> dict:
    """Model H: section 5 + (9H)."""
    return _solve(inst, "hard", time_limit)


def solve_elastic(inst: Instance, time_limit: float = 60) -> dict:
    """Model E: section 5 + (9E) + P2 penalty."""
    return _solve(inst, "elastic", time_limit)


# ---------------------------------------------------------------------------
# Model R (robust), ported from reference/robust_model_reference.py (same logic)
# ---------------------------------------------------------------------------
PRIORITY = ("violations", "overtime", "extra_moves", "regular")   # fixed, highest first


PRIORITY_OVERTIME_FIRST = ("overtime", "violations", "extra_moves", "regular")   # experiment only


def solve_robust(inst: Instance, time_limit: float = 60) -> dict:
    """Model E with a soft move limit (moves <= M + o) and a soft shift rule (overtime
    minutes ot[i, j] charged instead of forbidding x[i, j]). Hard: (1), (3), (6).
    Lexicographic objective via Gurobi hierarchical multi-objective (reltol = 0), in the
    fixed order PRIORITY: 2T violations, overtime, extra moves, regular objective.
    `objective` in the result is the regular objective R."""
    return _solve_robust(inst, PRIORITY, "robust", time_limit)


def solve_robust_overtime_first(inst: Instance, time_limit: float = 60) -> dict:
    """EXPERIMENT, not the project's Model R: same model, but overtime minutes are
    minimised before 2T violations (PRIORITY_OVERTIME_FIRST)."""
    return _solve_robust(inst, PRIORITY_OVERTIME_FIRST, "robust_ot_first", time_limit)


def _solve_robust(inst: Instance, priority, model_name: str, time_limit: float) -> dict:
    res = _base_result(inst, model_name)
    t0 = time.perf_counter()
    try:
        if not inst.robust_guaranteed_feasible():
            res.update(status="PRECHECK_FAILED", infeasible=True,
                       message="capacity condition fails: some e_j > C_j or free non-sleeping capacity < |I|")
            return res

        m = gp.Model(f"robust_{inst.name}")
        m.Params.OutputFlag = 0
        I, J, V = range(inst.nI), range(inst.nJ), range(inst.nV)
        S = set(inst.S)

        # x only for non-sleeping bases (6); no shift-rule removal.
        x = {(i, j): m.addVar(vtype=GRB.BINARY, name=f"x[{i},{j}]") for i in I for j in J if j not in S}
        for i in I:                                                     # (1)
            m.addConstr(gp.quicksum(x[i, j] for j in J if j not in S) == 1, name=f"c1[{i}]")
        at_base = {j: gp.quicksum(x[i, j] for i in I if (i, j) in x) for j in J}
        for j in J:                                                     # (3)
            m.addConstr(at_base[j] + inst.e[j] <= inst.C[j], name=f"c3[{j}]")
        o = m.addVar(vtype=GRB.INTEGER, lb=0, name="o")                 # (4-soft)
        moves = gp.quicksum(1 - x[i, int(inst.delta[i])] if (i, int(inst.delta[i])) in x else 1 for i in I)
        m.addConstr(moves <= inst.M + o, name="c4")

        y = {(v, k): m.addVar(vtype=GRB.BINARY, name=f"y[{v},{k}]")
             for v in V for k in range(1, int(inst.ymax[v]) + 1)}
        for v in V:                                                     # (2)
            if inst.ymax[v] == 0:
                continue  # both sides are 0
            m.addConstr(gp.quicksum(y[v, k] for k in range(1, int(inst.ymax[v]) + 1))
                        <= gp.quicksum(at_base[j] + inst.e[j] for j in J if inst.a[j, v]), name=f"c2[{v}]")
        u = {}
        if inst.P > 0:                                                  # (7)
            for v in V:
                u[v] = m.addVar(vtype=GRB.BINARY, name=f"u[{v}]")
                if inst.ymax[v] >= 1:
                    m.addConstr(u[v] >= 1 - y[v, 1], name=f"c7[{v}]")
                else:
                    m.addConstr(u[v] == 1, name=f"c7[{v}]")
        w = {}
        for v in inst.V2:                                               # (9E)
            w[v] = m.addVar(vtype=GRB.BINARY, name=f"w[{v}]")
            m.addConstr(gp.quicksum(at_base[j] + inst.e[j] for j in J if inst.b[j, v]) >= 1 - w[v],
                        name=f"c9E[{v}]")

        cov = gp.quicksum(inst.d[v] * (1 - inst.q) * inst.q ** (k - 1) * y[v, k] for (v, k) in y)
        moving = gp.quicksum(inst.c[i, j] * x[i, j] for (i, j) in x)
        regular = cov - inst.lam * moving - inst.P * gp.quicksum(u.values())
        levels = {
            "overtime": gp.quicksum(int(inst.ot[i, j]) * x[i, j] for (i, j) in x),
            "violations": gp.quicksum(w.values()),
            "extra_moves": o + 0,
            "regular": -regular,                                        # all levels minimised
        }
        m.ModelSense = GRB.MINIMIZE
        n = len(priority)
        for idx, name in enumerate(priority):
            m.setObjectiveN(levels[name], index=idx, priority=n - idx, weight=1.0,
                            abstol=1e-9, reltol=0.0, name=name)
        m.Params.TimeLimit = time_limit
        m.Params.MIPGap = 0.0
        m.update()
        res.update(n_vars=m.NumVars, n_constrs=m.NumConstrs)
        m.optimize()
        st = m.Status
        res["time_limit_hit"] = st == GRB.TIME_LIMIT
        if st == GRB.INFEASIBLE:
            res.update(status="INFEASIBLE", infeasible=True,
                       message="Model R infeasible (should not happen when the capacity condition holds)")
            return res
        if st not in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL):
            res.update(status="ERROR", message=f"Gurobi status code {st}")
            return res
        if m.SolCount == 0:
            res.update(status="TIME_LIMIT", message=f"time limit {time_limit}s hit with no feasible solution")
            return res

        assignment = {i: j for (i, j), var in x.items() if var.X > 0.5}
        from .evaluate import evaluate
        ev = evaluate(inst, assignment, "robust")
        res.update(
            status="OPTIMAL" if st == GRB.OPTIMAL else "TIME_LIMIT", infeasible=False,
            assignment=assignment, objective=ev["regular"], regular=ev["regular"],
            coverage_term=ev["coverage_term"], moving_cost_term=ev["moving_cost_term"],
            moving_minutes=ev["moving_minutes"], uncovered_term=ev["uncovered_term"], violation_term=None,
            n_moves=ev["n_moves"], n_violated=ev["n_violated_9"], overtime_minutes=ev["overtime_minutes"],
            extra_moves=ev["extra_moves"], o_var=int(round(o.X)), mip_gap=0.0 if st == GRB.OPTIMAL else None,
        )
        res["message"] = ("optimal" if st == GRB.OPTIMAL else "time limit hit (best plan so far)") + \
            f": overtime {ev['overtime_minutes']} min, {ev['n_violated_9']} 2T-rule violations, " \
            f"{ev['n_moves']} moves ({ev['extra_moves']} above M), coverage {ev['coverage_term']:.6f}"
        return res
    except gp.GurobiError as exc:
        if exc.errno == 10010 or "size-limited" in str(exc):
            res.update(status="SIZE_LIMIT", message=f"model too large for the size-limited Gurobi licence "
                                                    f"({res['n_vars']} vars, {res['n_constrs']} constraints)")
        else:
            res.update(status="ERROR", message=f"Gurobi error {exc.errno}: {exc}")
        return res
    except Exception as exc:
        res.update(status="ERROR", message=f"{type(exc).__name__}: {exc}")
        return res
    finally:
        res["runtime"] = time.perf_counter() - t0
