"""
FutureFork Integration Bridge
Connects the FastAPI backend to the engine (CP-SAT + Monte Carlo) and the AI layer.

Golden Rule: this module never fabricates numbers. If the engine cannot evaluate a
branch, the exception propagates and the runner marks that scenario as failed.
"""

from __future__ import annotations

import dataclasses
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from ai.agents.explainer import explain_branches
from ai.agents.parser import DecisionParseError, parse_financial_decision
from ai.agents.scenario import build_forks
from engine.changes import BRANCH_TYPES
from engine.model import FinancialProblemInstance
from engine.solver import evaluate_financial_branch

DEFAULT_DATASET_TYPE = "personal"


# ---------------------------------------------------------------------------
# Dataset helpers
# ---------------------------------------------------------------------------

def load_instance(dataset_payload: Dict[str, Any]) -> FinancialProblemInstance:
    """Rebuilds the compiled 12-month FinancialProblemInstance stored with a dataset."""
    raw = (dataset_payload or {}).get("instance")
    if not raw:
        raise ValueError("Dataset has no compiled financial instance; re-commit the CSV.")
    return FinancialProblemInstance.from_dict(raw)


def dataset_type_of(dataset_payload: Dict[str, Any]) -> str:
    summary = (dataset_payload or {}).get("summary", {})
    return summary.get("dataset_type") or DEFAULT_DATASET_TYPE


# ---------------------------------------------------------------------------
# 1. Decision parsing
# ---------------------------------------------------------------------------

def call_parse_decision(
    text: str,
    dataset_id: str,
    instance: Optional[FinancialProblemInstance],
    dataset_type: str = DEFAULT_DATASET_TYPE,
) -> Dict[str, Any]:
    """Parses a plain-English decision into a DecisionSpec dict."""
    decision_id = f"dec_{uuid.uuid4().hex[:12]}"
    base = {
        "id": decision_id,
        "text": text,
        "dataset_id": dataset_id,
        "dataset_type": dataset_type,
        "objectives": [
            {"metric": "cash_out_risk_pct", "direction": "minimize"},
            {"metric": "survival_score_pct", "direction": "maximize"},
        ],
    }

    try:
        parsed = parse_financial_decision(text, baseline=instance, dataset_type=dataset_type)
    except DecisionParseError as exc:
        return {
            **base,
            "constraints": [],
            "change": {"type": "upfront", "params": {}},
            "financial": None,
            "status": "needs_clarification",
            "message": str(exc),
        }

    fin = dataclasses.asdict(parsed)
    return {
        **base,
        "constraints": [
            {"kind": "emergency_floor", "params": {"floor": fin["emergency_floor"]}},
        ],
        "change": {
            "type": fin["financing_preference"],
            "params": {
                "item_name": fin["item_label"],
                "total_cost": fin["total_cost"],
                "emergency_floor": fin["emergency_floor"],
                "target_month": fin["target_month"],
                "emi_months": fin["emi_months"],
                "quantity": fin["quantity"],
            },
        },
        "financial": fin,
        "status": "ok",
        "message": None,
    }


# ---------------------------------------------------------------------------
# 2. Scenario fan-out (baseline + 4 forks)
# ---------------------------------------------------------------------------

def scenario_id_for(decision_id: str, branch_type: str) -> str:
    """Scenario ids are unique per decision so decisions never overwrite each other."""
    return f"{decision_id}_{branch_type}"


def call_generate_scenarios(
    decision: Dict[str, Any],
    instance: FinancialProblemInstance,
) -> List[Dict[str, Any]]:
    """Builds the baseline node plus the 4 policy forks for a decision."""
    d_id = decision["id"]
    fork_set = build_forks(
        decision.get("text", ""),
        instance,
        decision.get("dataset_type", DEFAULT_DATASET_TYPE),
    )

    floor = float(getattr(fork_set.baseline_goal, "emergency_floor", 0.0) or 0.0)
    scenarios: List[Dict[str, Any]] = [{
        "id": scenario_id_for(d_id, "baseline"),
        "decision_id": d_id,
        "parent_id": None,
        "name": "Baseline (Node 0)",
        "description": "Your historical 12-month cash flow with no purchase and no spending changes.",
        "change": {"type": "baseline", "params": {"emergency_floor": floor}},
        "status": "queued",
    }]

    for fork in fork_set.forks:
        goal = fork.goal.to_dict() if hasattr(fork.goal, "to_dict") else dict(fork.goal or {})
        ok = fork.status == "ready"
        description = fork.policy_description
        if not ok and fork.infeasibility_reason:
            description = f"{description} Not evaluated: {fork.infeasibility_reason}"
        scenarios.append({
            "id": scenario_id_for(d_id, fork.fork_id),
            "decision_id": d_id,
            "parent_id": scenario_id_for(d_id, "baseline"),
            "name": fork.title,
            "description": description,
            "change": {"type": fork.fork_id, "params": goal},
            "status": "queued" if ok else "failed",
        })
    return scenarios


# ---------------------------------------------------------------------------
# 3. Evaluation (CP-SAT + Monte Carlo)
# ---------------------------------------------------------------------------

def call_evaluate_scenario(
    instance: FinancialProblemInstance,
    scenario: Dict[str, Any],
    n_sims: int = 300,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Evaluates one scenario with the real engine and returns the raw engine result dict,
    tagged with the scenario id, branch type and the dataset's category types.
    Raises on failure; never returns placeholder numbers.
    """
    change = scenario.get("change") or {}
    branch_type = str(change.get("type") or "")
    result = evaluate_financial_branch(
        instance,
        branch_type,
        change.get("params") or {},
        n_sims=n_sims,
        seed=seed,
    )
    raw = result.to_dict()
    raw["scenario_id"] = scenario["id"]
    raw["decision_id"] = scenario.get("decision_id")
    raw["branch_type"] = result.branch_type
    raw["category_types"] = dict(instance.category_types)
    return raw


# ---------------------------------------------------------------------------
# 4. Explanation (Numeric Guard enforced inside explain_branches)
# ---------------------------------------------------------------------------

def call_explain(decision: Dict[str, Any], raw_results: Dict[str, Any]) -> Dict[str, Any]:
    """Explains the evaluated branches. raw_results: scenario_id -> raw engine result."""
    if not raw_results:
        return {
            "summary": "No scenarios have been evaluated yet.",
            "source": "none",
            "guard_passed": True,
            "violations": [],
        }

    by_branch = {r.get("branch_type", sid): r for sid, r in raw_results.items()}
    fin = decision.get("financial") or {}
    parsed = SimpleNamespace(**fin) if fin else None

    result = explain_branches(parsed, by_branch)
    report = result.guard_report
    return {
        "summary": result.text,
        "source": result.source,
        "guard_passed": bool(report.passed),
        "violations": [dataclasses.asdict(v) for v in report.violations],
    }


# ---------------------------------------------------------------------------
# 5. API view: raw engine result -> FinancialScenarioResult contract
# ---------------------------------------------------------------------------

def to_api_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Projects a stored engine result into the FinancialScenarioResult API contract."""
    metrics = raw.get("metrics") or {}
    sim = raw.get("simulation_results") or {}
    solver_meta = raw.get("solver_metadata") or {}
    schedules = raw.get("monthly_schedules") or []
    trajectories = sim.get("monthly_trajectories") or []
    category_types = raw.get("category_types") or {}

    months = [s.get("month_str", f"M{i + 1}") for i, s in enumerate(schedules)]
    category_names: List[str] = list(category_types.keys())
    for s in schedules:
        for name in (s.get("category_outflows") or {}):
            if name not in category_names:
                category_names.append(name)

    categories = [
        {
            "name": name,
            "type": category_types.get(name, "fixed"),
            "values": [float((s.get("category_outflows") or {}).get(name, 0.0)) for s in schedules],
        }
        for name in category_names
    ]

    def _single(value: Any) -> Dict[str, float]:
        v = float(value or 0.0)
        return {"mean": v, "std": 0.0, "p10": v, "p90": v}

    lowest_dist = (sim.get("per_metric") or {}).get("lowest_balance") or {}
    p10_worst = metrics.get("p10_lowest_balance", metrics.get("lowest_balance", 0.0))

    return {
        "scenario_id": raw.get("scenario_id"),
        "decision_id": raw.get("decision_id"),
        "branch_type": raw.get("branch_type"),
        "name": raw.get("scenario_name"),
        "is_feasible": bool(raw.get("is_feasible", False)),
        "purchase_month": raw.get("purchase_month", -1),
        "solver": {
            "status": solver_meta.get("status", "UNKNOWN"),
            "solver": solver_meta.get("solver"),
            "runtime_s": float(solver_meta.get("runtime_s", 0.0)),
        },
        "metrics": {
            "cash_out_risk_pct": float(metrics.get("cash_out_risk_pct", 0.0)),
            "floor_breach_risk_pct": float(metrics.get("floor_breach_risk_pct", 0.0)),
            "survival_score_pct": float(metrics.get("survival_score_pct", 0.0)),
            "p10_worst_balance": float(p10_worst),
            "lowest_balance": float(metrics.get("lowest_balance", 0.0)),
            "lowest_balance_month": str(metrics.get("lowest_balance_month", "")),
            "months_below_floor": int(metrics.get("months_below_floor", 0)),
            "runway_months": float(metrics.get("runway_months", 0.0)),
            "ending_balance": float(metrics.get("ending_balance", 0.0)),
            "emergency_floor": float(metrics.get("emergency_floor", 0.0)),
            "total_purchase_cost": float(metrics.get("total_purchase_cost", 0.0)),
            "total_financing_interest": float(metrics.get("total_financing_interest", 0.0)),
            "total_trims_saved": float(metrics.get("total_trims_saved", 0.0)),
        },
        "simulation": {
            "n_runs": int(sim.get("n_runs", 0)),
            "prob_cash_out": float(sim.get("cash_out_risk_pct", 0.0)) / 100.0,
            "monthly_balances": [float(s.get("closing_balance", 0.0)) for s in schedules],
            "balance_p10": [float(t.get("p10", 0.0)) for t in trajectories],
            "balance_p90": [float(t.get("p90", 0.0)) for t in trajectories],
            "per_metric": {
                "cash_out_risk_pct": _single(metrics.get("cash_out_risk_pct")),
                "survival_score_pct": _single(metrics.get("survival_score_pct")),
                "runway_months": _single(metrics.get("runway_months")),
                "p10_worst_balance": {
                    "mean": float(lowest_dist.get("mean", p10_worst)),
                    "std": 0.0,
                    "p10": float(lowest_dist.get("p10", p10_worst)),
                    "p90": float(lowest_dist.get("p90", p10_worst)),
                },
            },
        },
        "cash_flow": {
            "months": months,
            "inflows": [float(s.get("inflow", 0.0)) for s in schedules],
            "purchase_cash_out": [float(s.get("purchase_cash_out", 0.0)) for s in schedules],
            "categories": categories,
        },
        "category_trims": raw.get("category_trims") or {},
        "explanation": None,
    }


__all__ = [
    "BRANCH_TYPES",
    "load_instance",
    "dataset_type_of",
    "call_parse_decision",
    "call_generate_scenarios",
    "call_evaluate_scenario",
    "call_explain",
    "scenario_id_for",
    "to_api_result",
]
