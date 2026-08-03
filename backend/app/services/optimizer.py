"""PuLP MILP offer optimiser (single borrower and portfolio)."""
from __future__ import annotations

from typing import Any

import pulp


class OptimizerError(Exception):
    """Raised when the MILP solver cannot find a feasible/optimal solution."""


def _status_name(status: int) -> str:
    return pulp.LpStatus.get(status, str(status))


def optimize_single_borrower(
    offers: list[dict[str, Any]],
    *,
    rr_min: float = 0.20,
    rr_max: float = 0.80,
    max_rr: float | None = None,
    min_p_fulfill: float | None = None,
    fixed_installments: int | None = None,
) -> dict[str, Any]:
    """Pick exactly one offer maximizing EV subject to constraints."""
    eligible = []
    for o in offers:
        rr = float(o["recovery_rate"])
        pf = float(o["p_fulfillment"])
        inst = int(o["installments"])
        if rr < rr_min or rr > rr_max:
            continue
        if max_rr is not None and rr > max_rr:
            continue
        if min_p_fulfill is not None and pf < min_p_fulfill:
            continue
        if fixed_installments is not None and inst != fixed_installments:
            continue
        eligible.append(o)

    if not eligible:
        raise OptimizerError("No feasible offer found under the given constraints")

    prob = pulp.LpProblem("single_borrower_offer", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(len(eligible))}
    prob += pulp.lpSum(float(eligible[i]["expected_value"]) * x[i] for i in range(len(eligible)))
    prob += pulp.lpSum(x[i] for i in range(len(eligible))) == 1

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    status_name = _status_name(status)
    if status != pulp.LpStatusOptimal:
        raise OptimizerError(f"MILP solver failed: {status_name}")

    chosen_idx = next(i for i in range(len(eligible)) if pulp.value(x[i]) and pulp.value(x[i]) > 0.5)
    chosen = dict(eligible[chosen_idx])
    objective = float(pulp.value(prob.objective) or 0)
    chosen.update(
        {
            "solver_status": status_name,
            "mip_gap": 0.0,
            "objective": objective,
            "optimizer": "pulp_cbc",
            "constraints_applied": {
                "rr_min": rr_min,
                "rr_max": rr_max,
                "max_rr": max_rr,
                "min_p_fulfill": min_p_fulfill,
                "fixed_installments": fixed_installments,
            },
        }
    )
    return chosen


def optimize_portfolio(
    offers_by_customer: dict[int, list[dict[str, Any]]],
    *,
    rr_min: float = 0.20,
    rr_max: float = 0.80,
    max_rr: float | None = None,
    min_p_fulfill: float | None = None,
    max_avg_rr: float | None = None,
    max_installment_share: float | None = 0.60,
    high_installment_threshold: int = 3,
) -> dict[str, Any]:
    """Assign exactly one offer per borrower maximizing total portfolio EV."""
    # Filter eligible offers per borrower
    filtered: dict[int, list[dict[str, Any]]] = {}
    for cust, offers in offers_by_customer.items():
        elig = []
        for o in offers:
            rr = float(o["recovery_rate"])
            pf = float(o["p_fulfillment"])
            if rr < rr_min or rr > rr_max:
                continue
            if max_rr is not None and rr > max_rr:
                continue
            if min_p_fulfill is not None and pf < min_p_fulfill:
                continue
            elig.append(o)
        if elig:
            filtered[cust] = elig

    if not filtered:
        raise OptimizerError("No feasible portfolio assignment under the given constraints")

    n = len(filtered)
    prob = pulp.LpProblem("portfolio_offer_assignment", pulp.LpMaximize)
    x: dict[tuple[int, int], pulp.LpVariable] = {}
    for cust, offers in filtered.items():
        for i in range(len(offers)):
            x[(cust, i)] = pulp.LpVariable(f"x_{cust}_{i}", cat="Binary")
        # Exactly one offer per borrower
        prob += pulp.lpSum(x[(cust, i)] for i in range(len(offers))) == 1, f"one_{cust}"

    prob += pulp.lpSum(
        float(offers[i]["expected_value"]) * x[(cust, i)]
        for cust, offers in filtered.items()
        for i in range(len(offers))
    )

    if max_avg_rr is not None and n > 0:
        prob += (
            pulp.lpSum(
                float(offers[i]["recovery_rate"]) * x[(cust, i)]
                for cust, offers in filtered.items()
                for i in range(len(offers))
            )
            <= max_avg_rr * n,
            "max_avg_rr",
        )

    if max_installment_share is not None and n > 0:
        high_inst = pulp.lpSum(
            x[(cust, i)]
            for cust, offers in filtered.items()
            for i in range(len(offers))
            if int(offers[i]["installments"]) >= high_installment_threshold
        )
        prob += high_inst <= max_installment_share * n, "max_installment_share"

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    status_name = _status_name(status)
    if status != pulp.LpStatusOptimal:
        raise OptimizerError(f"Portfolio MILP solver failed: {status_name}")

    assignments: list[dict[str, Any]] = []
    for cust, offers in filtered.items():
        for i in range(len(offers)):
            if pulp.value(x[(cust, i)]) and pulp.value(x[(cust, i)]) > 0.5:
                row = dict(offers[i])
                row["customer_code"] = cust
                assignments.append(row)
                break

    portfolio_ev = float(pulp.value(prob.objective) or 0)
    avg_rr = sum(float(a["recovery_rate"]) for a in assignments) / len(assignments) if assignments else 0
    high_share = (
        sum(1 for a in assignments if int(a["installments"]) >= high_installment_threshold) / len(assignments)
        if assignments
        else 0
    )

    return {
        "assignments": assignments,
        "borrowers_assigned": len(assignments),
        "portfolio_ev": round(portfolio_ev, 2),
        "avg_rr": round(avg_rr, 4),
        "high_installment_share": round(high_share, 4),
        "solver_status": status_name,
        "mip_gap": 0.0,
        "optimizer": "pulp_cbc",
        "constraints_applied": {
            "rr_min": rr_min,
            "rr_max": rr_max,
            "max_rr": max_rr,
            "min_p_fulfill": min_p_fulfill,
            "max_avg_rr": max_avg_rr,
            "max_installment_share": max_installment_share,
        },
    }
