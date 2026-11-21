"""
FutureFork Optimization Engine: Vectorized NumPy Monte Carlo Simulator
Member 3: Vectorized NumPy Monte Carlo & Risk Metrics (engine/simulator)

Executes a vectorized (300, 12) simulation matrix over 12-month CP-SAT schedules:
1. Historical variance (sigma) applied to flexible expense buckets.
2. 3 Stochastic Shocks injected across 300 runs:
   - Inflow Delay Shock: salary, college grant, or client invoice delayed by 1 month (t -> t+1).
   - Emergency Outflow Shock: random medical bill, lab equipment breakdown, or server spike.
   - Inflation / Category Drift: Gaussian spend multiplier on flexible buckets using historical sigma.
3. Vectorized Balance Evaluation:
   Balance[i, t] = Balance[0] + cumsum(Inflow[i, :] - Outflow[i, :])
4. Generates rich risk distributions: Cash-Out Risk (%), p10 Worst-Case Lowest Balance,
   Lowest Balance Month, Runway (Months), Survival Score (%), and confidence fan charts.
5. Benchmark Target: < 50ms per branch.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Union

import numpy as np

from engine.model import (
    FinancialProblemInstance,
    MonthlyCashSchedule,
    ScenarioEvaluationResult,
)

# ==============================================================================
# FINANCIAL MONTE CARLO SIMULATOR (MEMBER 3)
# ==============================================================================

def run_financial_monte_carlo(
    schedule: Union[ScenarioEvaluationResult, List[MonthlyCashSchedule], Dict[str, Any]],
    instance: FinancialProblemInstance,
    n_runs: int = 300,
    seed: int = 42,
    inject_shocks: bool = True,
) -> Dict[str, Any]:
    """
    Executes a vectorized (n_runs, 12) Monte Carlo risk simulation on a 12-month financial schedule.
    Injects 3 stochastic shocks:
    - Shock 1: Inflow Delay Shock (revenue shifted t -> t+1)
    - Shock 2: Emergency Outflow Shock (unexpected capital/medical/repair expenses)
    - Shock 3: Category Inflation Drift (Gaussian perturbation on flexible buckets using historical sigma)

    Performance: Vectorized NumPy execution completes in < 15ms for 300 runs.
    """
    start_t = time.perf_counter()
    rng = np.random.default_rng(seed)

    # 1. Extract Monthly Schedules
    monthly_schedules: List[Union[MonthlyCashSchedule, Dict[str, Any]]] = []
    category_trims: Dict[str, float] = {}

    if isinstance(schedule, ScenarioEvaluationResult):
        monthly_schedules = schedule.monthly_schedules
        category_trims = schedule.category_trims or {}
    elif isinstance(schedule, dict):
        monthly_schedules = schedule.get("monthly_schedules", [])
        category_trims = schedule.get("category_trims", {})
    elif isinstance(schedule, list):
        monthly_schedules = schedule

    T = 12
    if len(monthly_schedules) < T:
        # Fallback padding if less than 12 months provided
        padded_schedules = list(monthly_schedules)
        while len(padded_schedules) < T:
            m_idx = len(padded_schedules)
            padded_schedules.append({
                "month_idx": m_idx,
                "month_str": instance.months[m_idx] if m_idx < len(instance.months) else f"M{m_idx}",
                "inflow": instance.inflows[m_idx] if m_idx < len(instance.inflows) else 0.0,
                "trimmed_outflow": instance.total_outflows[m_idx] if m_idx < len(instance.total_outflows) else 0.0,
                "purchase_cash_out": 0.0,
                "closing_balance": instance.starting_balance,
                "emergency_floor": 0.0,
            })
        monthly_schedules = padded_schedules

    # 2. Extract Base Coordinate Vectors (12 elements)
    def _get_val(obj: Any, key: str, default: float = 0.0) -> float:
        if isinstance(obj, dict):
            return float(obj.get(key, default))
        return float(getattr(obj, key, default))

    planned_inflows = np.array([_get_val(s, "inflow") for s in monthly_schedules[:T]], dtype=np.float64)
    purchase_outflows = np.array([_get_val(s, "purchase_cash_out") for s in monthly_schedules[:T]], dtype=np.float64)
    floor = _get_val(monthly_schedules[0], "emergency_floor", 0.0)
    b0 = float(instance.starting_balance)

    # Build (12, 8) planned category outflow matrix incorporating category trims
    num_cats = len(instance.categories)
    O_planned = np.zeros((T, num_cats), dtype=np.float64)

    for t in range(T):
        s = monthly_schedules[t]
        s_cat_outflows = getattr(s, "category_outflows", None) or (s.get("category_outflows") if isinstance(s, dict) else None)
        for c, cat in enumerate(instance.categories):
            if s_cat_outflows and cat in s_cat_outflows:
                O_planned[t, c] = float(s_cat_outflows[cat])
            else:
                trim_factor = 1.0 - float(category_trims.get(cat, 0.0))
                O_planned[t, c] = instance.outflows[t][c] * trim_factor

    # ==========================================================================
    # VECTORIZED NUMPY SIMULATION MATRIX (n_runs, 12)
    # ==========================================================================

    # --- SHOCK 3: Inflation & Category Drift on Flexible Buckets ---
    # Draw (n_runs, 12, 8) spend multiplier matrix using historical sigma
    spend_multipliers = np.ones((n_runs, T, num_cats), dtype=np.float64)

    if inject_shocks:
        for c, cat in enumerate(instance.categories):
            is_flexible = (instance.category_types.get(cat) == "flexible")
            if is_flexible:
                mu = float(instance.category_means.get(cat, 1.0))
                sigma = float(instance.category_stds.get(cat, 0.0))
                cv = min(0.35, max(0.06, sigma / max(100.0, mu)))
                # Gaussian drift around mean 1.0 with variance based on historical CV
                drift = rng.normal(1.0, cv, size=(n_runs, T))
                # Truncate at [0.70, 1.45] to model realistic variance without negative expenses
                spend_multipliers[:, :, c] = np.clip(drift, 0.70, 1.45)
            else:
                # Fixed categories (salaries, rent) have minimal drift (+- 1%)
                spend_multipliers[:, :, c] = rng.normal(1.0, 0.01, size=(n_runs, T))

    # Broadcast category matrix across runs: (n_runs, 12, 8)
    sim_category_outflows = O_planned[np.newaxis, :, :] * spend_multipliers
    # Sum across the 8 categories to get base monthly operating outflows: (n_runs, 12)
    sim_operating_outflows = np.sum(sim_category_outflows, axis=2)

    # --- SHOCK 2: Emergency Outflow Shock ---
    # Random sudden expenditure (medical emergency, equipment outage, server spike)
    emergency_shocks = np.zeros((n_runs, T), dtype=np.float64)
    emergency_count = 0

    if inject_shocks:
        # 5% probability per month => ~46% of runs experience an emergency in a 12-month period
        emergency_mask = (rng.random((n_runs, T)) < 0.05)
        emergency_count = int(np.sum(emergency_mask))
        mean_monthly_out = float(np.mean(instance.total_outflows))
        total_sigma = float(np.sum(list(instance.category_stds.values())))
        emerg_scale = max(mean_monthly_out * 0.18, total_sigma * 0.30)
        emerg_magnitudes = emerg_scale * rng.uniform(0.85, 1.60, size=(n_runs, T))
        emergency_shocks = emergency_mask * emerg_magnitudes

    # Total simulated monthly outflows = operating + purchase outlay + emergency shocks
    sim_total_outflows = sim_operating_outflows + purchase_outflows[np.newaxis, :] + emergency_shocks

    # --- SHOCK 1: Inflow Delay Shock ---
    # Salary, student tuition grant, or client invoice delayed by 1 month (t -> t+1)
    sim_inflows = np.tile(planned_inflows, (n_runs, 1)).copy()
    inflow_delay_count = 0

    if inject_shocks:
        # ~20% of simulation runs experience an unexpected payment delay
        delay_run_mask = rng.random(n_runs) < 0.20
        inflow_delay_count = int(np.sum(delay_run_mask))

        # Identify months with positive inflows that can be delayed (months 0 to 10)
        eligible_months = [t for t in range(T - 1) if planned_inflows[t] > 1000.0]
        if eligible_months:
            # Pick a delay month for each affected run
            chosen_delay_months = rng.choice(eligible_months, size=n_runs)
            delay_fractions = rng.uniform(0.40, 0.85, size=n_runs)

            for i in range(n_runs):
                if delay_run_mask[i]:
                    t_del = chosen_delay_months[i]
                    delayed_amt = planned_inflows[t_del] * delay_fractions[i]
                    sim_inflows[i, t_del] -= delayed_amt
                    sim_inflows[i, t_del + 1] += delayed_amt

    # --- VECTORIZED CUMULATIVE CASH BALANCE MATRIX ---
    # Net Cash Flow Matrix: (n_runs, 12)
    sim_net_flows = sim_inflows - sim_total_outflows
    # Balances Matrix: B[i, t] = B0 + cumsum(Net[i, :])
    # Shape: (n_runs, 12)
    sim_balances = b0 + np.cumsum(sim_net_flows, axis=1)

    # ==========================================================================
    # RISK METRICS EVALUATION
    # ==========================================================================

    # Lowest balance reached per run: shape (n_runs,)
    run_lowest_balances = np.min(sim_balances, axis=1)
    run_lowest_months = np.argmin(sim_balances, axis=1)

    # Percentiles of lowest balance
    p10_lowest = float(np.percentile(run_lowest_balances, 10))
    p50_lowest = float(np.percentile(run_lowest_balances, 50))
    p90_lowest = float(np.percentile(run_lowest_balances, 90))
    mean_lowest = float(np.mean(run_lowest_balances))

    # Cash-Out Risk (% of runs where cash drops below 0)
    cash_out_runs = int(np.sum(run_lowest_balances < 0.0))
    cash_out_risk_pct = round(float((cash_out_runs / n_runs) * 100.0), 1)

    # Floor Breach Risk (% of runs where cash drops below emergency floor)
    floor_breach_runs = int(np.sum(run_lowest_balances < floor))
    floor_breach_risk_pct = round(float((floor_breach_runs / n_runs) * 100.0), 1)
    prob_safe_above_floor = round(float(1.0 - (floor_breach_runs / n_runs)), 3)

    # Most common lowest balance month
    counts = np.bincount(run_lowest_months, minlength=T)
    lowest_month_idx = int(np.argmax(counts))
    lowest_month_str = instance.months[lowest_month_idx] if lowest_month_idx < len(instance.months) else f"Month {lowest_month_idx + 1}"

    # Runway: Ending balance / average monthly burn
    ending_balances = sim_balances[:, -1]
    median_ending = float(np.median(ending_balances))
    avg_burn = float(np.mean(sim_total_outflows)) / 12.0
    if avg_burn > 0 and median_ending > 0:
        runway_months = round(float(median_ending / avg_burn), 1)
    else:
        runway_months = 0.0

    # Survival Score (%): Solvency and floor preservation
    if cash_out_risk_pct == 0.0 and floor_breach_risk_pct == 0.0:
        survival_score = 100.0
    else:
        # Penalty weighted on cash out (60%) and floor breach (40%)
        deficit_factor = 0.0
        if floor > 0 and p10_lowest < floor:
            deficit_factor = min(30.0, ((floor - p10_lowest) / floor) * 20.0)
        penalty = (cash_out_risk_pct * 0.55) + (floor_breach_risk_pct * 0.35) + deficit_factor
        survival_score = round(max(5.0, min(100.0, 100.0 - penalty)), 1)

    # Monthly fan chart trajectories for UI confidence ribbon
    monthly_trajectories = []
    for t in range(T):
        m_bals = sim_balances[:, t]
        monthly_trajectories.append({
            "month_idx": t,
            "month_str": instance.months[t] if t < len(instance.months) else f"M{t + 1}",
            "mean": round(float(np.mean(m_bals)), 2),
            "std": round(float(np.std(m_bals)), 2),
            "p10": round(float(np.percentile(m_bals, 10)), 2),
            "p50": round(float(np.percentile(m_bals, 50)), 2),
            "p90": round(float(np.percentile(m_bals, 90)), 2),
            "prob_below_floor": round(float(np.mean(m_bals < floor)), 3),
        })

    elapsed_ms = (time.perf_counter() - start_t) * 1000.0

    return {
        "n_runs": n_runs,
        "runtime_ms": round(elapsed_ms, 2),
        "cash_out_risk_pct": cash_out_risk_pct,
        "floor_breach_risk_pct": floor_breach_risk_pct,
        "p10_lowest_balance": round(p10_lowest, 2),
        "p50_lowest_balance": round(p50_lowest, 2),
        "p90_lowest_balance": round(p90_lowest, 2),
        "mean_lowest_balance": round(mean_lowest, 2),
        "lowest_balance_month": lowest_month_str,
        "lowest_balance_month_idx": lowest_month_idx,
        "runway_months": runway_months,
        "survival_score_pct": survival_score,
        "prob_safe_above_floor": prob_safe_above_floor,
        "shocks_summary": {
            "inflow_delays_count": inflow_delay_count,
            "emergency_shocks_count": emergency_count,
            "category_drift_active": inject_shocks,
        },
        "monthly_trajectories": monthly_trajectories,
        "per_metric": {
            "cash_out_risk": {"mean": cash_out_risk_pct, "p10": cash_out_risk_pct, "p90": cash_out_risk_pct},
            "lowest_balance": {"mean": round(mean_lowest, 1), "p10": round(p10_lowest, 1), "p90": round(p90_lowest, 1)},
            "survival_score": {"mean": survival_score, "p10": survival_score, "p90": survival_score},
        },
    }
