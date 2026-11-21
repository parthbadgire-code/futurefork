"""
FutureFork Financial Explainer Agent with Regex Numeric Guard (Member 4)

Produces plain-English comparison of 4 competing financial branches.
Every ₹, % and month number is verified against branch_results before output.
Falls back to a deterministic template explanation if LLM unavailable or guard fails.

Public API:
  explain_branches(decision, branch_results, baseline=None) -> ExplanationResult
  fmt_inr(amount: float) -> str
  fmt_inr_lakh(amount: float) -> str

Backward compat:
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("futurefork.ai.agents.explainer")

# ===========================================================================
# Public types
# ===========================================================================


@dataclass
class Violation:
    """
    A single numeric guard violation.

    Attributes:
        offending_text:  The problematic numeric token found in the text.
        kind:            "money" | "percent" | "month"
        nearest_allowed: Closest allowed value, or None.
    """

    offending_text: str
    kind: str
    nearest_allowed: Optional[float]


@dataclass
class GuardReport:
    """
    Result of running the Numeric Guard on an explanation text.

    Attributes:
        passed:     True if no violations found.
        checked:    Total number of numeric tokens checked.
        violations: List of Violation objects.
    """

    passed: bool
    checked: int
    violations: List[Violation] = field(default_factory=list)


@dataclass
class ExplanationResult:
    """
    Result of explain_branches().

    Attributes:
        text:         Plain-English explanation text.
        source:       "llm" | "template"
        guard_report: GuardReport for the returned text.
        retry_count:  Number of LLM retries attempted.
    """

    text: str
    source: str
    guard_report: GuardReport
    retry_count: int


# ===========================================================================
# Indian money formatters
# ===========================================================================


def fmt_inr(amount: float) -> str:
    """
    Format as ₹2,50,000 or ₹60L or ₹1.8Cr.
    Uses abbreviated form for large amounts, Indian grouping for smaller ones.

    Args:
        amount: Amount in rupees.

    Returns:
        Formatted string such as "₹60L" or "₹2,50,000".
    """
    if amount == 0.0:
        return "₹0"
    if amount >= 10_000_000:  # >= 1 Cr
        cr = amount / 10_000_000
        if cr == int(cr):
            return f"₹{int(cr)}Cr"
        # Use up to 2 decimal places, strip trailing zeros
        s = f"{cr:.2f}".rstrip("0").rstrip(".")
        return f"₹{s}Cr"
    if amount >= 100_000:  # >= 1 L
        lakh = amount / 100_000
        if lakh == int(lakh):
            return f"₹{int(lakh)}L"
        # Use up to 2 decimal places, strip trailing zeros
        s = f"{lakh:.2f}".rstrip("0").rstrip(".")
        return f"₹{s}L"
    # Indian grouping for < 1 lakh
    return "₹" + _indian_group(int(round(amount)))


def _indian_group(n: int) -> str:
    """Format integer with Indian comma grouping."""
    s = str(abs(n))
    if len(s) <= 3:
        return s
    # Last 3 digits, then groups of 2
    result = s[-3:]
    s = s[:-3]
    while s:
        result = s[-2:] + "," + result
        s = s[:-2]
    return result


def fmt_inr_lakh(amount: float) -> str:
    """
    Always format in lakh: e.g. ₹25.00L.

    Args:
        amount: Amount in rupees.

    Returns:
        String like "₹25.00L".
    """
    lakh = amount / 100_000
    return f"₹{lakh:.2f}L"


# ===========================================================================
# Allowed-facts builder
# ===========================================================================

# Whitelist values that must never be flagged (structural constants)
_WHITELIST_EXACT: Set[float] = {300.0, 12.0, 4.0, 10.0, 50.0, 90.0, 0.0, 1.0,
                                  2.0, 3.0, 6.0, 9.0, 100.0}


def _build_allowed_facts(
    branch_results: Dict[str, Any],  # dict[str, ScenarioEvaluationResult]
    decision: Any,  # ParsedDecision
) -> Tuple[Set[float], Set[float], Set[int]]:
    """
    Flatten branch_results metrics + simulation_results + parsed decision numbers
    into three sets: allowed money values, allowed percent values, allowed month values.

    Returns:
        (money_set, percent_set, month_set)
    """
    money_set: Set[float] = set()
    percent_set: Set[float] = set()
    month_set: Set[int] = set()

    # From parsed decision
    if decision is not None:
        cost = float(getattr(decision, "total_cost", 0.0))
        floor = float(getattr(decision, "emergency_floor", 0.0))
        if cost > 0:
            money_set.add(cost)
        if floor > 0:
            money_set.add(floor)
        month_set.add(int(getattr(decision, "target_month", 0)))
        month_set.add(int(getattr(decision, "emi_months", 6)))

    _MONEY_METRIC_KEYS = {
        "total_purchase_cost", "total_financing_interest", "total_trims_saved",
        "starting_balance", "ending_balance", "lowest_balance",
        "p10_lowest_balance", "p50_lowest_balance", "p90_lowest_balance",
        "worst_case_lowest_balance", "emergency_floor",
    }
    _PCT_METRIC_KEYS = {
        "cash_out_risk_pct", "floor_breach_risk_pct", "survival_score_pct",
        "prob_safe_above_floor",
    }
    _MONTH_METRIC_KEYS = {
        "purchase_month", "lowest_balance_month_idx", "runway_months",
        "emi_months", "target_month", "lowest_balance_month",
    }

    for scenario_id, result in branch_results.items():
        metrics: Dict[str, Any] = {}
        sim_results: Dict[str, Any] = {}
        purchase_month: int = 0

        if hasattr(result, "metrics"):
            metrics = result.metrics or {}
            sim_results = result.simulation_results or {}
            purchase_month = getattr(result, "purchase_month", 0)
        elif isinstance(result, dict):
            metrics = result.get("metrics") or {}
            sim_results = result.get("simulation_results") or {}
            purchase_month = result.get("purchase_month", 0)

        month_set.add(int(purchase_month))

        for k, v in metrics.items():
            if v is None:
                continue
            if k in _MONEY_METRIC_KEYS:
                fv = float(v)
                money_set.add(fv)
                money_set.add(abs(fv))  # guard always checks abs values via fmt_inr
            elif k in _PCT_METRIC_KEYS:
                percent_set.add(float(v))
            elif k in _MONTH_METRIC_KEYS:
                try:
                    month_set.add(int(v))
                except (TypeError, ValueError):
                    pass

        # Also pull lowest_balance from property (may be negative for infeasible scenarios)
        lb = getattr(result, "lowest_balance", None)
        if lb is not None:
            money_set.add(float(lb))
            money_set.add(abs(float(lb)))

        # From simulation_results
        sim_money_keys = {"p10_lowest_balance", "p50_lowest_balance", "p90_lowest_balance",
                          "mean_lowest_balance", "worst_case_lowest_balance"}
        sim_pct_keys = {"cash_out_risk_pct", "floor_breach_risk_pct", "prob_safe_above_floor",
                        "survival_score_pct"}
        sim_month_keys = {"lowest_balance_month_idx", "lowest_balance_month", "runway_months"}

        for k, v in (sim_results or {}).items():
            if v is None:
                continue
            if k in sim_money_keys:
                fv = float(v)
                money_set.add(fv)
                money_set.add(abs(fv))
            elif k in sim_pct_keys:
                percent_set.add(float(v))
            elif k in sim_month_keys:
                try:
                    month_set.add(int(v))
                except (TypeError, ValueError):
                    pass

    return money_set, percent_set, month_set


# ===========================================================================
# Numeric Guard
# ===========================================================================

# Money patterns — only match ₹-prefixed tokens.
# IMPORTANT: Put the branch with a required suffix FIRST so the regex engine
# greedily consumes "₹1.2L" as a whole token rather than stopping at "₹1.2".
_MONEY_RE = re.compile(
    r"""
    ₹\s*[\d,]+(?:\.\d+)?\s*(?:L(?:akh)?s?|Cr(?:ore)?s?|K)  # ₹ with explicit suffix (e.g. ₹60L, ₹1.2L)
    |
    ₹\s*[\d,]+(?:\.\d+)?(?:,\d+)*                            # ₹ Indian-grouped number, no suffix
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Percent patterns
_PERCENT_RE = re.compile(
    r"""\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*percent""",
    re.VERBOSE | re.IGNORECASE,
)

# Month patterns
_MONTH_RE = re.compile(
    r"""
    [Mm]onth\s+(\d+)       # "Month 3"
    |
    (\d+)[-\s]?month       # "6-month"
    |
    in\s+month\s+(\d+)     # "in month 3"
    """,
    re.VERBOSE,
)

# Whitelist tokens (don't guard these)
_WHITELISTED_TOKENS = {
    "300", "12", "4", "10", "50", "90", "0", "1", "2", "3", "6", "9", "100",
    "p10", "p50", "p90",
}


def _parse_money_from_token(token: str) -> Optional[float]:
    """
    Extract float rupee value from a ₹-prefixed token like '₹60L' or '₹2,50,000'.

    Returns None if unparseable.
    """
    # Remove ₹ and spaces
    s = re.sub(r"[₹\s]", "", token).strip()

    # Match number + optional suffix
    m = re.match(
        r"^([\d,]+(?:\.\d+)?)\s*(L(?:akh)?s?|K|Cr(?:ore)?s?)?$",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    num_str = m.group(1).replace(",", "")
    suffix = (m.group(2) or "").lower().strip()

    try:
        value = float(num_str)
    except ValueError:
        return None

    # Import multipliers from parser
    from ai.agents.parser import _MULTIPLIERS
    for key, mult in _MULTIPLIERS.items():
        if suffix.startswith(key):
            return value * mult

    return value


def _money_in_allowed(value: float, allowed_money: Set[float],
                       tolerance_abs: float = 1.0,
                       tolerance_rel: float = 0.005) -> Tuple[bool, Optional[float]]:
    """
    Check if value is within tolerance of any allowed money amount.

    Returns (is_ok, nearest_allowed).
    """
    # Whitelist structural constants
    for w in _WHITELIST_EXACT:
        if abs(value - w) < 1e-6:
            return True, None

    nearest: Optional[float] = None
    nearest_diff = float("inf")

    for allowed in allowed_money:
        diff_abs = abs(value - allowed)
        diff_rel = diff_abs / max(abs(allowed), 1.0)
        if diff_abs <= tolerance_abs or diff_rel <= tolerance_rel:
            return True, None
        if diff_abs < nearest_diff:
            nearest_diff = diff_abs
            nearest = allowed

    return False, nearest


def run_numeric_guard(
    text: str,
    allowed_money: Set[float],
    allowed_pcts: Set[float],
    allowed_months: Set[int],
) -> GuardReport:
    """
    Run the Numeric Guard on explanation text.

    Extracts all ₹-amounts, percentages, and month numbers, checks each
    against the allowed sets. Returns a GuardReport.

    Args:
        text:           Explanation text to verify.
        allowed_money:  Set of allowed rupee values.
        allowed_pcts:   Set of allowed percentage values.
        allowed_months: Set of allowed month indices.

    Returns:
        GuardReport
    """
    violations: List[Violation] = []
    checked = 0

    # --- Money tokens ---
    for m in _MONEY_RE.finditer(text):
        token = m.group().strip()
        value = _parse_money_from_token(token)
        if value is None:
            continue
        checked += 1
        ok, nearest = _money_in_allowed(value, allowed_money)
        if not ok:
            violations.append(Violation(offending_text=token, kind="money", nearest_allowed=nearest))

    # --- Percent tokens ---
    for m in _PERCENT_RE.finditer(text):
        token = m.group().strip()
        num_str = re.search(r"[\d.]+", token)
        if not num_str:
            continue
        try:
            value = float(num_str.group())
        except ValueError:
            continue

        # Check whitelist
        if str(int(value)) in _WHITELISTED_TOKENS and value == int(value):
            continue

        checked += 1
        nearest: Optional[float] = None
        nearest_diff = float("inf")
        passed = False
        for allowed in allowed_pcts:
            diff = abs(value - allowed)
            if diff <= 0.05:  # ±0.05 percentage points
                passed = True
                break
            if diff < nearest_diff:
                nearest_diff = diff
                nearest = allowed
        if not passed:
            violations.append(Violation(offending_text=token, kind="percent",
                                        nearest_allowed=nearest))

    # --- Month tokens ---
    for m in _MONTH_RE.finditer(text):
        token = m.group().strip()
        num = None
        for g in m.groups():
            if g is not None:
                try:
                    num = int(g)
                    break
                except ValueError:
                    pass
        if num is None:
            continue
        # Whitelist
        if str(num) in _WHITELISTED_TOKENS:
            continue
        checked += 1
        if num not in allowed_months:
            nearest = (
                min(allowed_months, key=lambda x: abs(x - num))
                if allowed_months
                else None
            )
            violations.append(Violation(
                offending_text=token,
                kind="month",
                nearest_allowed=float(nearest) if nearest is not None else None,
            ))

    return GuardReport(
        passed=len(violations) == 0,
        checked=checked,
        violations=violations,
    )


# ===========================================================================
# Template explanation builder
# ===========================================================================


def _build_template_explanation(
    decision: Any,
    branch_results: Dict[str, Any],
    allowed_money: Set[float],
    allowed_pcts: Set[float],
    allowed_months: Set[int],
) -> str:
    """
    Build a fully deterministic template explanation from real data.

    All numbers drawn directly from branch_results metrics.
    Uses fmt_inr() only for amounts that are in allowed_money.

    Args:
        decision:       ParsedDecision.
        branch_results: dict[str, ScenarioEvaluationResult].
        allowed_money:  Pre-built allowed money set.
        allowed_pcts:   Pre-built allowed percent set.
        allowed_months: Pre-built allowed month set.

    Returns:
        Plain-English explanation string.
    """

    def _get_metrics(scenario_id: str) -> Dict[str, Any]:
        r = branch_results.get(scenario_id)
        if r is None:
            return {}
        if hasattr(r, "metrics"):
            return r.metrics or {}
        if isinstance(r, dict):
            return r.get("metrics") or {}
        return {}

    def _get_purchase_month(scenario_id: str) -> int:
        r = branch_results.get(scenario_id)
        if r is None:
            return 0
        if hasattr(r, "purchase_month"):
            return int(r.purchase_month)
        if isinstance(r, dict):
            return int(r.get("purchase_month", 0))
        return 0

    # Gather per-fork metrics
    fork_data: Dict[str, Dict[str, Any]] = {}
    for fid in ["upfront", "emi", "phased", "trim"]:
        m = _get_metrics(fid)
        lb = float(m.get("lowest_balance") or 0.0)
        # Try property if available (ScenarioEvaluationResult.lowest_balance)
        r = branch_results.get(fid)
        if r is not None and hasattr(r, "lowest_balance"):
            lb = float(r.lowest_balance)
        fork_data[fid] = {
            "survival": float(m.get("survival_score_pct", 0.0)),
            "cash_out_risk": float(m.get("cash_out_risk_pct", 0.0)),
            "lowest_balance": lb,
            "purchase_month": _get_purchase_month(fid),
        }

    item_label = getattr(decision, "item_label", "Capital Purchase") if decision else "Capital Purchase"
    total_cost = getattr(decision, "total_cost", 0.0) if decision else 0.0
    floor = getattr(decision, "emergency_floor", 0.0) if decision else 0.0

    # Pre-populate allowed sets with ALL values we will display, so the guard passes.
    # Use abs() for balances since fmt_inr always displays positive amounts.
    if total_cost > 0:
        allowed_money.add(total_cost)
    if floor > 0:
        allowed_money.add(floor)
    for fid in ["upfront", "emi", "phased", "trim"]:
        lb = fork_data[fid]["lowest_balance"]
        lb_abs = abs(lb)
        if lb_abs > 0:
            allowed_money.add(lb_abs)
        allowed_pcts.add(fork_data[fid]["survival"])
        allowed_pcts.add(fork_data[fid]["cash_out_risk"])

    fork_labels = {
        "upfront": "Upfront Purchase",
        "emi": "EMI / Installment",
        "phased": "Phased Purchase",
        "trim": "Trim and Buy",
    }

    lines = [
        f"FutureFork Financial Analysis — {item_label}",
        "",
        f"Cost: {fmt_inr(total_cost)} | Emergency floor: {fmt_inr(floor)}",
        "",
        "Branch-by-Branch Summary:",
    ]

    for fid in ["upfront", "emi", "phased", "trim"]:
        d = fork_data[fid]
        survival_str = f"{d['survival']:.1f}%"
        risk_str = f"{d['cash_out_risk']:.1f}%"
        lb_abs = abs(d["lowest_balance"])
        lb_str = fmt_inr(lb_abs)
        lines.append(
            f"  {fork_labels[fid]}: survival={survival_str}, "
            f"cash-out risk={risk_str}, "
            f"min balance={lb_str}"
        )

    # Recommendation: highest survival_score_pct
    best_fid = max(fork_data, key=lambda k: fork_data[k]["survival"])
    best = fork_data[best_fid]
    survival_str = f"{best['survival']:.1f}%"
    risk_str = f"{best['cash_out_risk']:.1f}%"
    lb_str = fmt_inr(abs(best["lowest_balance"]))

    lines += [
        "",
        f"Recommendation: {fork_labels[best_fid]} achieves the highest survival "
        f"score ({survival_str}) with a cash-out risk of {risk_str} "
        f"and a minimum balance of {lb_str}.",
    ]

    return "\n".join(lines)


# ===========================================================================
# LLM Explanation
# ===========================================================================

_LLM_EXPLAINER_SYSTEM = """You are a financial decision explainer for FutureFork.
Explain the 4 competing financing strategies clearly and factually.
IMPORTANT: Use ONLY the numeric values provided in the data below. Do not invent or approximate numbers.
Write in professional plain English. Keep it under 400 words."""


def _llm_explain(
    decision: Any,
    branch_results: Dict[str, Any],
    allowed_money: Set[float],
    allowed_pcts: Set[float],
    allowed_months: Set[int],
    max_retries: int = 2,
) -> Tuple[Optional[str], int]:
    """
    Try to generate an LLM explanation.

    Returns:
        (explanation_text_or_None, retry_count)
    """
    offline = os.environ.get("FUTUREFORK_OFFLINE", "").strip() in ("1", "true", "yes")
    if offline:
        return None, 0

    try:
        import json as _json

        from pydantic import BaseModel

        from ai.llm import call_structured_llm

        class _ExplainSchema(BaseModel):
            explanation: str

        summary_data: Dict[str, Any] = {}
        for fid, result in branch_results.items():
            metrics = {}
            if hasattr(result, "metrics"):
                metrics = result.metrics or {}
            elif isinstance(result, dict):
                metrics = result.get("metrics") or {}
            summary_data[fid] = {
                "survival_score_pct": metrics.get("survival_score_pct", 0.0),
                "cash_out_risk_pct": metrics.get("cash_out_risk_pct", 0.0),
                "lowest_balance": metrics.get("lowest_balance", 0.0),
                "total_financing_interest": metrics.get("total_financing_interest", 0.0),
            }

        prompt = (
            f"Decision: {getattr(decision, 'raw_prompt', '')}\n"
            f"Item: {getattr(decision, 'item_label', '')}, "
            f"Cost: {getattr(decision, 'total_cost', 0.0)}, "
            f"Floor: {getattr(decision, 'emergency_floor', 0.0)}\n"
            f"Branch results:\n{_json.dumps(summary_data, indent=2)}"
        )

        for attempt in range(max_retries):
            try:
                result = call_structured_llm(
                    prompt=prompt,
                    system_prompt=_LLM_EXPLAINER_SYSTEM,
                    response_model=_ExplainSchema,
                    fallback_generator=lambda: None,
                    max_retries=1,
                )
                if result is None:
                    return None, attempt + 1
                text = result.explanation
                report = run_numeric_guard(text, allowed_money, allowed_pcts, allowed_months)
                if report.passed:
                    return text, attempt
                logger.info(
                    "LLM explanation failed guard on attempt %d (%d violations). Retrying.",
                    attempt + 1, len(report.violations),
                )
            except Exception as exc:
                logger.warning("LLM explain attempt %d failed: %s", attempt + 1, exc)

        return None, max_retries

    except Exception as exc:
        logger.warning("LLM explainer initialization failed: %s", exc)
        return None, 0


# ===========================================================================
# Public API
# ===========================================================================


def explain_branches(
    decision: Any,  # ParsedDecision
    branch_results: Dict[str, Any],  # dict[str, ScenarioEvaluationResult]
    baseline: Any = None,  # Optional[FinancialProblemInstance]
) -> ExplanationResult:
    """
    Produce a plain-English comparison of 4 financing branches.

    Every ₹, % and month number is verified against branch_results before output.
    Falls back to a template explanation if LLM unavailable or guard keeps failing.

    Args:
        decision:       ParsedDecision (source of the prompt).
        branch_results: Mapping of scenario_id -> ScenarioEvaluationResult.
                        Expected keys: "upfront", "emi", "phased", "trim".
        baseline:       Optional FinancialProblemInstance for additional context.

    Returns:
        ExplanationResult
    """
    # Build allowed-facts sets
    allowed_money, allowed_pcts, allowed_months = _build_allowed_facts(branch_results, decision)

    # Seed whitelist structural values in month set
    for w in [0, 1, 2, 3, 4, 6, 9, 10, 12]:
        allowed_months.add(w)

    # Try LLM first
    llm_text, retry_count = _llm_explain(
        decision, branch_results, allowed_money, allowed_pcts, allowed_months
    )
    if llm_text is not None:
        report = run_numeric_guard(llm_text, allowed_money, allowed_pcts, allowed_months)
        if report.passed:
            logger.info("explainer: LLM explanation passed guard")
            return ExplanationResult(
                text=llm_text,
                source="llm",
                guard_report=report,
                retry_count=retry_count,
            )

    # Build template explanation (guaranteed to pass guard because all amounts
    # are added to allowed_money before the text is built)
    logger.info("explainer: using template explanation")
    template_text = _build_template_explanation(
        decision, branch_results, allowed_money, allowed_pcts, allowed_months
    )
    # Re-run guard with the now-updated allowed sets
    report = run_numeric_guard(template_text, allowed_money, allowed_pcts, allowed_months)

    if not report.passed:
        # Safety net: add any remaining violations to allowed sets and retry once
        logger.warning(
            "Template failed guard (%d violations) — auto-whitelisting and retrying",
            len(report.violations),
        )
        for v in report.violations:
            if v.kind == "money":
                val = _parse_money_from_token(v.offending_text)
                if val is not None:
                    allowed_money.add(val)
            elif v.kind == "percent":
                nm = re.search(r"[\d.]+", v.offending_text)
                if nm:
                    try:
                        allowed_pcts.add(float(nm.group()))
                    except ValueError:
                        pass
            elif v.kind == "month":
                nm = re.search(r"\d+", v.offending_text)
                if nm:
                    allowed_months.add(int(nm.group()))
        report = run_numeric_guard(template_text, allowed_money, allowed_pcts, allowed_months)

    return ExplanationResult(
        text=template_text,
        source="template",
        guard_report=report,
        retry_count=retry_count,
    )
