import argparse
import json
import math
import sys
import time

import gurobipy as gp

from gurobipy import GRB

STATUS = {GRB.OPTIMAL: "OPTIMAL", GRB.INFEASIBLE: "INFEASIBLE",
          GRB.TIME_LIMIT: "TIME_LIMIT", GRB.INF_OR_UNBD: "INF_OR_UNBD"}

# ---------------------------------------------------------------------------
# Instância
# ---------------------------------------------------------------------------

def read_instance(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        inst = json.load(f)
    for r in inst["resources"]:
        if not (len(r["A"]) == len(r["P"]) == len(r["E"])):
            raise ValueError(f"resource {r['id']}: A, P and E must have the same length")
    return inst


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

def solve_ecmtc(inst, eps_rel=1e-9, time_limit=3600, threads=0, verbose=False):
    T, D = inst["T"], inst["D"]
    resources = inst["resources"]

    # Conjuntos e parâmetros: R, A_i, P_i(j), E_i(j)
    R = range(len(resources))
    A = {i: resources[i]["A"] for i in R}
    P = {(i, j): p for i in R for j, p in zip(A[i], resources[i]["P"])}
    E = {(i, j): e for i in R for j, e in zip(A[i], resources[i]["E"])}

    m = gp.Model("ECMTC")
    m.Params.OutputFlag = 1 if verbose else 0
    m.Params.MIPGap = 0.0          # resolver até o ótimo
    m.Params.MIPGapAbs = 0.0
    m.Params.TimeLimit = time_limit
    if threads:
        m.Params.Threads = threads

    # Variáveis
    pairs = [(i, j) for i in R for j in A[i]]
    y = m.addVars(pairs, vtype=GRB.BINARY, name="y")
    cmax = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="Cmax")

    # Restrições
    # sum_{j in A_i} y_ij = 1, para todo i em R
    for i in R:
        m.addConstr(gp.quicksum(y[i, j] for j in A[i]) == 1, name=f"choice_{i}")
    # sum_{i in R} sum_{j in A_i} j y_ij = T
    m.addConstr(gp.quicksum(j * y[i, j] for i in R for j in A[i]) == T, name="total_tasks")
    # C_max >= sum_{j in A_i} P_i(j) y_ij, para todo i em R
    for i in R:
        m.addConstr(cmax >= gp.quicksum(P[i, j] * y[i, j] for j in A[i]), name=f"makespan_{i}")
    # C_max <= D
    m.addConstr(cmax <= D, name="deadline")

    # lex min (sum_ij E_i(j) y_ij , C_max)
    # Objetivos hierárquicos: prioridade maior = otimizado primeiro.
    # reltol/abstol = degradação permitida na energia ao otimizar o makespan (o eps).
    energy = gp.quicksum(E[i, j] * y[i, j] for i in R for j in A[i])
    m.ModelSense = GRB.MINIMIZE
    m.setObjectiveN(energy, index=0, priority=2, weight=1.0,
                    abstol=0.0, reltol=eps_rel, name="energy")
    m.setObjectiveN(cmax, index=1, priority=1, weight=1.0,
                    abstol=0.0, reltol=0.0, name="makespan")

    t0 = time.perf_counter()
    m.optimize()
    summary = {"solver_status": STATUS.get(m.Status, str(m.Status)),
               "time_s": time.perf_counter() - t0, "nodes": m.NodeCount,
               "num_binaries": len(y), "num_constraints": m.NumConstrs}
    if m.Status != GRB.OPTIMAL:
        return {"status": "not_optimal", **summary}

    solver_objectives = {}
    for k, name in enumerate(["energy", "makespan"]):
        m.Params.ObjNumber = k
        solver_objectives[name] = m.ObjNVal

    # Solução: j com y_ij = 1 para cada recurso
    x = {i: j for (i, j), v in y.items() if round(v.X) == 1}

    # objetivos recalculados a partir de P e E (independem de tolerâncias do solver)
    return {
        "status": "optimal",
        "total_energy": sum(E[i, x[i]] for i in R),
        "makespan": max(P[i, x[i]] for i in R),
        "num_selected": sum(1 for i in R if x[i] > 0),
        "assignment": [{"id": resources[i]["id"], "tasks": x[i],
                        "time": P[i, x[i]], "energy": E[i, x[i]],
                        "selected": x[i] > 0} for i in R],
        "solver_objectives": solver_objectives,
        **summary,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="ECMTC as an integer program (gurobipy)")
    ap.add_argument("instance", help="instance JSON file")
    ap.add_argument("--eps", type=float, default=1e-9,
                    help="allowed relative degradation of the energy (default 1e-9)")
    ap.add_argument("--time-limit", type=float, default=3600, help="seconds")
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("-o", "--output", help="write the result to a JSON file")
    ap.add_argument("--verbose", action="store_true", help="show the Gurobi log")
    args = ap.parse_args()

    inst = read_instance(args.instance)
    res = solve_ecmtc(inst, eps_rel=args.eps, time_limit=args.time_limit,
                      threads=args.threads, verbose=args.verbose)
    res = {"instance": inst.get("name", args.instance), "T": inst["T"],
           "D": None if math.isinf(inst["D"]) else inst["D"], **res}

    print(f"Instance: {res['instance']}")
    print(f"T = {res['T']}, D = {res['D']}, status = {res['status']}")
    if res["status"] == "optimal":
        print(f"ΣE = {res['total_energy']:.4f}   C_max = {res['makespan']:.4f}   "
              f"selected = {res['num_selected']}/{len(res['assignment'])}")
        for a in res["assignment"]:
            print(f"  resource {a['id']}: {a['tasks']} tasks (P = {a['time']:g}, E = {a['energy']:g})")
        print(f"Time: {res['time_s']:.3f} s, {res['nodes']:.0f} nodes, "
              f"{res['num_binaries']} binaries")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
        print(f"Result written to {args.output}")
    return 0 if res["status"] == "optimal" else 1


if __name__ == "__main__":
    sys.exit(main())