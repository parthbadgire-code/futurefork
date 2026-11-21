"""
FutureFork Optimization Engine: Metric Calculator
Deterministic cash-flow risk metrics for a 12-month financial schedule.
Every number shown in the UI comes from this module, the CP-SAT solver, or the simulator.
"""

from typing import Any, Dict, List, Optional, Union

from engine.model import MonthlyCashSchedule

# ==============================================================================
# FINANCIAL METRICS EVALUATOR (MEMBER 3)
# ==============================================================================

def compute_financial_metrics(
    schedules: List[Union[MonthlyCashSchedule, Dict[str, Any]]],
    starting_balance: float,
    emergency_floor: float,
    total_purchase: float = 0.0,
    total_interest: float = 0.0,
    total_saved: float = 0.0,
    simulation_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Computes exact deterministic and stochastic risk metrics for a 12-month financial schedule.
    Member 3 Metrics:
    - Cash-Out Risk (%): Probability of dropping below 0 INR
    - p10 Worst-Case Lowest Balance (₹): 10th percentile lowest balance across stochastic runs
    - Lowest Balance Month: Period where cash balance reaches annual minimum
    - Runway (Months): Months of operation funded by ending balance at average burn
    - Survival Score (%): Composite score reflecting solvency and emergency floor preservation
    """
    # Normalize schedules to MonthlyCashSchedule objects or dicts
    norm_schedules: List[Dict[str, Any]] = []
    for s in schedules:
        if isinstance(s, MonthlyCashSchedule):
            norm_schedules.append(s.to_dict())
        elif isinstance(s, dict):
            norm_schedules.append(s)

    balances = [float(s.get("closing_balance", 0.0)) for s in norm_schedules]
    inflows = [float(s.get("inflow", 0.0)) for s in norm_schedules]
    total_outflows = [
        float(s.get("trimmed_outflow", s.get("base_outflow", 0.0))) + float(s.get("purchase_cash_out", 0.0))
        for s in norm_schedules
    ]

    min_bal = min(balances) if balances else 0.0
    min_idx = balances.index(min_bal) if balances else 0
    min_month = norm_schedules[min_idx].get("month_str", f"Month {min_idx + 1}") if norm_schedules else "N/A"
    months_below = sum(1 for b in balances if b < emergency_floor)
    ending_balance = balances[-1] if balances else 0.0

    sum_inflows = sum(inflows)
    sum_outflows = sum(total_outflows)
    avg_monthly_burn = (sum_outflows / 12.0) if sum_outflows > 0 else 1.0

    # Runway: months of runway left at ending balance
    if avg_monthly_burn > 0 and ending_balance > 0:
        runway_months = round(ending_balance / avg_monthly_burn, 1)
    else:
        runway_months = 0.0

    # Deterministic Cash-Out Risk %
    if min_bal >= 0:
        det_cash_out_risk = 0.0
    else:
        det_cash_out_risk = round(min(100.0, (abs(min_bal) / max(1.0, sum_inflows)) * 100.0), 1)

    # Deterministic Survival Score: 100% if never below emergency floor
    if months_below == 0:
        det_survival_score = 100.0
    else:
        worst_deficit = max(0.0, emergency_floor - min_bal)
        penalty = min(80.0, (worst_deficit / max(1.0, emergency_floor)) * 50.0 + (months_below * 5.0))
        det_survival_score = round(max(5.0, 100.0 - penalty), 1)

    # Blend with simulation results if provided
    sim = simulation_results or {}
    cash_out_risk = sim.get("cash_out_risk_pct", det_cash_out_risk)
    p10_lowest = sim.get("p10_lowest_balance", round(min_bal, 2))
    p50_lowest = sim.get("p50_lowest_balance", round(min_bal, 2))
    p90_lowest = sim.get("p90_lowest_balance", round(min_bal, 2))
    survival_score = sim.get("survival_score_pct", det_survival_score)

    return {
        "starting_balance": round(starting_balance, 2),
        "ending_balance": round(ending_balance, 2),
        "lowest_balance": round(min_bal, 2),
        "lowest_balance_month": min_month,
        "lowest_balance_month_idx": min_idx,
        "emergency_floor": round(emergency_floor, 2),
        "months_below_floor": months_below,
        "is_safe_above_floor": (months_below == 0),
        "total_inflow": round(sum_inflows, 2),
        "total_outflow": round(sum_outflows, 2),
        "net_cash_flow": round(sum_inflows - sum_outflows, 2),
        "total_purchase_cost": round(total_purchase, 2),
        "total_financing_interest": round(total_interest, 2),
        "total_trims_saved": round(total_saved, 2),
        "runway_months": runway_months,
        "cash_out_risk_pct": round(float(cash_out_risk), 1),
        "survival_score_pct": round(float(survival_score), 1),
        "p10_lowest_balance": round(float(p10_lowest), 2),
        "p50_lowest_balance": round(float(p50_lowest), 2),
        "p90_lowest_balance": round(float(p90_lowest), 2),
        "worst_case_lowest_balance": round(float(p10_lowest), 2),
    }
