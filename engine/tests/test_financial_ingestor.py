"""
FutureFork Financial Ingestion & Baseline Compiler Unit Tests
Member 1: Data Ingestion & Baseline Compiler (data/)

Tests:
1. Generation of 3 sample CSVs + 1 pre-parsed JSON fixture (make_finance_samples.py).
2. Compilation into 12 Months x 8 Categories outflow matrix and 12-element inflow vector (ingestor.py).
3. Auto-tagging of Fixed vs. Flexible categories and Node 0 statistical parameters (mu, sigma).
4. Sub-200ms compilation latency SLA on all demo datasets.
5. Defensive parsing: encodings (utf-8-sig, latin-1), currency cleaner (INR, commas, parens), missing columns.
6. Loader accessor functions (loader.py).
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from data.ingestor import (
    ColumnMapping,
    FinancialIngestor,
    clean_currency_series,
    compile_financial_instance,
    tag_category,
)
from data.loader import (
    list_sample_datasets,
    load_fixture_json,
    load_sample_csv_bytes,
    load_sample_instance,
)
from data.make_finance_samples import main as generate_all_samples
from engine.model import FinancialProblemInstance


@pytest.fixture(scope="session", autouse=True)
def ensure_samples_generated():
    """Ensure sample CSVs and JSON fixture are generated before running tests."""
    generate_all_samples()


def test_make_finance_samples_generates_all_files():
    """Validates that make_finance_samples produces the required 3 CSVs + 1 JSON fixture."""
    samples_dir = Path("data/samples")
    assert (samples_dir / "personal_upi.csv").is_file(), "personal_upi.csv missing"
    assert (samples_dir / "institute_erp_1.8cr.csv").is_file(), "institute_erp_1.8cr.csv missing"
    assert (samples_dir / "startup_pnl.csv").is_file(), "startup_pnl.csv missing"
    assert (samples_dir / "fixture_institute_node0.json").is_file(), "fixture_institute_node0.json missing"

    # Verify non-trivial file sizes
    assert (samples_dir / "personal_upi.csv").stat().st_size > 1000
    assert (samples_dir / "institute_erp_1.8cr.csv").stat().st_size > 1000
    assert (samples_dir / "startup_pnl.csv").stat().st_size > 1000
    assert (samples_dir / "fixture_institute_node0.json").stat().st_size > 1000


def test_compile_personal_upi():
    """Tests compilation of individual bank / UPI statement CSV."""
    instance = load_sample_instance("personal_upi.csv")
    assert isinstance(instance, FinancialProblemInstance)

    # 1. 12 months x 8 categories
    assert len(instance.months) == 12
    assert len(instance.categories) == 8
    assert instance.outflow_matrix.shape == (12, 8)
    assert len(instance.inflows) == 12

    # 2. Category tagging
    for cat in instance.categories:
        assert cat in instance.category_types
        assert instance.category_types[cat] in ("fixed", "flexible")
        assert cat in instance.category_means
        assert cat in instance.category_stds
        assert instance.category_means[cat] >= 0.0
        assert instance.category_stds[cat] >= 0.0

    # 3. Numeric integrity: non-negative, no NaN, no Inf
    assert not np.isnan(instance.outflow_matrix).any()
    assert not np.isinf(instance.outflow_matrix).any()
    assert (instance.outflow_matrix >= 0.0).all()
    assert not np.isnan(instance.inflow_vector).any()
    assert (instance.inflow_vector >= 0.0).all()

    # 4. Summary metrics
    assert instance.summary["starting_balance"] == 150000.0
    assert instance.summary["total_inflow"] > 0
    assert instance.summary["total_outflow"] > 0
    assert len(instance.cash_balances) == 12


def test_compile_institute_erp():
    """Tests compilation of institute college ERP expense ledger (~1.8 Cr budget)."""
    instance = load_sample_instance("institute_erp_1.8cr.csv")
    assert isinstance(instance, FinancialProblemInstance)

    assert len(instance.months) == 12
    assert len(instance.categories) == 8
    assert instance.outflow_matrix.shape == (12, 8)
    assert len(instance.inflows) == 12

    # High-level budget check (~1.8 Cr)
    total_annual_outflow = sum(instance.total_outflows)
    assert 1.4e7 <= total_annual_outflow <= 2.6e7, f"Total outflow {total_annual_outflow} out of expected ~1.8 Cr range"

    # Fixed categories should include Payroll and Utilities
    fixed_cats = [cat for cat, t in instance.category_types.items() if t == "fixed"]
    assert any("Payroll" in c or "Salary" in c for c in fixed_cats)
    assert any("Utilities" in c or "Electricity" in c for c in fixed_cats)


def test_compile_startup_pnl():
    """Tests compilation of company P&L / Burn statement CSV."""
    instance = load_sample_instance("startup_pnl.csv")
    assert isinstance(instance, FinancialProblemInstance)

    assert len(instance.months) == 12
    assert len(instance.categories) == 8
    assert instance.outflow_matrix.shape == (12, 8)
    assert len(instance.inflows) == 12

    # Check runway calculation in summary
    assert "runway_months" in instance.summary
    assert instance.summary["starting_balance"] == 6000000.0


def test_compilation_latency_sla_under_200ms():
    """Verifies that compiling each of the 3 CSVs completes in strictly under 200ms."""
    csv_names = ["personal_upi.csv", "institute_erp_1.8cr.csv", "startup_pnl.csv"]

    for name in csv_names:
        raw_bytes = load_sample_csv_bytes(name)

        t0 = time.perf_counter()
        inst = compile_financial_instance(raw_bytes, dataset_id=name)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert inst is not None
        assert elapsed_ms < 200.0, f"Compilation latency SLA violated for {name}: {elapsed_ms:.2f}ms >= 200ms"


def test_clean_currency_series():
    """Tests vectorized currency parsing across Indian and international formats."""
    import pandas as pd

    dirty = pd.Series([
        "₹ 1,50,000.00",
        "Rs. 2,450.50",
        "$12,000",
        "(5,000.00)",  # Accounting parentheses negative
        " - ",
        "nan",
        None,
        450.75,
    ])
    cleaned = clean_currency_series(dirty)

    assert cleaned[0] == 150000.0
    assert cleaned[1] == 2450.50
    assert cleaned[2] == 12000.0
    assert cleaned[3] == -5000.0
    assert cleaned[4] == 0.0
    assert cleaned[5] == 0.0
    assert cleaned[6] == 0.0
    assert cleaned[7] == 450.75


def test_tag_category_keywords_and_variance():
    """Tests auto-tagging logic for fixed vs flexible classifications."""
    assert tag_category("Office Rent & Infrastructure") == "fixed"
    assert tag_category("Faculty & Core Payroll") == "fixed"
    assert tag_category("Campus Utilities & Power") == "fixed"
    assert tag_category("Term Loan EMI") == "fixed"

    assert tag_category("Academic Travel & Conferences") == "flexible"
    assert tag_category("Student Fests & Cultural Events") == "flexible"
    assert tag_category("Performance Marketing & Ads") == "flexible"
    assert tag_category("Food & Team Dining") == "flexible"

    # Variance heuristic: low CV (< 0.20) should tag as fixed even with ambiguous name
    stable_series = np.array([10000.0, 10050.0, 9980.0, 10020.0, 10010.0, 9990.0] * 2)
    assert tag_category("Custom Bucket", stable_series) == "fixed"

    # High variance CV (> 0.20) should tag as flexible
    volatile_series = np.array([1000.0, 8500.0, 200.0, 12000.0, 500.0, 9000.0] * 2)
    assert tag_category("Custom Bucket", volatile_series) == "flexible"


def test_loader_helpers():
    """Tests data.loader API methods."""
    # 1. load_sample_csv_bytes
    b = load_sample_csv_bytes("personal_upi.csv")
    assert isinstance(b, bytes)
    assert len(b) > 0

    # 2. load_fixture_json
    fixture = load_fixture_json("fixture_institute_node0.json")
    assert isinstance(fixture, dict)
    assert "outflows" in fixture
    assert "inflows" in fixture
    assert len(fixture["categories"]) == 8
    assert len(fixture["months"]) == 12

    # 3. list_sample_datasets
    datasets = list_sample_datasets()
    assert "personal_upi.csv" in datasets
    assert "institute_erp_1.8cr.csv" in datasets
    assert "startup_pnl.csv" in datasets


def test_defensive_encoding_and_malformed_csv():
    """Tests resilience to encodings, extra whitespace, and missing columns."""
    # CSV encoded in UTF-8 with BOM
    csv_content = (
        "\ufeffDate,Category,Debit,Credit\n"
        "2024-04-01, Rent , ₹ 50000.00 , 0.00\n"
        "2024-05-01, Rent , 50000.00 , \n"
        "2024-06-01, Marketing , 10000.00 , 0.00\n"
    ).encode("utf-8-sig")

    mapping = ColumnMapping(date_col="Date", category_col="Category", debit_col="Debit", credit_col="Credit")
    inst = FinancialIngestor.compile(csv_content, mapping=mapping)
    assert isinstance(inst, FinancialProblemInstance)
    assert len(inst.categories) == 8
    assert inst.outflow_matrix.shape == (12, 8)

    # Empty CSV should raise ValueError
    with pytest.raises(ValueError, match="CSV dataset is empty"):
        FinancialIngestor.compile(b"")


def test_mixed_date_separators_are_not_dropped():
    """A column mixing DD/MM/YYYY and DD-MM-YYYY must parse every row (regression)."""
    import pandas as pd

    from data.ingestor import parse_date_series

    parsed = parse_date_series(pd.Series(["28/04/2024", "18-07-2024", "02-04-2024", "05.06.2024"]))
    assert parsed.notna().all()
    assert [d.month for d in parsed] == [4, 7, 4, 6]


def test_personal_sample_keeps_all_salary_credits():
    """The personal sample has a monthly salary credit; none may be lost to date parsing."""
    from data.loader import load_sample_instance

    inst = load_sample_instance("personal_upi.csv")
    assert sum(inst.inflows) > 1_500_000  # 12 salary credits of ~₹1.45L each
