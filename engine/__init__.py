"""
FutureFork Optimization and Simulation Engine.

Pure Python: OR-Tools CP-SAT cash-flow solver, fork transformers, deterministic
risk metrics, and a vectorized NumPy Monte Carlo simulator. The engine never
touches HTTP, databases, or LLMs.
"""

from engine.changes import (
    BRANCH_TYPES,
    apply_discretionary_trim,
    apply_emi_split,
    apply_financial_change,
    apply_phased_delay,
    apply_upfront,
    normalize_branch_type,
)
from engine.metrics import compute_financial_metrics
from engine.model import (
    CategoryTrim,
    ColumnMapping,
    FinancialProblemInstance,
    MonthlyCashSchedule,
    PurchaseGoal,
    ScenarioEvaluationResult,
)
from engine.simulator import run_financial_monte_carlo
from engine.solver import (
    attach_simulation,
    evaluate_financial_baseline,
    evaluate_financial_branch,
    solve_all_financial_scenarios,
    solve_emi_branch,
    solve_financial_scenario,
    solve_phased_branch,
    solve_trim_branch,
    solve_upfront_branch,
)

__all__ = [
    # Models
    "ColumnMapping",
    "FinancialProblemInstance",
    "PurchaseGoal",
    "MonthlyCashSchedule",
    "CategoryTrim",
    "ScenarioEvaluationResult",
    # Fork transformers
    "BRANCH_TYPES",
    "normalize_branch_type",
    "apply_upfront",
    "apply_emi_split",
    "apply_phased_delay",
    "apply_discretionary_trim",
    "apply_financial_change",
    # Solvers
    "evaluate_financial_branch",
    "evaluate_financial_baseline",
    "solve_financial_scenario",
    "solve_all_financial_scenarios",
    "solve_upfront_branch",
    "solve_emi_branch",
    "solve_phased_branch",
    "solve_trim_branch",
    # Simulation & metrics
    "attach_simulation",
    "compute_financial_metrics",
    "run_financial_monte_carlo",
]
