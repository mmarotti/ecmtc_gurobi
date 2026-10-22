import argparse
import json
import sys
import time
from pathlib import Path

from numpy import array, full, inf, ndarray, zeros


# ---------------------------------------------------------------------------
# Algoritmo original (fl-cs-sim/schedulers/ecmtc.py)
# ---------------------------------------------------------------------------

def ecmtc(num_resources: int,
          num_tasks: int,
          assignment_capacities: ndarray,
          time_costs: ndarray,
          energy_costs: ndarray,
          time_limit: float) -> tuple:
    # (I) Filtering: only assignments that respect the number of tasks to schedule (T) and the time limit (D).
    assignment_capacities_filtered = []
    for i in range(0, num_resources):
        assignment_capacities_i = []
        for j in assignment_capacities[i]:
            j_index = list(assignment_capacities[i]).index(j)
            if j <= num_tasks and time_costs[i][j_index] <= time_limit:
                assignment_capacities_i.append(j)
        assignment_capacities_filtered.append(assignment_capacities_i)
    # (II) Initialization: minimal costs and partial solutions matrices.
    partial_solutions = zeros(shape=(num_resources, num_tasks+1), dtype=int)
    minimal_energy_costs = full(shape=(num_resources, num_tasks+1), fill_value=inf, dtype=float)
    minimal_time_costs = full(shape=(num_resources, num_tasks+1), fill_value=inf, dtype=float)
    # (III) Solutions for the first resource (Z₁).
    for j in assignment_capacities_filtered[0]:
        j_index = list(assignment_capacities[0]).index(j)
        partial_solutions[0][j] = j
        minimal_energy_costs[0][j] = energy_costs[0][j_index]
        minimal_time_costs[0][j] = time_costs[0][j_index]
    # Solutions for other resources (Zᵢ).
    for i in range(1, num_resources):
        # Test all assignments to resource i.
        for j in assignment_capacities_filtered[i]:
            j_index = list(assignment_capacities[i]).index(j)
            for t in range(j, num_tasks+1):
                # (IV) Test new solution.
                energy_cost_new_solution = minimal_energy_costs[i-1][t-j] + energy_costs[i][j_index]
                time_cost_new_solution = max(float(minimal_time_costs[i-1][t-j]), float(time_costs[i][j_index]))
                if ((energy_cost_new_solution < minimal_energy_costs[i][t]) or
                        (energy_cost_new_solution == minimal_energy_costs[i][t] and
                         time_cost_new_solution < minimal_time_costs[i][t])):
                    # New best solution for Zᵢ(t).
                    minimal_energy_costs[i][t] = energy_cost_new_solution
                    minimal_time_costs[i][t] = time_cost_new_solution
                    partial_solutions[i][t] = j
    # Extract the optimal schedule (X*).
    t = num_tasks
    optimal_schedule = zeros(num_resources, dtype=int)
    for i in reversed(range(num_resources)):
        j = partial_solutions[i][t]  # Number of tasks to assign to resource i.
        optimal_schedule[i] = j
        t = t-j  # Solution index of resource i-1.
    # (V) Organize the final solution.
    minimal_energy_consumption = minimal_energy_costs[num_resources-1][num_tasks]
    minimal_makespan = minimal_time_costs[num_resources-1][num_tasks]
    # Return the optimal schedule (X*), the minimal energy consumption (ΣE), and the minimal makespan (C_max).
    return optimal_schedule, minimal_energy_consumption, minimal_makespan


# ---------------------------------------------------------------------------
# Instância: JSON -> parâmetros no formato da função original
# ---------------------------------------------------------------------------

def read_instance(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        inst = json.load(f)
    for r in inst["resources"]:
        if not (len(r["A"]) == len(r["P"]) == len(r["E"])):
            raise ValueError(f"resource {r['id']}: A, P and E must have the same length")
    return inst


def to_paper_format(inst: dict) -> tuple:
    resources = inst["resources"]
    num_resources = len(resources)
    assignment_capacities = array([r["A"] for r in resources])
    time_costs = array([r["P"] for r in resources], dtype=float)
    energy_costs = array([r["E"] for r in resources], dtype=float)
    time_limit = inf if inst["D"] is None else float(inst["D"])
    return num_resources, inst["T"], assignment_capacities, time_costs, energy_costs, time_limit


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="ECMTC by dynamic programming (original algorithm)")
    ap.add_argument("instance", help="instance JSON file")
    ap.add_argument("-o", "--output", help="output directory (saves result.json)")
    args = ap.parse_args()

    inst = read_instance(args.instance)
    params = to_paper_format(inst)

    # Tempo de execução do algoritmo
    t0 = time.perf_counter()
    x, energy, makespan = ecmtc(*params)
    solve_time = time.perf_counter() - t0

    resources = inst["resources"]
    res = {
        "instance": inst.get("name", args.instance), "T": inst["T"], "D": inst["D"],
        "method": "dynamic_programming",
        "status": "optimal" if energy < inf else "infeasible",
        "total_energy": float(energy),
        "makespan": float(makespan),
        "num_selected": int(sum(1 for j in x if j > 0)),
        "assignment": [{"id": r["id"], "tasks": int(x[i]), "selected": bool(x[i] > 0)}
                       for i, r in enumerate(resources)],
        "solve_time_s": solve_time,
    }

    print(f"Instance: {res['instance']}")
    print(f"T = {res['T']}, D = {res['D']}, status = {res['status']}")
    print(f"ΣE = {res['total_energy']:.4f}   C_max = {res['makespan']:.4f}   "
          f"selected = {res['num_selected']}/{len(resources)}")
    print(f"Solve: {res['solve_time_s']:.3f} s")

    if args.output:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "result.json", "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
        print(f"Result written to {out_dir}/result.json")
    return 0 if res["status"] == "optimal" else 1


if __name__ == "__main__":
    sys.exit(main())