"""
FutureFork Dataset Loader & Financial Fixture Accessor
Member 1: Data Ingestion & Baseline Compiler

Provides clean, typed helper functions for the rest of the team:
- load_sample_csv_bytes(name: str) -> bytes
- load_sample_instance(name: str) -> FinancialProblemInstance
- load_fixture_json(path: str) -> dict
- list_sample_datasets() -> list of bundled sample CSV names
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure repository root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data.ingestor import (
    ColumnMapping,
    FinancialIngestor,
    FinancialProblemInstance,
)

DATA_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = DATA_DIR / "samples"


# ==============================================================================
# FINANCIAL DATASET HELPERS (MEMBER 1 NEW API)
# ==============================================================================

def _resolve_sample_path(name: Union[str, Path], default_ext: str = ".csv") -> Path:
    """Helper to resolve a sample file by name from data/samples/ or the repo root."""
    p_name = Path(name)
    clean_name = str(name).strip()
    base_name = p_name.name

    # Check direct file or root-relative file first
    if p_name.is_file():
        return p_name.resolve()
    if (ROOT_DIR / p_name).is_file():
        return (ROOT_DIR / p_name).resolve()

    candidate_names = [clean_name, base_name]
    if not clean_name.endswith(default_ext):
        candidate_names.append(f"{clean_name}{default_ext}")
    if not base_name.endswith(default_ext):
        candidate_names.append(f"{base_name}{default_ext}")

    seen = set()
    deduped = []
    for c in candidate_names:
        if c not in seen:
            seen.add(c)
            deduped.append(c)

    # Priority search locations
    for c_name in deduped:
        for parent in [Path("."), ROOT_DIR, SAMPLES_DIR, DATA_DIR]:
            p = (parent / c_name).resolve()
            if p.is_file():
                return p

    raise FileNotFoundError(
        f"Financial sample file '{name}' not found. Searched for candidates {deduped} in:\n"
        f" - {SAMPLES_DIR}\n"
        f" - {ROOT_DIR}"
    )


def load_sample_csv_bytes(name: str) -> bytes:
    """
    Loads raw bytes of a sample CSV file by name.
    Examples:
        load_sample_csv_bytes("personal_upi.csv")
        load_sample_csv_bytes("institute_erp_1.8cr")
        load_sample_csv_bytes("startup_pnl")
    """
    path = _resolve_sample_path(name, default_ext=".csv")
    return path.read_bytes()


def load_sample_instance(
    name: str,
    starting_balance: Optional[float] = None,
    mapping: Optional[Union[ColumnMapping, Dict[str, Any]]] = None,
) -> FinancialProblemInstance:
    """
    Compiles a named financial sample CSV into a FinancialProblemInstance.
    Examples:
        inst = load_sample_instance("institute_erp_1.8cr.csv")
        inst = load_sample_instance("personal_upi")
        inst = load_sample_instance("startup_pnl")
    """
    path = _resolve_sample_path(name, default_ext=".csv")
    dataset_id = path.stem

    # Use default preset mapping if not explicitly provided
    if mapping is None:
        if "institute" in dataset_id:
            mapping = ColumnMapping(
                date_col="Date",
                debit_col="Debit",
                credit_col="Credit",
                category_col="Account_Head",
                description_col="Narration",
                date_format="%d/%m/%Y",
                starting_balance=2500000.0 if starting_balance is None else starting_balance,
            )
        elif "personal" in dataset_id:
            mapping = ColumnMapping(
                date_col="Date",
                debit_col="Debit",
                credit_col="Credit",
                category_col="Category",
                description_col="Narration",
                starting_balance=150000.0 if starting_balance is None else starting_balance,
            )
        elif "startup" in dataset_id:
            mapping = ColumnMapping(
                date_col="Date",
                amount_col="Amount",
                category_col="Category",
                description_col="Description",
                type_col="Type",
                date_format="%Y-%m-%d",
                starting_balance=6000000.0 if starting_balance is None else starting_balance,
            )

    return FinancialIngestor.compile(
        csv_source=path,
        mapping=mapping,
        dataset_id=dataset_id,
        name=f"FutureFork Sample: {dataset_id}",
        starting_balance=starting_balance,
    )


def load_fixture_json(path_or_name: Union[str, Path] = "fixture_institute_node0.json") -> Dict[str, Any]:
    """
    Loads pre-parsed FinancialProblemInstance JSON fixture.
    Can be used by Members 2, 3, 4, 5 to immediately test without parsing CSVs.
    """
    if isinstance(path_or_name, str):
        path = _resolve_sample_path(path_or_name, default_ext=".json")
    else:
        path = path_or_name

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_sample_datasets() -> List[str]:
    """Returns list of all available financial sample CSV names."""
    samples = set()
    if SAMPLES_DIR.exists():
        for p in SAMPLES_DIR.glob("*.csv"):
            samples.add(p.name)
    return sorted(list(samples))
