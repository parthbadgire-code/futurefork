"""
FutureFork Column Mapper Agent (Member 4)

Proposes a ColumnMapping from CSV headers + ≤3 sample rows.

Tier 1: LLM — sends ONLY headers + max 3 rows, validates mapped cols against
         real headers (case-insensitive), rejects hallucinated columns.
         1 retry on invalid JSON/hallucination, then falls to Tier 2.
Tier 2: Deterministic regex/heuristic fallback — always works offline.

Public API:
  propose_mapping(headers, sample_rows, dataset_type_hint=None) -> MappingResult

MappingResult is a dataclass with:
  mapping:       ColumnMapping
  confidence:    float  (0.0–1.0)
  dataset_type:  str    ("personal" | "institute" | "startup" | "unknown")
  tier_used:     str    ("llm" | "regex")
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from engine.model import ColumnMapping

logger = logging.getLogger("futurefork.ai.agents.mapper")

# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------


@dataclass
class MappingResult:
    """
    Result of propose_mapping().

    Attributes:
        mapping:       A ColumnMapping ready for FinancialIngestor.compile().
        confidence:    0.0–1.0 confidence score.
        dataset_type:  Detected dataset type string.
        tier_used:     "llm" or "regex".
    """

    mapping: ColumnMapping
    confidence: float
    dataset_type: str
    tier_used: str


# ---------------------------------------------------------------------------
# Heuristic helpers
# ---------------------------------------------------------------------------

_PERSONAL_HEADERS = {"date", "narration", "category", "debit", "credit", "balance"}
_INSTITUTE_HEADERS = {"voucher_no", "date", "account_head", "department", "narration", "debit", "credit"}
_STARTUP_HEADERS = {"date", "description", "category", "amount", "type"}


def _lower_set(headers: List[str]) -> Dict[str, str]:
    """Return {lowercase_header: original_header} mapping."""
    return {h.lower(): h for h in headers}


def _detect_dataset_type(headers: List[str]) -> str:
    """Detect dataset type from header set."""
    lower_hdrs = set(h.lower() for h in headers)

    # Score overlap with each known schema
    personal_score = len(lower_hdrs & _PERSONAL_HEADERS)
    institute_score = len(lower_hdrs & _INSTITUTE_HEADERS)
    startup_score = len(lower_hdrs & _STARTUP_HEADERS)

    # Distinct discriminators
    if "account_head" in lower_hdrs or "voucher_no" in lower_hdrs or "department" in lower_hdrs:
        return "institute"
    if "type" in lower_hdrs and "amount" in lower_hdrs and "description" in lower_hdrs:
        return "startup"
    if "narration" in lower_hdrs and "balance" in lower_hdrs:
        return "personal"

    # Fallback to max score
    scores = {"personal": personal_score, "institute": institute_score, "startup": startup_score}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "unknown"
    return best


def _regex_mapping(
    headers: List[str],
    dataset_type: str,
    dataset_type_hint: Optional[str],
) -> tuple[ColumnMapping, float]:
    """
    Build a ColumnMapping deterministically from headers.

    Returns:
        (ColumnMapping, confidence)  — confidence 0.0–1.0
    """
    hmap = _lower_set(headers)  # {lower: original}
    dtype = dataset_type_hint or dataset_type

    def pick(*candidates: str) -> Optional[str]:
        """Return the first candidate found in headers (case-insensitive)."""
        for c in candidates:
            orig = hmap.get(c.lower())
            if orig is not None:
                return orig
        return None

    # Date column
    date_col = pick("date", "txn_date", "transaction_date", "value_date") or headers[0]

    if dtype == "institute":
        mapping = ColumnMapping(
            date_col=date_col,
            amount_col=None,
            debit_col=pick("debit", "withdrawal", "expense"),
            credit_col=pick("credit", "deposit", "income"),
            category_col=pick("account_head", "account", "category"),
            description_col=pick("narration", "description", "particulars", "remarks"),
            type_col=None,
            date_format=pick("date_format") and None or "%d/%m/%Y",
            starting_balance=0.0,
        )
        confidence = 0.95 if pick("account_head") and pick("narration") else 0.75

    elif dtype == "startup":
        mapping = ColumnMapping(
            date_col=date_col,
            amount_col=pick("amount", "value"),
            debit_col=None,
            credit_col=None,
            category_col=pick("category", "account_head"),
            description_col=pick("description", "narration", "particulars"),
            type_col=pick("type", "txn_type", "transaction_type"),
            date_format=None,
            starting_balance=0.0,
        )
        confidence = 0.95 if pick("amount") and pick("type") else 0.70

    else:  # personal (default)
        mapping = ColumnMapping(
            date_col=date_col,
            amount_col=None,
            debit_col=pick("debit", "withdrawal", "expense"),
            credit_col=pick("credit", "deposit", "income"),
            category_col=pick("category", "account_head"),
            description_col=pick("narration", "description", "particulars"),
            type_col=None,
            date_format=None,
            starting_balance=0.0,
        )
        confidence = 0.95 if pick("debit") and pick("credit") else 0.70

    return mapping, confidence


# ---------------------------------------------------------------------------
# LLM-tier helpers
# ---------------------------------------------------------------------------

_LLM_SYSTEM_PROMPT = """You are a financial CSV column mapper.
Given CSV headers and sample rows, output a JSON object with these keys
(use null if column not applicable):
  date_col, amount_col, debit_col, credit_col, category_col, description_col, type_col, date_format

IMPORTANT: Every non-null value MUST be one of the exact CSV column header strings provided.
Do not invent column names. Output ONLY valid JSON, no explanation."""


def _call_llm_for_mapping(
    headers: List[str],
    sample_rows: List[Union[List[Any], Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """
    Calls the LLM for a column mapping suggestion.

    Returns:
        Parsed JSON dict or None if LLM unavailable / fails.
    """
    offline = os.environ.get("FUTUREFORK_OFFLINE", "").strip() in ("1", "true", "yes")
    if offline:
        logger.debug("FUTUREFORK_OFFLINE=1: skipping LLM tier in mapper.")
        return None

    # Build a compact prompt
    rows_to_send = sample_rows[:3]
    prompt_data = {
        "headers": headers,
        "sample_rows": rows_to_send,
    }
    prompt = f"CSV metadata:\n{json.dumps(prompt_data, default=str, indent=2)}"

    try:
        from pydantic import BaseModel

        from ai.llm import call_structured_llm

        class _MapSchema(BaseModel):
            date_col: Optional[str] = None
            amount_col: Optional[str] = None
            debit_col: Optional[str] = None
            credit_col: Optional[str] = None
            category_col: Optional[str] = None
            description_col: Optional[str] = None
            type_col: Optional[str] = None
            date_format: Optional[str] = None

        result = call_structured_llm(
            prompt=prompt,
            system_prompt=_LLM_SYSTEM_PROMPT,
            response_model=_MapSchema,
            fallback_generator=lambda: None,
            max_retries=1,
        )
        if result is None:
            return None
        return result.model_dump()
    except Exception as exc:
        logger.warning("LLM call for column mapping failed: %s", exc)
        return None


def _validate_llm_mapping(
    llm_dict: Dict[str, Any],
    headers: List[str],
) -> Optional[Dict[str, Any]]:
    """
    Validate LLM mapping by ensuring every non-None value exists in headers
    (case-insensitive). Reject hallucinated column names.

    Returns:
        Sanitised dict or None if too many hallucinations.
    """
    hmap_lower = {h.lower(): h for h in headers}
    cleaned: Dict[str, Any] = {}
    hallucinations = 0
    total_non_null = 0

    skip_fields = {"date_format"}

    for field, val in llm_dict.items():
        if field in skip_fields:
            cleaned[field] = val
            continue
        if val is None:
            cleaned[field] = None
            continue
        total_non_null += 1
        orig = hmap_lower.get(str(val).lower())
        if orig is not None:
            cleaned[field] = orig
        else:
            logger.warning(
                "LLM hallucinated column '%s' for field '%s' (not in headers). Dropping.",
                val,
                field,
            )
            cleaned[field] = None
            hallucinations += 1

    if total_non_null > 0 and hallucinations / total_non_null > 0.5:
        logger.warning(
            "Too many hallucinations (%d/%d). Rejecting LLM mapping entirely.",
            hallucinations,
            total_non_null,
        )
        return None

    return cleaned


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def propose_mapping(
    headers: List[str],
    sample_rows: List[Union[List[Any], Dict[str, Any]]],
    dataset_type_hint: Optional[str] = None,
) -> MappingResult:
    """
    Propose a ColumnMapping from CSV headers and up to 3 sample rows.

    Tier 1 (LLM): Send headers + ≤3 rows to the LLM. Validate response.
    Tier 2 (regex): Deterministic heuristic fallback.

    Args:
        headers:           List of CSV column header strings.
        sample_rows:       Up to 3 sample rows (list of lists or list of dicts).
        dataset_type_hint: Optional hint ("personal"|"institute"|"startup").

    Returns:
        MappingResult with mapping, confidence, dataset_type, tier_used.
    """
    if not headers:
        # Degenerate case
        return MappingResult(
            mapping=ColumnMapping(),
            confidence=0.0,
            dataset_type="unknown",
            tier_used="regex",
        )

    dataset_type = dataset_type_hint or _detect_dataset_type(headers)

    # ---- Tier 1: LLM -------------------------------------------------------
    llm_raw = _call_llm_for_mapping(headers, sample_rows)
    if llm_raw is not None:
        validated = _validate_llm_mapping(llm_raw, headers)
        if validated is not None:
            mapping = ColumnMapping(
                date_col=validated.get("date_col") or headers[0],
                amount_col=validated.get("amount_col"),
                debit_col=validated.get("debit_col"),
                credit_col=validated.get("credit_col"),
                category_col=validated.get("category_col"),
                description_col=validated.get("description_col"),
                type_col=validated.get("type_col"),
                date_format=validated.get("date_format"),
                starting_balance=0.0,
            )
            logger.info("mapper: used LLM tier (dataset_type=%s)", dataset_type)
            return MappingResult(
                mapping=mapping,
                confidence=0.88,
                dataset_type=dataset_type,
                tier_used="llm",
            )
        logger.info("mapper: LLM mapping validation failed, falling back to regex tier.")
    else:
        logger.debug("mapper: LLM unavailable or offline, using regex tier.")

    # ---- Tier 2: Regex/heuristic -------------------------------------------
    mapping, confidence = _regex_mapping(headers, dataset_type, dataset_type_hint)
    logger.info("mapper: used regex tier (dataset_type=%s, confidence=%.2f)", dataset_type, confidence)
    return MappingResult(
        mapping=mapping,
        confidence=confidence,
        dataset_type=dataset_type,
        tier_used="regex",
    )
