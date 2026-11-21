"""
FutureFork API contracts (source of truth).

These Pydantic models define the JSON the backend returns for evaluated scenarios and
comparisons. `contracts/types.ts` and `frontend/src/contracts/types.ts` mirror them, and
`contracts/openapi.json` is generated from the running app (`python scripts/export_openapi.py`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

BranchType = Literal["baseline", "upfront", "emi", "phased", "trim"]
DecisionStatus = Literal["ok", "needs_clarification"]
ScenarioStatus = Literal["queued", "running", "done", "failed"]
CategoryType = Literal["fixed", "flexible"]


# ---------------------------------------------------------------------------
# Decisions & scenarios
# ---------------------------------------------------------------------------

class ChangeSpec(BaseModel):
    type: str = Field(..., description="baseline | upfront | emi | phased | trim")
    params: Dict[str, Any] = Field(default_factory=dict, description="PurchaseGoal fields")


class Scenario(BaseModel):
    id: str
    decision_id: str
    parent_id: Optional[str] = None
    name: str
    description: str
    change: ChangeSpec
    status: ScenarioStatus


class RunStatus(BaseModel):
    run_id: str
    decision_id: str
    overall_status: ScenarioStatus
    scenarios: Dict[str, ScenarioStatus]
    progress_percent: Optional[float] = None


# ---------------------------------------------------------------------------
# Evaluated scenario (FinancialScenarioResult)
# ---------------------------------------------------------------------------

class SolverInfo(BaseModel):
    status: str = Field(..., description="OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN")
    solver: Optional[str] = None
    runtime_s: float


class FinancialMetrics(BaseModel):
    cash_out_risk_pct: float = Field(..., description="% of Monte Carlo runs that go below ₹0")
    floor_breach_risk_pct: float = Field(..., description="% of runs that breach the emergency floor")
    survival_score_pct: float = Field(..., description="Composite solvency / floor-preservation score")
    p10_worst_balance: float = Field(..., description="10th-percentile lowest balance across runs (₹)")
    lowest_balance: float = Field(..., description="Deterministic lowest closing balance (₹)")
    lowest_balance_month: str
    months_below_floor: int
    runway_months: float
    ending_balance: float
    emergency_floor: float
    total_purchase_cost: float
    total_financing_interest: float
    total_trims_saved: float


class MetricDistribution(BaseModel):
    mean: float
    std: float
    p10: float
    p90: float


class FinancialSimulation(BaseModel):
    n_runs: int
    prob_cash_out: float = Field(..., description="0–1")
    monthly_balances: List[float] = Field(..., description="Deterministic closing balance per month")
    balance_p10: List[float] = Field(..., description="Monte Carlo P10 balance per month")
    balance_p90: List[float] = Field(..., description="Monte Carlo P90 balance per month")
    per_metric: Dict[str, MetricDistribution]


class CashFlowCategory(BaseModel):
    name: str
    type: CategoryType
    values: List[float] = Field(..., description="Outflow per month (₹), after any trims")


class CashFlowMatrix(BaseModel):
    months: List[str]
    inflows: List[float]
    purchase_cash_out: List[float]
    categories: List[CashFlowCategory]


class FinancialScenarioResult(BaseModel):
    scenario_id: str
    decision_id: Optional[str] = None
    branch_type: BranchType
    name: Optional[str] = None
    is_feasible: bool
    purchase_month: int = Field(..., description="Month index of the (first) purchase; -1 for baseline")
    solver: SolverInfo
    metrics: FinancialMetrics
    simulation: FinancialSimulation
    cash_flow: CashFlowMatrix
    category_trims: Dict[str, float] = Field(default_factory=dict, description="category -> cut fraction")
    explanation: Optional[str] = None


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

class Explanation(BaseModel):
    summary: str
    source: str = Field(..., description="llm | template | none")
    guard_passed: bool = Field(..., description="True if every number passed the Numeric Guard")
    violations: List[Dict[str, Any]] = Field(default_factory=list)


class ComparisonResponse(BaseModel):
    decision_id: str
    decision_spec: Dict[str, Any]
    scenarios: List[Scenario]
    results: Dict[str, FinancialScenarioResult]
    explanation: Explanation


class ApiError(BaseModel):
    error: str
    message: str
