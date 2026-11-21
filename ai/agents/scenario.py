"""
FutureFork Scenario Fan-out Agent (Member 4)

Builds 4 competing policy fork branches from a plain-English financial decision.
Uses LangGraph StateGraph internally when available; falls back to plain Python
function calls with identical external interface.

Public API:
  build_forks(prompt, baseline, dataset_type="personal") -> ForkSet

Backward compat:
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("futurefork.ai.agents.scenario")

# ===========================================================================
# Public types
# ===========================================================================


@dataclass
class ForkSpec:
    """
    One policy fork branch.

    Attributes:
        fork_id:               "upfront" | "emi" | "phased" | "trim"
        title:                 Display title for this fork.
        policy_description:    One-sentence policy explanation.
        goal:                  PurchaseGoal ready to pass to solver.
        status:                "ready" | "infeasible" | "error"
        infeasibility_reason:  Set if status != "ready".
    """

    fork_id: str
    title: str
    policy_description: str
    goal: Any  # PurchaseGoal — typed as Any to avoid circular import issues
    status: str = "ready"
    infeasibility_reason: Optional[str] = None


@dataclass
class ForkSet:
    """
    Result of build_forks().

    Attributes:
        decision:      ParsedDecision (source of truth for the prompt).
        baseline_goal: The base PurchaseGoal built from the parsed decision.
        forks:         Exactly 4 ForkSpec objects in order: upfront, emi, phased, trim.
    """

    decision: Any  # ParsedDecision
    baseline_goal: Any  # PurchaseGoal
    forks: List[ForkSpec]  # always exactly 4


# ===========================================================================
# Internal helpers
# ===========================================================================

_FORK_METADATA: Dict[str, Tuple[str, str]] = {
    "upfront": (
        "Upfront Purchase",
        "Pay the full purchase cost immediately in a single payment with zero interest.",
    ),
    "emi": (
        "EMI / Installment Financing",
        "Spread the capital outlay across monthly installments with an annual financing rate.",
    ),
    "phased": (
        "Phased / Milestone Purchase",
        "Split the purchase into two equal tranches (50/50) to smooth the cash-flow impact.",
    ),
    "trim": (
        "Trim & Buy",
        "Optimally reduce discretionary spending to protect the emergency reserve while purchasing.",
    ),
}


def _build_base_goal(decision: Any) -> Any:
    """
    Convert a ParsedDecision into a base PurchaseGoal.

    Args:
        decision: ParsedDecision instance.

    Returns:
        PurchaseGoal
    """
    from engine.model import PurchaseGoal

    return PurchaseGoal(
        item_name=decision.item_label,
        total_cost=decision.total_cost,
        emergency_floor=decision.emergency_floor,
        target_month=decision.target_month,
        financing_mode=decision.financing_preference if decision.financing_preference != "auto" else "upfront",
        emi_months=decision.emi_months,
        downpayment=0.0,
        interest_rate_annual=0.10,
        phased_splits=[],
        max_trim_pct=0.35,
        flexible_categories=[],
    )


def _feasibility_check(decision: Any, baseline: Any) -> Optional[str]:
    """
    Sanity check the parsed decision against the baseline.

    Returns:
        Error message if infeasible, None if OK.
    """
    if decision.total_cost <= 0:
        return "total_cost must be > 0"
    if decision.emergency_floor < 0:
        return "emergency_floor must be >= 0"
    if baseline is not None:
        starting = getattr(baseline, "starting_balance", 0.0)
        if starting > 0 and decision.total_cost > 10 * starting:
            return (
                f"total_cost ({decision.total_cost:,.0f}) exceeds 10x starting_balance "
                f"({starting:,.0f}); likely a parse error"
            )
    return None


def _apply_fork(
    fork_id: str,
    base_goal: Any,
    baseline: Any,
) -> ForkSpec:
    """
    Apply the matching engine.changes transformer and build a ForkSpec.

    Args:
        fork_id:   "upfront" | "emi" | "phased" | "trim"
        base_goal: Base PurchaseGoal.
        baseline:  FinancialProblemInstance.

    Returns:
        ForkSpec with status "ready" or "error".
    """
    from engine.changes import (
        apply_discretionary_trim,
        apply_emi_split,
        apply_phased_delay,
        apply_upfront,
    )

    _APPLIERS = {
        "upfront": apply_upfront,
        "emi": apply_emi_split,
        "phased": apply_phased_delay,
        "trim": apply_discretionary_trim,
    }

    title, description = _FORK_METADATA[fork_id]
    applier = _APPLIERS[fork_id]

    try:
        transformed_goal = applier(baseline, base_goal)
        return ForkSpec(
            fork_id=fork_id,
            title=title,
            policy_description=description,
            goal=transformed_goal,
            status="ready",
            infeasibility_reason=None,
        )
    except Exception as exc:
        logger.warning("Fork '%s' transformer raised: %s", fork_id, exc)
        return ForkSpec(
            fork_id=fork_id,
            title=title,
            policy_description=description,
            goal=base_goal,  # keep base goal as fallback
            status="error",
            infeasibility_reason=str(exc),
        )


# ===========================================================================
# Plain-Python implementation (always available)
# ===========================================================================


def _build_forks_plain(
    prompt: str,
    baseline: Any,
    dataset_type: str,
) -> ForkSet:
    """
    Plain-Python fan-out into 4 policy forks.

    Nodes (sequential):
        1. parse: parse_financial_decision
        2. feasibility_check
        3. fork_upfront, fork_emi, fork_phased, fork_trim  (fan-out)
        4. collect: assemble ForkSet

    Args:
        prompt:       Plain-English decision prompt.
        baseline:     FinancialProblemInstance.
        dataset_type: "personal" | "institute" | "startup".

    Returns:
        ForkSet with exactly 4 forks.
    """
    from ai.agents.parser import DecisionParseError, parse_financial_decision

    # Node: parse
    try:
        decision = parse_financial_decision(prompt, baseline=baseline, dataset_type=dataset_type)
    except DecisionParseError as exc:
        logger.error("scenario: parse failed: %s", exc)
        # Return 4 error forks with minimal data
        from engine.model import PurchaseGoal
        dummy_goal = PurchaseGoal(item_name="Unknown", total_cost=0.0)
        from ai.agents.parser import ParsedDecision
        dummy_decision = ParsedDecision(
            item_label="Unknown",
            total_cost=0.0,
            emergency_floor=0.0,
            quantity=None,
            target_month=0,
            financing_preference="auto",
            emi_months=6,
            dataset_type=dataset_type,
            raw_prompt=prompt,
            defaulted_fields=["total_cost"],
        )
        forks = [
            ForkSpec(
                fork_id=fid,
                title=_FORK_METADATA[fid][0],
                policy_description=_FORK_METADATA[fid][1],
                goal=dummy_goal,
                status="error",
                infeasibility_reason=str(exc),
            )
            for fid in ["upfront", "emi", "phased", "trim"]
        ]
        return ForkSet(decision=dummy_decision, baseline_goal=dummy_goal, forks=forks)

    # Node: feasibility_check
    infeasibility = _feasibility_check(decision, baseline)

    # Build base goal
    base_goal = _build_base_goal(decision)

    if infeasibility:
        logger.warning("scenario: feasibility check failed: %s", infeasibility)
        forks = [
            ForkSpec(
                fork_id=fid,
                title=_FORK_METADATA[fid][0],
                policy_description=_FORK_METADATA[fid][1],
                goal=base_goal,
                status="infeasible",
                infeasibility_reason=infeasibility,
            )
            for fid in ["upfront", "emi", "phased", "trim"]
        ]
        return ForkSet(decision=decision, baseline_goal=base_goal, forks=forks)

    # Fan-out: apply 4 transformers
    forks = [_apply_fork(fid, base_goal, baseline) for fid in ["upfront", "emi", "phased", "trim"]]

    # Node: collect
    return ForkSet(decision=decision, baseline_goal=base_goal, forks=forks)


# ===========================================================================
# LangGraph implementation (when available)
# ===========================================================================


def _try_build_forks_langgraph(
    prompt: str,
    baseline: Any,
    dataset_type: str,
) -> Optional[ForkSet]:
    """
    Try to run the fan-out using a LangGraph StateGraph.
    Returns ForkSet or None if LangGraph is not available.
    """
    try:
        from typing import TypedDict

        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    from ai.agents.parser import DecisionParseError, parse_financial_decision

    # State schema
    class _State(TypedDict, total=False):
        prompt: str
        baseline: Any
        dataset_type: str
        decision: Any
        base_goal: Any
        infeasibility: Optional[str]
        forks: List[ForkSpec]
        error: Optional[str]

    # Node functions --------------------------------------------------------

    def node_parse(state: _State) -> _State:
        try:
            decision = parse_financial_decision(
                state["prompt"],
                baseline=state.get("baseline"),
                dataset_type=state.get("dataset_type", "personal"),
            )
            return {**state, "decision": decision, "error": None}
        except DecisionParseError as exc:
            return {**state, "decision": None, "error": str(exc)}

    def node_feasibility(state: _State) -> _State:
        if state.get("error") or state.get("decision") is None:
            return {**state, "infeasibility": state.get("error")}
        decision = state["decision"]
        base_goal = _build_base_goal(decision)
        infeasibility = _feasibility_check(decision, state.get("baseline"))
        return {**state, "base_goal": base_goal, "infeasibility": infeasibility}

    def node_fork_upfront(state: _State) -> _State:
        forks = list(state.get("forks") or [])
        if state.get("infeasibility") or not state.get("base_goal"):
            forks.append(ForkSpec(
                fork_id="upfront", title=_FORK_METADATA["upfront"][0],
                policy_description=_FORK_METADATA["upfront"][1],
                goal=state.get("base_goal"), status="infeasible",
                infeasibility_reason=state.get("infeasibility"),
            ))
        else:
            forks.append(_apply_fork("upfront", state["base_goal"], state["baseline"]))
        return {**state, "forks": forks}

    def node_fork_emi(state: _State) -> _State:
        forks = list(state.get("forks") or [])
        if state.get("infeasibility") or not state.get("base_goal"):
            forks.append(ForkSpec(
                fork_id="emi", title=_FORK_METADATA["emi"][0],
                policy_description=_FORK_METADATA["emi"][1],
                goal=state.get("base_goal"), status="infeasible",
                infeasibility_reason=state.get("infeasibility"),
            ))
        else:
            forks.append(_apply_fork("emi", state["base_goal"], state["baseline"]))
        return {**state, "forks": forks}

    def node_fork_phased(state: _State) -> _State:
        forks = list(state.get("forks") or [])
        if state.get("infeasibility") or not state.get("base_goal"):
            forks.append(ForkSpec(
                fork_id="phased", title=_FORK_METADATA["phased"][0],
                policy_description=_FORK_METADATA["phased"][1],
                goal=state.get("base_goal"), status="infeasible",
                infeasibility_reason=state.get("infeasibility"),
            ))
        else:
            forks.append(_apply_fork("phased", state["base_goal"], state["baseline"]))
        return {**state, "forks": forks}

    def node_fork_trim(state: _State) -> _State:
        forks = list(state.get("forks") or [])
        if state.get("infeasibility") or not state.get("base_goal"):
            forks.append(ForkSpec(
                fork_id="trim", title=_FORK_METADATA["trim"][0],
                policy_description=_FORK_METADATA["trim"][1],
                goal=state.get("base_goal"), status="infeasible",
                infeasibility_reason=state.get("infeasibility"),
            ))
        else:
            forks.append(_apply_fork("trim", state["base_goal"], state["baseline"]))
        return {**state, "forks": forks}

    def node_collect(state: _State) -> _State:
        # Already assembled in forks list
        return state

    # Build graph -----------------------------------------------------------
    try:
        graph = StateGraph(_State)
        graph.add_node("parse", node_parse)
        graph.add_node("feasibility_check", node_feasibility)
        graph.add_node("fork_upfront", node_fork_upfront)
        graph.add_node("fork_emi", node_fork_emi)
        graph.add_node("fork_phased", node_fork_phased)
        graph.add_node("fork_trim", node_fork_trim)
        graph.add_node("collect", node_collect)

        graph.set_entry_point("parse")
        graph.add_edge("parse", "feasibility_check")
        # Sequential fan-out (LangGraph doesn't support true parallel fan-out in simple API)
        graph.add_edge("feasibility_check", "fork_upfront")
        graph.add_edge("fork_upfront", "fork_emi")
        graph.add_edge("fork_emi", "fork_phased")
        graph.add_edge("fork_phased", "fork_trim")
        graph.add_edge("fork_trim", "collect")
        graph.add_edge("collect", END)

        compiled = graph.compile()
        init_state: _State = {
            "prompt": prompt,
            "baseline": baseline,
            "dataset_type": dataset_type,
            "forks": [],
        }
        final_state = compiled.invoke(init_state)

        forks = final_state.get("forks") or []
        decision = final_state.get("decision")
        base_goal = final_state.get("base_goal")

        if decision is None:
            # Parse failed — return error ForkSet via plain path
            return None

        # Ensure exactly 4 forks
        fork_ids_seen = {f.fork_id for f in forks}
        for fid in ["upfront", "emi", "phased", "trim"]:
            if fid not in fork_ids_seen:
                forks.append(ForkSpec(
                    fork_id=fid,
                    title=_FORK_METADATA[fid][0],
                    policy_description=_FORK_METADATA[fid][1],
                    goal=base_goal,
                    status="error",
                    infeasibility_reason="fork not built by graph",
                ))

        # Sort to canonical order
        order = {"upfront": 0, "emi": 1, "phased": 2, "trim": 3}
        forks.sort(key=lambda f: order.get(f.fork_id, 99))

        return ForkSet(decision=decision, baseline_goal=base_goal, forks=forks)

    except Exception as exc:
        logger.warning("LangGraph build_forks failed: %s", exc)
        return None


# ===========================================================================
# Public API
# ===========================================================================


def build_forks(
    prompt: str,
    baseline: Any,  # FinancialProblemInstance
    dataset_type: str = "personal",
) -> ForkSet:
    """
    Parse the prompt and fan out into 4 competing policy forks.

    Uses LangGraph StateGraph internally when langgraph is installed.
    Falls back to plain Python function calls with identical interface.
    Works fully offline (parser fallback + deterministic transformers).

    Args:
        prompt:       Plain-English financial decision prompt.
        baseline:     FinancialProblemInstance (Node 0 baseline).
        dataset_type: "personal" | "institute" | "startup".

    Returns:
        ForkSet with exactly 4 ForkSpec objects in order: upfront, emi, phased, trim.
    """
    # Try LangGraph first
    offline = os.environ.get("FUTUREFORK_OFFLINE", "").strip() in ("1", "true", "yes")
    if not offline:
        result = _try_build_forks_langgraph(prompt, baseline, dataset_type)
        if result is not None:
            logger.info("scenario: used LangGraph StateGraph")
            return result
        logger.info("scenario: LangGraph unavailable or failed, using plain Python")

    # Fallback to plain Python
    result = _build_forks_plain(prompt, baseline, dataset_type)
    logger.info("scenario: used plain Python fan-out")
    return result
