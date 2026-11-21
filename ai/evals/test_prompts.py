"""
FutureFork Financial Evaluation Benchmark Suite (Member 4)

6 financial test prompts covering personal, institute, and startup datasets.
Works both as:
  - pytest: pytest ai/evals/test_prompts.py -v
  - standalone: python ai/evals/test_prompts.py

FUTUREFORK_OFFLINE=1 must be set before import to disable LLM calls.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Always run offline for deterministic tests
os.environ.setdefault("FUTUREFORK_OFFLINE", "1")

# Ensure repo root on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ===========================================================================
# Imports (after path setup)
# ===========================================================================

from ai.agents.explainer import (
    _build_allowed_facts,
    explain_branches,
    run_numeric_guard,
)
from ai.agents.mapper import propose_mapping
from ai.agents.parser import ParsedDecision, parse_financial_decision, parse_indian_amount
from ai.agents.scenario import ForkSet, build_forks
from data.loader import load_sample_csv_bytes, load_sample_instance
from engine.model import ColumnMapping, PurchaseGoal, ScenarioEvaluationResult
from engine.solver import solve_all_financial_scenarios

# ===========================================================================
# Test prompt definitions
# ===========================================================================

TEST_PROMPTS = [
    # (id, prompt, csv_name, starting_balance, dataset_type, expected)
    {
        "id": "P1",
        "label": "Personal laptop EMI",
        "prompt": "Buy a ₹1.2L laptop on EMI without dropping below ₹30k emergency savings",
        "csv_name": "personal_upi.csv",
        "starting_balance": 150000.0,
        "dataset_type": "personal",
        "expected": {
            "total_cost": 120000.0,
            "emergency_floor": 30000.0,
            "financing_preference": "emi",
            "quantity": None,
        },
    },
    {
        "id": "P2",
        "label": "Personal smartphone upfront",
        "prompt": "Buy a ₹45k smartphone upfront without dropping below ₹25k reserve",
        "csv_name": "personal_upi.csv",
        "starting_balance": 150000.0,
        "dataset_type": "personal",
        "expected": {
            "total_cost": 45000.0,
            "emergency_floor": 25000.0,
            "financing_preference": "upfront",
            "quantity": None,
        },
    },
    {
        "id": "I1",
        "label": "Institute 40 GPU PCs",
        "prompt": "Buy 40 GPU lab PCs for ₹60L without dropping below ₹25L reserve",
        "csv_name": "institute_erp_1.8cr.csv",
        "starting_balance": 2500000.0,
        "dataset_type": "institute",
        "expected": {
            "total_cost": 6000000.0,
            "emergency_floor": 2500000.0,
            "quantity": 40,
        },
    },
    {
        "id": "I2",
        "label": "Institute generator",
        "prompt": "Purchase lab generator replacement for ₹8L without dropping below ₹10L reserve",
        "csv_name": "institute_erp_1.8cr.csv",
        "starting_balance": 2500000.0,
        "dataset_type": "institute",
        "expected": {
            "total_cost": 800000.0,
            "emergency_floor": 1000000.0,
            "quantity": None,
        },
    },
    {
        "id": "S1",
        "label": "Startup GPU cloud credits",
        "prompt": "Buy GPU cloud credits worth ₹5L without dropping below ₹3L reserve",
        "csv_name": "startup_pnl.csv",
        "starting_balance": 6000000.0,
        "dataset_type": "startup",
        "expected": {
            "total_cost": 500000.0,
            "emergency_floor": 300000.0,
            "quantity": None,
        },
    },
    {
        "id": "S2",
        "label": "Startup 2 engineers",
        "prompt": "Hire 2 engineers for ₹18L annual cost without dropping below ₹5L reserve",
        "csv_name": "startup_pnl.csv",
        "starting_balance": 6000000.0,
        "dataset_type": "startup",
        "expected": {
            "total_cost": 1800000.0,
            "emergency_floor": 500000.0,
            "quantity": 2,
        },
    },
]

# CSV headers for each dataset type (used in mapper tests)
_PERSONAL_HEADERS = ["Date", "Narration", "Category", "Debit", "Credit", "Balance"]
_INSTITUTE_HEADERS = ["Voucher_No", "Date", "Account_Head", "Department", "Narration", "Debit", "Credit"]
_STARTUP_HEADERS = ["Date", "Description", "Category", "Amount", "Type"]

# ===========================================================================
# Helper: load baseline instance
# ===========================================================================


def _load_baseline(csv_name: str, starting_balance: float, dataset_type: str) -> Any:
    """Load a FinancialProblemInstance for the given CSV."""
    # Determine mapping from dataset type
    if dataset_type == "institute":
        mapping = ColumnMapping(
            date_col="Date",
            debit_col="Debit",
            credit_col="Credit",
            category_col="Account_Head",
            description_col="Narration",
            date_format="%d/%m/%Y",
            starting_balance=starting_balance,
        )
    elif dataset_type == "startup":
        mapping = ColumnMapping(
            date_col="Date",
            amount_col="Amount",
            category_col="Category",
            description_col="Description",
            type_col="Type",
            date_format="%Y-%m-%d",
            starting_balance=starting_balance,
        )
    else:  # personal
        mapping = ColumnMapping(
            date_col="Date",
            debit_col="Debit",
            credit_col="Credit",
            category_col="Category",
            description_col="Narration",
            starting_balance=starting_balance,
        )
    return load_sample_instance(csv_name, starting_balance=starting_balance, mapping=mapping)


# ===========================================================================
# Full-pipeline test runner
# ===========================================================================


def run_prompt_test(tc: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Run all assertions for a single test prompt.

    Returns:
        (passed: bool, messages: list[str])
    """
    failures: List[str] = []
    prompt = tc["prompt"]
    csv_name = tc["csv_name"]
    starting_balance = tc["starting_balance"]
    dataset_type = tc["dataset_type"]
    expected = tc["expected"]

    # --- (a) Mapper returns valid ColumnMapping ---
    try:
        csv_bytes = load_sample_csv_bytes(csv_name)
        csv_text = csv_bytes.decode("utf-8", errors="replace")
        # Parse headers from first line
        first_line = csv_text.split("\n")[0].strip()
        headers = [h.strip() for h in first_line.split(",")]
        sample_lines = [line for line in csv_text.split("\n")[1:4] if line.strip()]
        sample_rows = [[v.strip() for v in line.split(",")] for line in sample_lines]

        mapper_result = propose_mapping(headers, sample_rows, dataset_type_hint=dataset_type)
        assert isinstance(mapper_result.mapping, ColumnMapping), "mapper did not return ColumnMapping"
        assert mapper_result.mapping.date_col, "mapper: date_col is empty"

        # Verify ingestor accepts the mapping
        baseline = _load_baseline(csv_name, starting_balance, dataset_type)
        assert baseline is not None, "Failed to load baseline instance"
        assert len(baseline.months) == 12, f"Expected 12 months, got {len(baseline.months)}"
    except Exception as exc:
        failures.append(f"(a) Mapper/Ingestor: {exc}")
        baseline = None

    if baseline is None:
        try:
            baseline = _load_baseline(csv_name, starting_balance, dataset_type)
        except Exception as exc:
            failures.append(f"(a) Fallback baseline load: {exc}")
            return False, failures

    # --- (b) Parser extracts correct fields ---
    try:
        parsed = parse_financial_decision(prompt, baseline=baseline, dataset_type=dataset_type)
        assert isinstance(parsed, ParsedDecision), "parser did not return ParsedDecision"

        exp_cost = expected["total_cost"]
        exp_floor = expected["emergency_floor"]

        cost_ok = abs(parsed.total_cost - exp_cost) / max(exp_cost, 1.0) < 0.02
        if not cost_ok:
            failures.append(f"(b) total_cost={parsed.total_cost:.0f}, expected={exp_cost:.0f}")

        floor_ok = abs(parsed.emergency_floor - exp_floor) / max(exp_floor, 1.0) < 0.02
        if not floor_ok:
            failures.append(f"(b) emergency_floor={parsed.emergency_floor:.0f}, expected={exp_floor:.0f}")

        exp_qty = expected.get("quantity")
        if exp_qty is not None:
            if parsed.quantity != exp_qty:
                failures.append(f"(b) quantity={parsed.quantity}, expected={exp_qty}")

        exp_fin = expected.get("financing_preference")
        if exp_fin is not None:
            if parsed.financing_preference != exp_fin:
                failures.append(f"(b) financing_preference={parsed.financing_preference!r}, expected={exp_fin!r}")

    except Exception as exc:
        failures.append(f"(b) Parser: {exc}")
        parsed = None

    if parsed is None:
        return False, failures

    # --- (c) Exactly 4 forks with correct ids ---
    try:
        fork_set = build_forks(prompt, baseline=baseline, dataset_type=dataset_type)
        assert isinstance(fork_set, ForkSet), "build_forks did not return ForkSet"
        assert len(fork_set.forks) == 4, f"Expected 4 forks, got {len(fork_set.forks)}"
        fork_ids = [f.fork_id for f in fork_set.forks]
        for expected_id in ["upfront", "emi", "phased", "trim"]:
            if expected_id not in fork_ids:
                failures.append(f"(c) Missing fork id: {expected_id!r}")
        if fork_ids != ["upfront", "emi", "phased", "trim"]:
            failures.append(f"(c) Fork order wrong: {fork_ids}")
    except Exception as exc:
        failures.append(f"(c) ForkSet: {exc}")
        fork_set = None

    if fork_set is None:
        return False, failures

    # --- (d) Solve scenarios and check result keys ---
    try:
        # Use the parsed decision to build a PurchaseGoal for the solver
        goal = PurchaseGoal(
            item_name=parsed.item_label,
            total_cost=parsed.total_cost,
            emergency_floor=parsed.emergency_floor,
            target_month=parsed.target_month,
            financing_mode="auto",
            emi_months=parsed.emi_months,
        )
        branch_results = solve_all_financial_scenarios(
            baseline,
            goal,
            run_monte_carlo=True,
            n_sims=50,  # small for speed
            seed=42,
        )

        required_keys = {"survival_score_pct", "cash_out_risk_pct", "lowest_balance", "p10_lowest_balance"}
        for scenario_id, result in branch_results.items():
            if scenario_id == "baseline":
                continue
            metrics = result.metrics if hasattr(result, "metrics") else {}
            sim = result.simulation_results if hasattr(result, "simulation_results") else {}
            # Check required keys across metrics + simulation_results
            combined = {**metrics, **(sim or {})}
            for k in required_keys:
                if k not in combined:
                    failures.append(f"(d) {scenario_id}: missing key {k!r}")

    except Exception as exc:
        failures.append(f"(d) Solver: {exc}")
        branch_results = None

    if branch_results is None:
        return False, failures

    # Build branch results subset (non-baseline)
    fork_branch_results = {k: v for k, v in branch_results.items() if k != "baseline"}

    # --- (e) Explainer output passes NumericGuard with 0 violations ---
    try:
        explanation = explain_branches(
            decision=parsed,
            branch_results=fork_branch_results,
            baseline=baseline,
        )
        guard = explanation.guard_report
        if not guard.passed:
            violations_summary = [(v.offending_text, v.kind) for v in guard.violations]
            failures.append(
                f"(e) NumericGuard: {len(guard.violations)} violation(s): {violations_summary}"
            )
    except Exception as exc:
        failures.append(f"(e) Explainer: {exc}")

    return len(failures) == 0, failures


# ===========================================================================
# Unit tests (also run under pytest)
# ===========================================================================


def test_indian_amount_parser() -> None:
    """Verify parse_indian_amount handles all Indian number formats."""
    cases = [
        ("₹60L", 6_000_000.0),
        ("₹1.8Cr", 18_000_000.0),
        ("30k", 30_000.0),
        ("₹1.2L", 120_000.0),
        ("60,00,000", 6_000_000.0),
        ("1.8 crore", 18_000_000.0),
        ("1.2 lakh", 120_000.0),
        ("₹25L", 2_500_000.0),
        ("Rs 1.2L", 120_000.0),
    ]
    for text, expected_rupees in cases:
        result = parse_indian_amount(text)
        assert result is not None, f"parse_indian_amount({text!r}) returned None"
        assert abs(result - expected_rupees) < 1.0, (
            f"parse_indian_amount({text!r}) = {result}, expected {expected_rupees}"
        )

    # Test percent is not parsed as rupees (should work without multiplier confusion)
    # 12.5% → parse_indian_amount should still return 12.5 (no multiplier)
    pct_result = parse_indian_amount("12.5%")
    assert pct_result is not None and abs(pct_result - 12.5) < 0.01, (
        f"parse_indian_amount('12.5%') = {pct_result}"
    )


def test_numeric_guard_violations() -> None:
    """
    Craft an explanation with fabricated ₹99L, 42%, Month 11 → guard must flag all 3.
    """
    # Build a minimal branch_results with known values (survival=75%, lowest_balance=50000)
    from engine.model import MonthlyCashSchedule, ScenarioEvaluationResult

    # Build dummy schedules
    dummy_schedules = [
        MonthlyCashSchedule(
            month_idx=i,
            month_str=f"2024-{i+1:02d}",
            inflow=10000.0,
            base_outflow=8000.0,
            trimmed_outflow=8000.0,
            purchase_cash_out=0.0,
            net_cash_flow=2000.0,
            closing_balance=50000.0 + i * 2000,
            emergency_floor=30000.0,
            is_below_floor=False,
            floor_breach_amount=0.0,
        )
        for i in range(12)
    ]

    dummy_result = ScenarioEvaluationResult(
        scenario_id="upfront",
        scenario_name="Upfront",
        description="Test",
        branch_type="upfront",
        is_feasible=True,
        purchase_month=0,
        total_purchase_cost=120000.0,
        total_financing_interest=0.0,
        total_trims_saved=0.0,
        monthly_schedules=dummy_schedules,
        category_trims={},
        metrics={
            "survival_score_pct": 75.0,
            "cash_out_risk_pct": 5.0,
            "lowest_balance": 50000.0,
            "p10_lowest_balance": 40000.0,
            "emergency_floor": 30000.0,
        },
        simulation_results=None,
    )

    branch_results = {"upfront": dummy_result}

    # Fabricated text with invalid numbers
    bad_text = "The lowest balance is ₹99L which is 42% safe. Buy in Month 11."
    allowed_money, allowed_pcts, allowed_months = _build_allowed_facts(branch_results, None)
    allowed_months.update({0, 1, 2, 3, 4, 6, 9, 10, 12})

    report = run_numeric_guard(bad_text, allowed_money, allowed_pcts, allowed_months)

    assert not report.passed, "Guard should have FAILED on fabricated text"
    violation_kinds = [v.kind for v in report.violations]
    assert "money" in violation_kinds, f"Expected money violation, got: {violation_kinds}"
    assert "percent" in violation_kinds, f"Expected percent violation, got: {violation_kinds}"
    assert "month" in violation_kinds, f"Expected month violation, got: {violation_kinds}"


def test_numeric_guard_pass() -> None:
    """
    Template explanation from real branch_results must pass with 0 violations.
    """
    from ai.agents.explainer import _build_template_explanation
    from ai.agents.parser import ParsedDecision
    from engine.model import MonthlyCashSchedule, ScenarioEvaluationResult

    # Build a realistic set of branch_results
    def _make_result(fid: str, survival: float, risk: float, lb: float) -> ScenarioEvaluationResult:
        schedules = [
            MonthlyCashSchedule(
                month_idx=i,
                month_str=f"2024-{i+1:02d}",
                inflow=50000.0,
                base_outflow=40000.0,
                trimmed_outflow=40000.0,
                purchase_cash_out=10000.0 if i == 0 else 0.0,
                net_cash_flow=0.0,
                closing_balance=lb + i * 5000,
                emergency_floor=25000.0,
                is_below_floor=lb < 25000.0,
                floor_breach_amount=max(0.0, 25000.0 - lb),
            )
            for i in range(12)
        ]
        return ScenarioEvaluationResult(
            scenario_id=fid,
            scenario_name=fid.title(),
            description=f"{fid} branch",
            branch_type=fid,
            is_feasible=True,
            purchase_month=0,
            total_purchase_cost=120000.0,
            total_financing_interest=0.0,
            total_trims_saved=0.0,
            monthly_schedules=schedules,
            category_trims={},
            metrics={
                "survival_score_pct": survival,
                "cash_out_risk_pct": risk,
                "lowest_balance": lb,
                "p10_lowest_balance": lb * 0.9,
                "emergency_floor": 25000.0,
                "total_purchase_cost": 120000.0,
            },
            simulation_results={
                "cash_out_risk_pct": risk,
                "p10_lowest_balance": lb * 0.9,
                "survival_score_pct": survival,
            },
        )

    branch_results = {
        "upfront": _make_result("upfront", 82.0, 3.0, 55000.0),
        "emi": _make_result("emi", 90.0, 1.5, 70000.0),
        "phased": _make_result("phased", 87.0, 2.0, 62000.0),
        "trim": _make_result("trim", 85.0, 2.5, 58000.0),
    }

    decision = ParsedDecision(
        item_label="Laptop",
        total_cost=120000.0,
        emergency_floor=25000.0,
        quantity=None,
        target_month=0,
        financing_preference="emi",
        emi_months=12,
        dataset_type="personal",
        raw_prompt="Buy a ₹1.2L laptop on EMI without dropping below ₹25k reserve",
        defaulted_fields=[],
    )

    allowed_money, allowed_pcts, allowed_months = _build_allowed_facts(branch_results, decision)
    allowed_months.update({0, 1, 2, 3, 4, 6, 9, 10, 12})

    template_text = _build_template_explanation(
        decision, branch_results, allowed_money, allowed_pcts, allowed_months
    )

    report = run_numeric_guard(template_text, allowed_money, allowed_pcts, allowed_months)
    assert report.passed, (
        f"Template explanation FAILED guard with {len(report.violations)} violation(s):\n"
        + "\n".join(f"  {v.offending_text!r} ({v.kind})" for v in report.violations)
        + f"\n\nTemplate text:\n{template_text}"
    )


def test_mapper_hallucination_rejection() -> None:
    """If LLM returns a column not in headers, it's rejected and regex is used."""
    from ai.agents.mapper import _validate_llm_mapping

    headers = ["Date", "Narration", "Category", "Debit", "Credit", "Balance"]
    # Simulate LLM returning hallucinated columns
    llm_dict = {
        "date_col": "Date",          # valid
        "amount_col": "Amount",      # HALLUCINATED — not in headers
        "debit_col": "Withdrawal",   # HALLUCINATED
        "credit_col": "Credit",      # valid
        "category_col": "Category",  # valid
        "description_col": "Narration",  # valid
        "type_col": "TxnType",       # HALLUCINATED
        "date_format": None,
    }

    result = _validate_llm_mapping(llm_dict, headers)
    # With 3 hallucinations out of 7 non-null — 3/7 ≈ 43% < 50%, so it won't be entirely rejected
    # But the hallucinated columns should be set to None
    if result is not None:
        assert result.get("amount_col") is None, "Hallucinated amount_col should be None"
        assert result.get("debit_col") is None, "Hallucinated debit_col should be None"
        assert result.get("type_col") is None, "Hallucinated type_col should be None"
        assert result.get("date_col") == "Date", "Valid date_col should be preserved"
        assert result.get("credit_col") == "Credit", "Valid credit_col should be preserved"

    # Now test total rejection: >50% hallucinated
    llm_dict_bad = {
        "date_col": "FakeDate",          # HALLUCINATED
        "amount_col": "FakeAmount",      # HALLUCINATED
        "debit_col": "FakeDebit",        # HALLUCINATED
        "credit_col": "FakeCredit",      # HALLUCINATED
        "category_col": "Category",     # valid
        "description_col": "Narration", # valid
        "type_col": None,
        "date_format": None,
    }
    result_bad = _validate_llm_mapping(llm_dict_bad, headers)
    assert result_bad is None, "Should reject mapping with >50% hallucinations"


def test_mapper_regex_fallback_personal() -> None:
    """Regex fallback on personal_upi.csv headers returns correct mapping."""
    from ai.agents.mapper import propose_mapping

    headers = _PERSONAL_HEADERS
    result = propose_mapping(headers, [], dataset_type_hint="personal")

    assert result.tier_used == "regex", f"Expected 'regex', got {result.tier_used!r}"
    assert result.dataset_type == "personal"
    assert result.mapping.date_col == "Date"
    assert result.mapping.debit_col == "Debit"
    assert result.mapping.credit_col == "Credit"
    assert result.mapping.category_col == "Category"
    assert result.mapping.description_col == "Narration"
    assert result.confidence >= 0.7


def test_mapper_regex_fallback_institute() -> None:
    """Regex fallback on institute ERP headers returns correct mapping."""
    from ai.agents.mapper import propose_mapping

    headers = _INSTITUTE_HEADERS
    result = propose_mapping(headers, [], dataset_type_hint="institute")

    assert result.tier_used == "regex", f"Expected 'regex', got {result.tier_used!r}"
    assert result.dataset_type == "institute"
    assert result.mapping.date_col == "Date"
    assert result.mapping.debit_col == "Debit"
    assert result.mapping.credit_col == "Credit"
    assert result.mapping.category_col == "Account_Head"
    assert result.mapping.description_col == "Narration"
    assert result.confidence >= 0.7


def test_mapper_regex_fallback_startup() -> None:
    """Regex fallback on startup P&L headers returns correct mapping."""
    from ai.agents.mapper import propose_mapping

    headers = _STARTUP_HEADERS
    result = propose_mapping(headers, [], dataset_type_hint="startup")

    assert result.tier_used == "regex", f"Expected 'regex', got {result.tier_used!r}"
    assert result.dataset_type == "startup"
    assert result.mapping.date_col == "Date"
    assert result.mapping.amount_col == "Amount"
    assert result.mapping.category_col == "Category"
    assert result.mapping.description_col == "Description"
    assert result.mapping.type_col == "Type"
    assert result.confidence >= 0.7


# Collect all unit tests
UNIT_TESTS = [
    ("test_indian_amount_parser", test_indian_amount_parser),
    ("test_numeric_guard_violations", test_numeric_guard_violations),
    ("test_numeric_guard_pass", test_numeric_guard_pass),
    ("test_mapper_hallucination_rejection", test_mapper_hallucination_rejection),
    ("test_mapper_regex_fallback_personal", test_mapper_regex_fallback_personal),
    ("test_mapper_regex_fallback_institute", test_mapper_regex_fallback_institute),
    ("test_mapper_regex_fallback_startup", test_mapper_regex_fallback_startup),
]

# ===========================================================================
# __main__ runner: PASS/FAIL table + pipeline tests
# ===========================================================================


def _run_unit_tests() -> Tuple[int, int]:
    """Run all unit tests. Returns (passed, total)."""
    passed = 0
    total = len(UNIT_TESTS)
    print("\n" + "=" * 70)
    print("UNIT TESTS")
    print("=" * 70)
    for name, fn in UNIT_TESTS:
        try:
            fn()
            print(f"  ✓  {name}")
            passed += 1
        except Exception as exc:
            print(f"  ✗  {name}")
            print(f"       {exc}")
            if os.environ.get("FUTUREFORK_VERBOSE_TESTS"):
                traceback.print_exc()
    return passed, total


def _run_pipeline_tests() -> Tuple[int, int]:
    """Run all 6 pipeline prompt tests. Returns (passed, total)."""
    passed = 0
    total = len(TEST_PROMPTS)
    print("\n" + "=" * 70)
    print("PIPELINE TESTS (6 Financial Prompts)")
    print("=" * 70)

    for tc in TEST_PROMPTS:
        tid = tc["id"]
        label = tc["label"]
        try:
            ok, failures = run_prompt_test(tc)
        except Exception as exc:
            ok = False
            failures = [f"Unexpected exception: {exc}"]
            if os.environ.get("FUTUREFORK_VERBOSE_TESTS"):
                traceback.print_exc()

        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {status}  [{tid}] {label}")
        if not ok:
            for f in failures:
                print(f"         → {f}")
        else:
            passed += 1

    return passed, total


def main() -> int:
    """Main entry point for standalone execution."""
    print("\n" + "=" * 70)
    print("FutureFork Financial Eval Suite  (FUTUREFORK_OFFLINE=1)")
    print("=" * 70)

    u_passed, u_total = _run_unit_tests()
    p_passed, p_total = _run_pipeline_tests()

    total_passed = u_passed + p_passed
    total_tests = u_total + p_total

    print("\n" + "=" * 70)
    print(f"SUMMARY: {total_passed}/{total_tests} passed")
    print(f"  Unit tests:     {u_passed}/{u_total}")
    print(f"  Pipeline tests: {p_passed}/{p_total}")
    print("=" * 70)

    if total_passed == total_tests:
        print("✓ ALL TESTS PASSED — 100% pass rate, 0 NumericGuard violations")
        return 0
    else:
        print(f"✗ {total_tests - total_passed} TEST(S) FAILED")
        return 1


# ===========================================================================
# pytest-compatible test functions (auto-discovered)
# ===========================================================================


def test_p1_personal_laptop_emi():
    ok, failures = run_prompt_test(TEST_PROMPTS[0])
    assert ok, "P1 failures:\n" + "\n".join(failures)


def test_p2_personal_smartphone_upfront():
    ok, failures = run_prompt_test(TEST_PROMPTS[1])
    assert ok, "P2 failures:\n" + "\n".join(failures)


def test_i1_institute_gpu_pcs():
    ok, failures = run_prompt_test(TEST_PROMPTS[2])
    assert ok, "I1 failures:\n" + "\n".join(failures)


def test_i2_institute_generator():
    ok, failures = run_prompt_test(TEST_PROMPTS[3])
    assert ok, "I2 failures:\n" + "\n".join(failures)


def test_s1_startup_gpu_credits():
    ok, failures = run_prompt_test(TEST_PROMPTS[4])
    assert ok, "S1 failures:\n" + "\n".join(failures)


def test_s2_startup_engineers():
    ok, failures = run_prompt_test(TEST_PROMPTS[5])
    assert ok, "S2 failures:\n" + "\n".join(failures)


if __name__ == "__main__":
    sys.exit(main())
