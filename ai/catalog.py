"""
FutureFork AI Catalog (Member 4)
Financial decision schemas for FutureFork 2.0.

Provides:
  - BigPurchaseDecision: Pydantic model for a financial purchase decision.
  - FINANCIAL_CATALOG: dict mapping decision type name to schema metadata.
  - get_financial_catalog_summary() -> str
  - is_financial_decision(text: str) -> bool
  - lookup_decision_schema(name: str) -> dict
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# ==============================================================================
# FINANCIAL CATALOG (NEW)
# ==============================================================================


class BigPurchaseDecision(BaseModel):
    """
    Schema for a financial big-purchase decision.

    Fields:
        item_label: Human-readable name of the item (e.g. "GPU Lab PCs").
        quantity: Optional count of units (e.g. 40 PCs).
        total_amount_inr: Total cost in Indian Rupees.
        emergency_floor_inr: Minimum cash reserve not to drop below (INR).
        target_month: Intended purchase month index 0-11 (0 = immediate).
        financing_preference: "upfront" | "emi" | "phased" | "trim" | "auto".
        emi_months: Number of EMI installments (3, 6, 9, or 12).
        dataset_type: Source dataset type ("personal" | "institute" | "startup").
    """

    item_label: str
    quantity: Optional[int] = None
    total_amount_inr: float
    emergency_floor_inr: float = 0.0
    target_month: int = 0
    financing_preference: str = "auto"  # "upfront"|"emi"|"phased"|"trim"|"auto"
    emi_months: int = 6
    dataset_type: str = "personal"  # "personal"|"institute"|"startup"


FINANCIAL_CATALOG: Dict[str, Dict[str, Any]] = {
    "big_purchase": {
        "name": "Big Purchase Decision",
        "description": (
            "Evaluates the financial feasibility of a one-time large capital purchase "
            "(equipment, infrastructure, assets) across 4 financing strategies: "
            "Upfront, EMI, Phased, and Trim-and-Buy."
        ),
        "schema": BigPurchaseDecision.model_json_schema(),
        "examples": [
            {
                "item_label": "GPU Lab PCs",
                "quantity": 40,
                "total_amount_inr": 6000000,
                "emergency_floor_inr": 2500000,
                "target_month": 0,
                "financing_preference": "auto",
                "emi_months": 6,
                "dataset_type": "institute",
            },
            {
                "item_label": "Laptop",
                "total_amount_inr": 120000,
                "emergency_floor_inr": 30000,
                "target_month": 0,
                "financing_preference": "emi",
                "emi_months": 12,
                "dataset_type": "personal",
            },
        ],
        "keywords": [
            "buy", "purchase", "acquire", "invest", "spend", "laptop", "pc", "server",
            "equipment", "machinery", "vehicle", "infrastructure", "hire", "recruit",
            "cloud", "credits", "gpu", "salary", "annual cost",
        ],
        "parameters": {
            "item_label": {"type": "string", "required": True},
            "quantity": {"type": "integer", "required": False},
            "total_amount_inr": {"type": "float", "required": True},
            "emergency_floor_inr": {"type": "float", "required": False, "default": 0.0},
            "target_month": {"type": "integer", "required": False, "default": 0},
            "financing_preference": {
                "type": "string",
                "enum": ["upfront", "emi", "phased", "trim", "auto"],
                "required": False,
                "default": "auto",
            },
            "emi_months": {"type": "integer", "required": False, "default": 6},
            "dataset_type": {
                "type": "string",
                "enum": ["personal", "institute", "startup"],
                "required": False,
                "default": "personal",
            },
        },
    },
}


def get_financial_catalog_summary() -> str:
    """Returns a human-readable summary of supported financial decision types."""
    lines = ["Supported Financial Decision Types in FutureFork 2.0:"]
    for k, v in FINANCIAL_CATALOG.items():
        lines.append(f"- {k}: {v['description']}")
    return "\n".join(lines)


_FINANCIAL_KEYWORDS: List[str] = [
    "buy", "purchase", "acquire", "invest", "laptop", "pc", "server", "equipment",
    "machinery", "vehicle", "infrastructure", "hire", "recruit", "cloud", "gpu",
    "₹", "rs ", "inr", "lakh", "crore", "salary", "annual cost", "worth",
    "without dropping", "emergency", "reserve", "emi", "upfront", "phased", "trim",
]


def is_financial_decision(text: str) -> bool:
    """
    Returns True if the text looks like a financial purchase/investment decision.

    Args:
        text: Plain-English decision prompt.

    Returns:
        True if it appears to be a financial decision; False otherwise.
    """
    lower = text.lower()
    return any(kw in lower for kw in _FINANCIAL_KEYWORDS)


def lookup_decision_schema(name: str) -> Dict[str, Any]:
    """
    Looks up a financial decision schema by name (case-insensitive).

    Args:
        name: Decision type name (e.g. "big_purchase").

    Returns:
        Schema metadata dict. Raises KeyError if not found.
    """
    key = name.lower().strip()
    if key in FINANCIAL_CATALOG:
        return FINANCIAL_CATALOG[key]
    # Try partial match
    for k, v in FINANCIAL_CATALOG.items():
        if key in k or k in key:
            return v
    raise KeyError(f"Decision schema '{name}' not found in FINANCIAL_CATALOG. "
                   f"Available: {list(FINANCIAL_CATALOG.keys())}")
