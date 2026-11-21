"""
FutureFork Financial Decision Parser Agent (Member 4)

Parses plain-English financial decision prompts into ParsedDecision objects.

Tier 1: LLM — structured JSON extraction.
Tier 2: Deterministic regex — always works offline.

Public API:
  parse_financial_decision(prompt, baseline=None, dataset_type="personal") -> ParsedDecision
  parse_indian_amount(text: str) -> float | None

Backward compat:
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("futurefork.ai.agents.parser")

# ===========================================================================
# Public types
# ===========================================================================


class DecisionParseError(Exception):
    """Raised when a prompt truly cannot be parsed into a financial decision."""


@dataclass
class ParsedDecision:
    """
    Parsed financial purchase decision.

    Attributes:
        item_label:            Human-readable item name.
        total_cost:            Total cost in rupees.
        emergency_floor:       Minimum reserve floor in rupees.
        quantity:              Number of units (or None).
        target_month:          Intended month index 0-11.
        financing_preference:  "auto"|"upfront"|"emi"|"phased"|"trim".
        emi_months:            EMI duration in months.
        dataset_type:          "personal"|"institute"|"startup".
        raw_prompt:            Original input prompt.
        defaulted_fields:      Fields that used baseline defaults.
    """

    item_label: str
    total_cost: float
    emergency_floor: float
    quantity: Optional[int]
    target_month: int
    financing_preference: str
    emi_months: int
    dataset_type: str
    raw_prompt: str
    defaulted_fields: List[str] = field(default_factory=list)


# ===========================================================================
# Indian number parser
# ===========================================================================

# Multipliers for Indian shorthand
_MULTIPLIERS: Dict[str, float] = {
    "cr": 10_000_000.0,
    "crore": 10_000_000.0,
    "crores": 10_000_000.0,
    "l": 100_000.0,
    "lakh": 100_000.0,
    "lakhs": 100_000.0,
    "lac": 100_000.0,
    "lacs": 100_000.0,
    "k": 1_000.0,
}

# Regex for Indian-style numbers: ₹60L, Rs 1.2L, 1.8 crore, 30k, 60,00,000, ₹25L
_INDIAN_AMOUNT_RE = re.compile(
    r"""
    (?:₹|Rs\.?\s*|INR\s*)?         # optional currency prefix
    ([\d,]+(?:\.\d+)?)             # digits with optional commas and decimals
    \s*
    (Cr(?:ore)?s?|L(?:akh)?s?|K)?  # optional multiplier suffix (case-insensitive)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_indian_amount(text: str) -> Optional[float]:
    """
    Parse a single Indian-format amount string to rupees.

    Handles:
        ₹60L, ₹1.2L, 1.2 lakh, 1.8Cr, 1.8 crore, 30k, ₹30,000,
        60,00,000 (Indian grouping), Rs 1.2L, ₹25L

    Args:
        text: Amount string such as "₹60L" or "1.8 crore".

    Returns:
        Float value in rupees, or None if unparseable.
    """
    text = text.strip()
    m = _INDIAN_AMOUNT_RE.search(text)
    if not m:
        return None

    num_str = m.group(1).replace(",", "")
    suffix = (m.group(2) or "").lower().strip()

    try:
        value = float(num_str)
    except ValueError:
        return None

    multiplier = 1.0
    for key, mult in _MULTIPLIERS.items():
        if suffix.startswith(key):
            multiplier = mult
            break

    return value * multiplier


# ===========================================================================
# Stricter amount regex — requires ₹/Rs prefix OR a multiplier suffix
# This prevents matching bare numbers like "2 engineers" or "40 GPU PCs"
# ===========================================================================

# Pattern 1: prefixed with ₹ or Rs (multiplier optional)
_PREFIXED_AMOUNT_RE = re.compile(
    r"""
    (?:₹|Rs\.?\s*)                     # ₹ or Rs prefix REQUIRED
    ([\d,]+(?:\.\d+)?)                 # number
    \s*
    (Cr(?:ore)?s?|L(?:akh)?s?|Lac?s?|K)?  # optional multiplier
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Pattern 2: no prefix but multiplier REQUIRED (e.g. "60L", "1.8 crore", "30k")
_SUFFIXED_AMOUNT_RE = re.compile(
    r"""
    \b
    ([\d,]+(?:\.\d+)?)                   # number
    \s*
    (Cr(?:ore)?s?|L(?:akh)?s?|K)        # multiplier REQUIRED (L(?:akh)?s? matches bare L)
    \b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Floor / reserve constraint pattern
_FLOOR_RE = re.compile(
    r"""
    (?:without\s+dropping\s+below|
       keep(?:ing)?\s+(?:at\s+least)?|
       maintain(?:ing)?\s+(?:a\s+)?|
       emergency\s+(?:savings?|reserves?|funds?)\s+of|
       dropping\s+below|
       minimum\s+(?:balance\s+of)?|
       at\s+least|
       reserve\s+of
    )
    \s+
    (?:₹|Rs\.?\s*)?
    ([\d,]+(?:\.\d+)?)
    \s*
    (Cr(?:ore)?s?|L(?:akh)?s?|K)?
    \b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Financing preference keywords
_FINANCING_KEYWORDS: Dict[str, str] = {
    "upfront": "upfront",
    "cash": "upfront",
    "outright": "upfront",
    "emi": "emi",
    "installment": "emi",
    "instalment": "emi",
    "loan": "emi",
    "lease": "emi",
    "financed": "emi",
    "phased": "phased",
    "milestone": "phased",
    "split": "phased",
    "trim": "trim",
    "trimming": "trim",
    "cut": "trim",
}

# Quantity pattern — "40 GPU lab PCs", "2 engineers"
_QUANTITY_RE = re.compile(
    r"\b(\d+)\s+(?:[A-Za-z]+\s+){0,3}"
    r"(?:pcs?|units?|sets?|servers?|engineers?|machines?|devices?|systems?|"
    r"laptops?|computers?|monitors?|tablets?|nodes?|gpus?|licences?|licenses?)\b",
    re.IGNORECASE,
)

# EMI months pattern
_EMI_MONTHS_RE = re.compile(
    r"\b(\d+)[- ]?months?\s+(?:emi|installment|instalment|loan)\b"
    r"|\b(?:emi|installment|instalment|loan)\s+(?:of\s+)?(\d+)[- ]?months?\b",
    re.IGNORECASE,
)

# Item label — after a purchase verb
_ITEM_VERB_RE = re.compile(
    r"\b(?:buy|purchase|acquire|invest\s+in|hire|recruit|get|procure)\s+(?:a\s+|an\s+|the\s+)?",
    re.IGNORECASE,
)


def _parse_amount_from_match(num_str: str, suffix: str) -> float:
    """Convert parsed number string + suffix into rupees."""
    num_str = num_str.replace(",", "")
    suffix = (suffix or "").lower()
    try:
        value = float(num_str)
    except ValueError:
        return 0.0
    multiplier = 1.0
    for key, mult in _MULTIPLIERS.items():
        if suffix.startswith(key):
            multiplier = mult
            break
    return value * multiplier


def _extract_all_amounts(text: str) -> List[tuple]:
    """
    Extract all amounts from text using strict patterns.
    Returns list of (start_pos, end_pos, rupee_value).
    """
    results = []

    # First pass: prefixed amounts (₹ / Rs)
    for m in _PREFIXED_AMOUNT_RE.finditer(text):
        val = _parse_amount_from_match(m.group(1), m.group(2) or "")
        if val > 0:
            results.append((m.start(), m.end(), val))

    # Second pass: suffixed amounts (no prefix, multiplier required)
    for m in _SUFFIXED_AMOUNT_RE.finditer(text):
        # Skip if already captured by prefixed pattern (overlapping)
        overlaps = any(s <= m.start() <= e for s, e, _ in results)
        if not overlaps:
            val = _parse_amount_from_match(m.group(1), m.group(2))
            if val > 0:
                results.append((m.start(), m.end(), val))

    # Sort by position
    results.sort(key=lambda x: x[0])
    return results


def _extract_floor(text: str) -> Optional[float]:
    """Extract emergency floor amount from text."""
    m = _FLOOR_RE.search(text)
    if not m:
        return None
    return _parse_amount_from_match(m.group(1), m.group(2) or "")


def _extract_item_label(text: str) -> str:
    """Extract the item/purchase description from the prompt."""
    m = _ITEM_VERB_RE.search(text)
    if m:
        rest = text[m.end():].strip()
        clip = re.search(
            r"\s+(?:without|for\s+(?:₹|Rs)|on\s+emi|upfront|worth|at|,|\.)",
            rest,
            re.IGNORECASE,
        )
        if clip:
            label = rest[: clip.start()].strip()
        else:
            label = rest[:60].strip()
        return label or "Capital Purchase"

    # Fallback: use text before first ₹
    price_match = re.search(r"[₹]|Rs\.?", text, re.IGNORECASE)
    if price_match:
        before = text[: price_match.start()].strip().rstrip("for").strip()
        if before:
            return before[-60:].strip()

    return "Capital Purchase"


def _extract_quantity(text: str) -> Optional[int]:
    """Extract item quantity from text."""
    m = _QUANTITY_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def _extract_financing(text: str) -> str:
    """Detect financing preference from keywords."""
    lower = text.lower()
    for keyword, pref in _FINANCING_KEYWORDS.items():
        if keyword in lower:
            return pref
    return "auto"


def _extract_emi_months(text: str) -> int:
    """Extract EMI duration in months."""
    m = _EMI_MONTHS_RE.search(text)
    if m:
        for g in m.groups():
            if g:
                return int(g)
    return 6


def _regex_parse(
    prompt: str,
    baseline_starting_balance: float = 0.0,
    dataset_type: str = "personal",
) -> ParsedDecision:
    """
    Deterministic regex parser for financial decision prompts.

    Args:
        prompt:                    Plain-English prompt.
        baseline_starting_balance: Starting balance for defaults.
        dataset_type:              Dataset context.

    Returns:
        ParsedDecision (may have defaults for missing fields).
    """
    defaulted: List[str] = []

    # --- Floor ---
    floor = _extract_floor(prompt)
    if floor is None:
        floor = 0.0
        defaulted.append("emergency_floor")

    # Find floor's position in text to avoid treating it as cost
    floor_match = _FLOOR_RE.search(prompt)

    # --- All amounts ---
    all_amounts = _extract_all_amounts(prompt)

    # --- Cost: first amount that is NOT the floor ---
    total_cost = None
    for start, end, val in all_amounts:
        # Skip if this overlaps with the floor match
        if floor_match and not (end <= floor_match.start() or start >= floor_match.end()):
            continue
        # Skip if value equals floor (and we already have floor)
        if floor_match and abs(val - floor) < 1.0:
            continue
        total_cost = val
        break

    if total_cost is None and floor is not None and floor > 0:
        # Maybe the first amount IS cost and second is floor
        for start, end, val in all_amounts:
            if abs(val - floor) > 1.0:
                total_cost = val
                break

    if total_cost is None:
        total_cost = 0.0
        defaulted.append("total_cost")

    # --- Quantity ---
    quantity = _extract_quantity(prompt)

    # --- Item label ---
    item_label = _extract_item_label(prompt)

    # --- Financing ---
    financing_preference = _extract_financing(prompt)

    # --- EMI months ---
    emi_months = _extract_emi_months(prompt) if financing_preference == "emi" else 6

    return ParsedDecision(
        item_label=item_label,
        total_cost=total_cost,
        emergency_floor=floor,
        quantity=quantity,
        target_month=0,
        financing_preference=financing_preference,
        emi_months=emi_months,
        dataset_type=dataset_type,
        raw_prompt=prompt,
        defaulted_fields=defaulted,
    )


# ===========================================================================
# LLM Tier
# ===========================================================================

_LLM_SYSTEM_PROMPT = """You are a financial decision parser for FutureFork.
Parse the user's prompt into a structured JSON object with these fields:
  item_label: string (what is being purchased/acquired)
  quantity: integer or null
  total_cost: float (in rupees, convert ₹60L → 6000000, ₹1.2L → 120000, 1.8Cr → 18000000, 30k → 30000)
  emergency_floor: float (minimum reserve in rupees, convert similarly, 0.0 if not stated)
  target_month: integer 0-11 (0 if immediate or not stated)
  financing_preference: one of "auto","upfront","emi","phased","trim"
  emi_months: integer (default 6, use stated value if given)
  dataset_type: one of "personal","institute","startup"

Output ONLY valid JSON. No explanation. All amounts must be in rupees (float).
"""


def _llm_parse(
    prompt: str,
    dataset_type: str,
) -> Optional[ParsedDecision]:
    """
    Try to parse the prompt using an LLM.

    Returns:
        ParsedDecision or None if LLM unavailable/fails.
    """
    offline = os.environ.get("FUTUREFORK_OFFLINE", "").strip() in ("1", "true", "yes")
    if offline:
        logger.debug("FUTUREFORK_OFFLINE=1: skipping LLM tier in parser.")
        return None

    try:
        from pydantic import BaseModel

        from ai.llm import call_structured_llm

        class _ParseSchema(BaseModel):
            item_label: str = "Capital Purchase"
            quantity: Optional[int] = None
            total_cost: float = 0.0
            emergency_floor: float = 0.0
            target_month: int = 0
            financing_preference: str = "auto"
            emi_months: int = 6
            dataset_type: str = "personal"

        result = call_structured_llm(
            prompt=f"Dataset type: {dataset_type}\nPrompt: {prompt}",
            system_prompt=_LLM_SYSTEM_PROMPT,
            response_model=_ParseSchema,
            fallback_generator=lambda: None,
            max_retries=1,
        )
        if result is None:
            return None

        return ParsedDecision(
            item_label=result.item_label or "Capital Purchase",
            total_cost=float(result.total_cost or 0.0),
            emergency_floor=float(result.emergency_floor or 0.0),
            quantity=result.quantity,
            target_month=int(result.target_month or 0),
            financing_preference=result.financing_preference or "auto",
            emi_months=int(result.emi_months or 6),
            dataset_type=result.dataset_type or dataset_type,
            raw_prompt=prompt,
            defaulted_fields=[],
        )
    except Exception as exc:
        logger.warning("LLM parse failed: %s", exc)
        return None


# ===========================================================================
# Public API
# ===========================================================================


def parse_financial_decision(
    prompt: str,
    baseline: Any = None,  # Optional[FinancialProblemInstance]
    dataset_type: str = "personal",
) -> ParsedDecision:
    """
    Parse a plain-English financial decision prompt into a ParsedDecision.

    Tier 1: LLM. Tier 2: Deterministic regex.
    Raises DecisionParseError if truly unparseable.

    Args:
        prompt:       Plain-English prompt, e.g. "Buy a ₹1.2L laptop on EMI".
        baseline:     Optional FinancialProblemInstance for context/defaults.
        dataset_type: "personal" | "institute" | "startup".

    Returns:
        ParsedDecision

    Raises:
        DecisionParseError: If prompt is too vague or completely unparseable.
    """
    prompt = prompt.strip()
    if not prompt:
        raise DecisionParseError("Empty prompt provided.")

    baseline_balance = 0.0
    if baseline is not None:
        baseline_balance = getattr(baseline, "starting_balance", 0.0)

    # Tier 1: LLM
    llm_result = _llm_parse(prompt, dataset_type)
    if llm_result is not None and llm_result.total_cost > 0:
        logger.info("parser: used LLM tier (cost=%.0f)", llm_result.total_cost)
        return llm_result
    if llm_result is not None:
        logger.info("parser: LLM returned zero cost, falling back to regex")

    # Tier 2: Regex
    result = _regex_parse(prompt, baseline_balance, dataset_type)
    logger.info(
        "parser: used regex tier (cost=%.0f, floor=%.0f)",
        result.total_cost,
        result.emergency_floor,
    )

    if result.total_cost == 0.0 and "total_cost" in result.defaulted_fields:
        raise DecisionParseError(
            f"Could not parse a cost amount from prompt: '{prompt}'. "
            "Please include an amount like ₹60L, ₹1.2 lakh, or ₹30,000."
        )

    return result
