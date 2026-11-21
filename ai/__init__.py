"""FutureFork AI layer: CSV column mapping, decision parsing, 4-fork scenario
fan-out, and explanations checked by the Numeric Guard.

The AI layer interprets and explains. It never computes or changes a number
shown to the user; every metric comes from the engine.
"""

from ai.agents.explainer import ExplanationResult, explain_branches
from ai.agents.mapper import MappingResult, propose_mapping
from ai.agents.parser import ParsedDecision, parse_financial_decision, parse_indian_amount
from ai.agents.scenario import ForkSet, ForkSpec, build_forks
from ai.catalog import (
    FINANCIAL_CATALOG,
    BigPurchaseDecision,
    get_financial_catalog_summary,
    is_financial_decision,
    lookup_decision_schema,
)

__all__ = [
    # Catalog
    "FINANCIAL_CATALOG",
    "BigPurchaseDecision",
    "get_financial_catalog_summary",
    "is_financial_decision",
    "lookup_decision_schema",
    # Mapper
    "propose_mapping",
    "MappingResult",
    # Parser
    "parse_financial_decision",
    "ParsedDecision",
    "parse_indian_amount",
    # Scenario
    "build_forks",
    "ForkSet",
    "ForkSpec",
    # Explainer
    "explain_branches",
    "ExplanationResult",
]
