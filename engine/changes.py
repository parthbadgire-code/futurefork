"""
FutureFork Optimization Engine: Change Appliers & Branch Transformers
Member 2: OR-Tools CP-SAT Financial Solver & Branch Transformers

Provides:
- apply_upfront: Branch 1 - 100% upfront purchase in target/earliest feasible month.
- apply_emi_split: Branch 2 - Structured installment financing over 6/12 months with interest.
- apply_phased_delay: Branch 3 - Multi-milestone split (e.g. 50/50) avoiding debt/interest.
- apply_discretionary_trim: Branch 4 - Optimized cuts across flexible categories to protect reserve.
- apply_financial_change: Unified financial change dispatcher.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from engine.model import (
    FinancialProblemInstance,
    PurchaseGoal,
)

# ==============================================================================
# FINANCIAL BRANCH TRANSFORMERS (MEMBER 2)
# ==============================================================================

def apply_upfront(
    instance: FinancialProblemInstance,
    goal: PurchaseGoal,
    params: Optional[Dict[str, Any]] = None,
) -> PurchaseGoal:
    """
    Branch 1: Upfront Purchase.
    Allocates 100% of purchase cost in target month (default Month 0) with 0% interest.
    """
    p = params or {}
    new_goal = copy.deepcopy(goal)
    new_goal.financing_mode = "upfront"
    new_goal.target_month = int(p.get("target_month", new_goal.target_month))
    new_goal.interest_rate_annual = 0.0
    new_goal.emi_months = 1
    new_goal.downpayment = new_goal.total_cost
    new_goal.phased_splits = [{"month": new_goal.target_month, "pct": 1.0}]
    return new_goal


def apply_emi_split(
    instance: FinancialProblemInstance,
    goal: PurchaseGoal,
    params: Optional[Dict[str, Any]] = None,
) -> PurchaseGoal:
    """
    Branch 2: EMI / Lease Financing.
    Spreads capital outlay across N months (default 6 or 12 months) with annual financing rate.
    """
    p = params or {}
    new_goal = copy.deepcopy(goal)
    new_goal.financing_mode = "emi"
    new_goal.emi_months = int(p.get("emi_months", p.get("months", new_goal.emi_months or 6)))
    if new_goal.emi_months < 2:
        new_goal.emi_months = 6

    # Downpayment percentage (e.g. 0.0 to 0.20)
    down_pct = float(p.get("downpayment_pct", 0.0))
    if down_pct > 0.0 and down_pct < 1.0:
        new_goal.downpayment = round(new_goal.total_cost * down_pct, 2)
    else:
        new_goal.downpayment = float(p.get("downpayment", 0.0))

    new_goal.interest_rate_annual = float(
        p.get("interest_rate_annual", p.get("interest_rate", new_goal.interest_rate_annual or 0.10))
    )
    new_goal.target_month = int(p.get("target_month", new_goal.target_month))
    return new_goal


def apply_phased_delay(
    instance: FinancialProblemInstance,
    goal: PurchaseGoal,
    params: Optional[Dict[str, Any]] = None,
) -> PurchaseGoal:
    """
    Branch 3: Phased Split / Milestone Delay.
    Splits acquisition into milestones (e.g. 50% in Month 0, 50% in Month 6) without interest debt.
    """
    p = params or {}
    new_goal = copy.deepcopy(goal)
    new_goal.financing_mode = "phased"
    new_goal.interest_rate_annual = 0.0

    splits = p.get("phased_splits") or p.get("splits")
    if not splits:
        # Default smart split: 50% at target_month (Month 0), 50% at Month 5 or 6 (mid-cycle revenue peak)
        m1 = int(p.get("month_1", new_goal.target_month))
        m2 = int(p.get("month_2", min(11, m1 + 5)))
        pct1 = float(p.get("pct_1", 0.5))
        pct2 = float(p.get("pct_2", 0.5))
        splits = [
            {"month": m1, "pct": pct1},
            {"month": m2, "pct": pct2},
        ]

    new_goal.phased_splits = splits
    return new_goal


def apply_discretionary_trim(
    instance: FinancialProblemInstance,
    goal: PurchaseGoal,
    params: Optional[Dict[str, Any]] = None,
) -> PurchaseGoal:
    """
    Branch 4: Trim-and-Buy (Discretionary Expenditure Reduction).
    Enables minimum-pain cuts across flexible categories (e.g. up to 35% cut) while
    strictly safeguarding fixed categories (salaries, rent, utilities) and emergency reserves.
    """
    p = params or {}
    new_goal = copy.deepcopy(goal)
    new_goal.financing_mode = "trim"
    new_goal.target_month = int(p.get("target_month", new_goal.target_month))
    new_goal.max_trim_pct = float(p.get("max_trim_pct", p.get("max_cut", 0.35)))

    # Identify flexible categories from instance if not explicitly provided
    flex_cats = p.get("flexible_categories")
    if not flex_cats:
        flex_cats = [
            cat for cat, ctype in instance.category_types.items()
            if ctype == "flexible"
        ]
    new_goal.flexible_categories = flex_cats
    return new_goal


BRANCH_TYPES = ("upfront", "emi", "phased", "trim")

_BRANCH_ALIASES = {
    "upfront": ("upfront", "buy_now", "immediate"),
    "emi": ("emi", "lease", "loan", "installment", "instalment"),
    "phased": ("phase", "delay", "milestone", "two_stage"),
    "trim": ("trim", "cut", "discretionary", "savings"),
}


def normalize_branch_type(change_type: str) -> str:
    """Maps a change type or alias (e.g. "phased_delay", "discretionary_trim") to a canonical fork type."""
    ct = str(change_type or "").lower()
    for canonical, aliases in _BRANCH_ALIASES.items():
        if any(a in ct for a in aliases):
            return canonical
    raise ValueError(
        f"Unsupported change type '{change_type}'. Supported fork types: {', '.join(BRANCH_TYPES)}"
    )


def apply_financial_change(
    instance: FinancialProblemInstance,
    change: Dict[str, Any],
    goal: Optional[PurchaseGoal] = None,
) -> PurchaseGoal:
    """
    Unified dispatcher for financial branch transformations.
    Accepts change spec dictionary and base PurchaseGoal.
    """
    change_type = str(change.get("type", "")).lower()
    params = change.get("params", {})

    base_goal = goal or PurchaseGoal.from_dict(params)

    appliers = {
        "upfront": apply_upfront,
        "emi": apply_emi_split,
        "phased": apply_phased_delay,
        "trim": apply_discretionary_trim,
    }
    return appliers[normalize_branch_type(change_type)](instance, base_goal, params)
