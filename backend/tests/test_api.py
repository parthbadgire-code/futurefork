"""
FutureFork Backend Tests
Covers the full financial CSV pipeline against the real engine (no stubs):
  - Health / ping
  - POST /datasets/inspect  (CSV upload → ColumnMapping + preview)
  - POST /datasets/commit   (ingest + baseline Node 0)
  - POST /decisions         (parse financial prompt)
  - POST /decisions/{id}/scenarios
  - POST /decisions/{id}/run
  - GET  /runs/{id}
  - GET  /scenarios/{id}/result
  - GET  /decisions/{id}/compare
  - POST /scenarios/{id}/branch
  - 404 error cases
"""

import io
import sys
import time
from pathlib import Path

import pytest

# Ensure repo root is importable
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api import routes
from backend.db.repository import SessionLocal, init_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_session():
    init_db()
    db = SessionLocal()
    yield db
    db.close()


def _make_minimal_csv() -> bytes:
    """Minimal valid personal UPI CSV for testing."""
    lines = [
        "Date,Description,Category,Amount,Type",
        "2024-04-01,Rent Payment,Rent & Infrastructure,25000.00,outflow",
        "2024-04-05,Swiggy Food,Food & Dining,450.00,outflow",
        "2024-04-10,Salary Credit,Income,85000.00,inflow",
        "2024-04-15,Electricity Bill,Utilities & Bills,1200.00,outflow",
        "2024-04-20,Uber Ride,Travel & Transport,250.00,outflow",
        "2024-05-01,Rent Payment,Rent & Infrastructure,25000.00,outflow",
        "2024-05-10,Salary Credit,Income,85000.00,inflow",
        "2024-05-15,Electricity Bill,Utilities & Bills,1300.00,outflow",
        "2024-06-01,Rent Payment,Rent & Infrastructure,25000.00,outflow",
        "2024-06-10,Salary Credit,Income,85000.00,inflow",
        "2024-07-01,Rent Payment,Rent & Infrastructure,25000.00,outflow",
        "2024-07-10,Salary Credit,Income,85000.00,inflow",
        "2024-08-01,Rent Payment,Rent & Infrastructure,25000.00,outflow",
        "2024-08-10,Salary Credit,Income,85000.00,inflow",
        "2024-09-01,Rent Payment,Rent & Infrastructure,25000.00,outflow",
        "2024-09-10,Salary Credit,Income,85000.00,inflow",
        "2024-10-01,Rent Payment,Rent & Infrastructure,25000.00,outflow",
        "2024-10-10,Salary Credit,Income,85000.00,inflow",
        "2024-11-01,Rent Payment,Rent & Infrastructure,25000.00,outflow",
        "2024-11-10,Salary Credit,Income,85000.00,inflow",
        "2024-12-01,Rent Payment,Rent & Infrastructure,25000.00,outflow",
        "2024-12-10,Salary Credit,Income,85000.00,inflow",
        "2025-01-01,Rent Payment,Rent & Infrastructure,25000.00,outflow",
        "2025-01-10,Salary Credit,Income,85000.00,inflow",
        "2025-02-01,Rent Payment,Rent & Infrastructure,25000.00,outflow",
        "2025-02-10,Salary Credit,Income,85000.00,inflow",
        "2025-03-01,Rent Payment,Rent & Infrastructure,25000.00,outflow",
        "2025-03-10,Salary Credit,Income,85000.00,inflow",
    ]
    return "\n".join(lines).encode("utf-8")


# ---------------------------------------------------------------------------
# Health tests
# ---------------------------------------------------------------------------

def test_health_check():
    res = routes.health_check()
    assert res["status"] == "ok"
    assert "futurefork-backend" in res["service"]


def test_keep_warm_ping():
    res = routes.keep_warm_ping()
    assert res["ping"] == "pong"


# ---------------------------------------------------------------------------
# POST /datasets/inspect
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inspect_dataset_valid_csv(db_session):
    """Uploading a valid CSV returns upload_id + proposed_mapping + preview."""
    from fastapi import UploadFile

    csv_bytes = _make_minimal_csv()
    file = UploadFile(filename="personal_upi.csv", file=io.BytesIO(csv_bytes))

    res = await routes.inspect_dataset(file=file, db=db_session)

    assert "upload_id" in res
    assert res["upload_id"].startswith("upl_")
    assert "proposed_mapping" in res
    assert "preview_rows" in res
    assert isinstance(res["preview_rows"], list)
    assert 1 <= len(res["preview_rows"]) <= 5
    assert res["ttl_seconds"] == 900
    # Store for downstream tests
    test_inspect_dataset_valid_csv._upload_id = res["upload_id"]
    test_inspect_dataset_valid_csv._mapping = res["proposed_mapping"]


@pytest.mark.asyncio
async def test_inspect_dataset_empty_file(db_session):
    """Uploading an empty file returns 400."""
    from fastapi import UploadFile

    file = UploadFile(filename="empty.csv", file=io.BytesIO(b""))
    with pytest.raises(Exception) as exc_info:
        await routes.inspect_dataset(file=file, db=db_session)
    assert "EMPTY_FILE" in str(exc_info.value) or "400" in str(exc_info.value)


# ---------------------------------------------------------------------------
# POST /datasets/commit
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def committed_dataset_id(db_session):
    """Synchronously run inspect + commit and return dataset_id for reuse."""
    import asyncio

    from fastapi import UploadFile

    csv_bytes = _make_minimal_csv()
    file = UploadFile(filename="personal_upi.csv", file=io.BytesIO(csv_bytes))

    # Inspect
    loop = asyncio.new_event_loop()
    inspect_res = loop.run_until_complete(routes.inspect_dataset(file=file, db=db_session))
    loop.close()

    upload_id = inspect_res["upload_id"]
    mapping = inspect_res["proposed_mapping"]

    # Commit
    commit_req = routes.CommitRequest(
        upload_id=upload_id,
        confirmed_mapping=mapping,
        dataset_name="Test Personal UPI Dataset",
        starting_balance=50000.0,
    )
    commit_res = routes.commit_dataset(commit_req, db=db_session)
    return commit_res["dataset_id"]


def test_commit_returns_dataset_id(committed_dataset_id):
    assert committed_dataset_id is not None
    assert committed_dataset_id.startswith("ds_")


def test_commit_expired_upload_raises_404(db_session):
    """Using a non-existent upload_id raises 404."""
    req = routes.CommitRequest(
        upload_id="upl_nonexistent_xxxx",
        confirmed_mapping={},
    )
    with pytest.raises(Exception) as exc_info:
        routes.commit_dataset(req, db=db_session)
    assert "UPLOAD_NOT_FOUND" in str(exc_info.value) or "404" in str(exc_info.value)


# ---------------------------------------------------------------------------
# GET /datasets  &  GET /datasets/{id}
# ---------------------------------------------------------------------------

def test_list_datasets(committed_dataset_id, db_session):
    datasets = routes.list_datasets(db=db_session)
    ids = [d["id"] for d in datasets]
    assert committed_dataset_id in ids
    # Bundled sample CSVs are seeded at startup
    for sample_id in ("sample_personal", "sample_institute", "sample_startup"):
        assert sample_id in ids


def test_get_dataset(committed_dataset_id, db_session):
    ds = routes.get_dataset(committed_dataset_id, db=db_session)
    assert ds["id"] == committed_dataset_id
    assert ds["stats"]["months"] == 12
    assert "survival_score_pct" in ds["baseline_metrics"]
    assert "cash_out_risk_pct" in ds["baseline_metrics"]


def test_get_dataset_not_found(db_session):
    with pytest.raises(Exception) as exc_info:
        routes.get_dataset("ds_does_not_exist", db=db_session)
    assert "DATASET_NOT_FOUND" in str(exc_info.value) or "404" in str(exc_info.value)


# ---------------------------------------------------------------------------
# POST /decisions
# ---------------------------------------------------------------------------

LAPTOP_PROMPT = "Buy a ₹1.2L laptop on EMI without dropping below ₹30k emergency savings"
FORK_TYPES = {"upfront", "emi", "phased", "trim"}


def _wait_for_run(run_id: str, db_session, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    run = {}
    while time.time() < deadline:
        db_session.expire_all()
        run = routes.get_run_status(run_id, db=db_session)
        if run["overall_status"] in ("done", "failed"):
            return run
        time.sleep(0.2)
    raise AssertionError(f"Run {run_id} did not finish in {timeout}s: {run}")


@pytest.fixture(scope="module")
def decision_id(committed_dataset_id, db_session):
    req = routes.CreateDecisionRequest(text=LAPTOP_PROMPT, dataset_id=committed_dataset_id)
    return routes.create_decision(req, db=db_session)["id"]


def test_create_decision_parses_amounts(committed_dataset_id, db_session):
    req = routes.CreateDecisionRequest(text=LAPTOP_PROMPT, dataset_id=committed_dataset_id)
    spec = routes.create_decision(req, db=db_session)
    assert spec["id"].startswith("dec_")
    assert spec["status"] == "ok"
    assert spec["change"]["params"]["total_cost"] == 120000.0
    assert spec["change"]["params"]["emergency_floor"] == 30000.0


def test_create_decision_ids_are_unique(committed_dataset_id, db_session):
    req = routes.CreateDecisionRequest(text=LAPTOP_PROMPT, dataset_id=committed_dataset_id)
    a = routes.create_decision(req, db=db_session)["id"]
    b = routes.create_decision(req, db=db_session)["id"]
    assert a != b


def test_create_decision_without_amount_needs_clarification(committed_dataset_id, db_session):
    req = routes.CreateDecisionRequest(text="Should we buy something nice?", dataset_id=committed_dataset_id)
    spec = routes.create_decision(req, db=db_session)
    assert spec["status"] == "needs_clarification"
    assert spec["message"]
    # Forking an unclear decision is rejected rather than evaluated with made-up inputs
    with pytest.raises(Exception) as exc_info:
        routes.generate_scenarios_endpoint(spec["id"], db=db_session)
    assert "DECISION_NOT_READY" in str(exc_info.value)


def test_create_decision_dataset_not_found(db_session):
    req = routes.CreateDecisionRequest(text="Buy a laptop", dataset_id="ds_nonexistent")
    with pytest.raises(Exception) as exc_info:
        routes.create_decision(req, db=db_session)
    assert "DATASET_NOT_FOUND" in str(exc_info.value)


# ---------------------------------------------------------------------------
# POST /decisions/{id}/scenarios — baseline + 4 forks
# ---------------------------------------------------------------------------

def test_generate_scenarios(decision_id, db_session):
    scenarios = routes.generate_scenarios_endpoint(decision_id, db=db_session)
    types = [s["change"]["type"] for s in scenarios]
    assert types[0] == "baseline"
    assert set(types[1:]) == FORK_TYPES
    # Scenario ids are namespaced by decision so decisions never overwrite each other
    assert all(s["id"].startswith(decision_id) for s in scenarios)
    # The trim fork receives the real dataset (flexible categories resolved)
    trim = next(s for s in scenarios if s["change"]["type"] == "trim")
    assert trim["status"] == "queued"
    assert trim["change"]["params"]["flexible_categories"]


def test_generate_scenarios_decision_not_found(db_session):
    with pytest.raises(Exception) as exc_info:
        routes.generate_scenarios_endpoint("dec_nonexistent", db=db_session)
    assert "DECISION_NOT_FOUND" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Run → results → compare
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def finished_run(decision_id, db_session):
    run_id = routes.start_run(decision_id, db=db_session)["run_id"]
    return _wait_for_run(run_id, db_session)


def test_run_evaluates_every_fork(finished_run):
    assert finished_run["run_id"].startswith("run_")
    assert finished_run["overall_status"] == "done"
    assert set(finished_run["scenarios"].values()) == {"done"}
    assert len(finished_run["scenarios"]) == 5


def test_scenario_results_come_from_engine(decision_id, finished_run, db_session):
    for branch in ["baseline", *FORK_TYPES]:
        res = routes.get_scenario_result(f"{decision_id}_{branch}", db=db_session)
        assert res["branch_type"] == branch
        assert res["solver"]["solver"].startswith(("OR-Tools-CP-SAT", "Deterministic-Audit"))
        assert res["simulation"]["n_runs"] == 300
        assert len(res["simulation"]["monthly_balances"]) == 12
        assert len(res["cash_flow"]["months"]) == 12
        assert res["cash_flow"]["categories"]
        assert 0.0 <= res["metrics"]["survival_score_pct"] <= 100.0
    upfront = routes.get_scenario_result(f"{decision_id}_upfront", db=db_session)
    assert upfront["metrics"]["total_purchase_cost"] == 120000.0


def test_comparison_endpoint(decision_id, finished_run, db_session):
    comp = routes.get_decision_comparison(decision_id, db=db_session)
    assert comp["decision_id"] == decision_id
    assert len(comp["results"]) == 5
    assert comp["explanation"]["summary"]
    assert comp["explanation"]["guard_passed"] is True


def test_decisions_do_not_overwrite_each_other(committed_dataset_id, decision_id, finished_run, db_session):
    other = routes.create_decision(
        routes.CreateDecisionRequest(
            text="Buy a ₹40k phone without dropping below ₹20k savings",
            dataset_id=committed_dataset_id,
        ),
        db=db_session,
    )
    routes.generate_scenarios_endpoint(other["id"], db=db_session)
    _wait_for_run(routes.start_run(other["id"], db=db_session)["run_id"], db_session)

    first = routes.get_scenario_result(f"{decision_id}_upfront", db=db_session)
    second = routes.get_scenario_result(f"{other['id']}_upfront", db=db_session)
    assert first["metrics"]["total_purchase_cost"] == 120000.0
    assert second["metrics"]["total_purchase_cost"] == 40000.0
    assert len(routes.get_decision_comparison(decision_id, db=db_session)["results"]) == 5


def test_get_scenario_result_not_found(db_session):
    with pytest.raises(Exception) as exc_info:
        routes.get_scenario_result("dec_missing_baseline", db=db_session)
    assert "RESULT_NOT_FOUND" in str(exc_info.value)


# ---------------------------------------------------------------------------
# POST /scenarios/{id}/branch — user-defined child fork
# ---------------------------------------------------------------------------

def test_branch_scenario(decision_id, finished_run, db_session):
    parent_id = f"{decision_id}_baseline"
    req = routes.BranchScenarioRequest(
        name="Custom: 12-month EMI",
        change={"type": "emi", "params": {"emi_months": 12}},
    )
    child = routes.branch_scenario_endpoint(parent_id, req, db=db_session)
    assert child["parent_id"] == parent_id
    assert child["id"].startswith("branch_")
    assert child["status"] == "done"
    res = routes.get_scenario_result(child["id"], db=db_session)
    assert res["branch_type"] == "emi"
    assert res["metrics"]["total_financing_interest"] > 0


def test_branch_scenario_rejects_unknown_type(decision_id, finished_run, db_session):
    req = routes.BranchScenarioRequest(name="Bad", change={"type": "shift_time_window", "params": {}})
    with pytest.raises(Exception) as exc_info:
        routes.branch_scenario_endpoint(f"{decision_id}_baseline", req, db=db_session)
    assert "UNSUPPORTED_CHANGE" in str(exc_info.value)


def test_branch_scenario_parent_not_found(db_session):
    req = routes.BranchScenarioRequest(name="Orphan Branch", change={"type": "upfront", "params": {}})
    with pytest.raises(Exception) as exc_info:
        routes.branch_scenario_endpoint("scenario_nonexistent_xyz", req, db=db_session)
    assert "PARENT_NOT_FOUND" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Infeasible decision: forks fail honestly instead of showing placeholder numbers
# ---------------------------------------------------------------------------

def test_unaffordable_purchase_fails_forks_not_baseline(committed_dataset_id, db_session):
    # ₹60L against a ₹50k opening balance fails the fan-out sanity check (> 10x balance)
    dec = routes.create_decision(
        routes.CreateDecisionRequest(
            text="Buy a ₹60L GPU cluster on EMI without dropping below ₹25L reserve",
            dataset_id=committed_dataset_id,
        ),
        db=db_session,
    )
    scenarios = routes.generate_scenarios_endpoint(dec["id"], db=db_session)
    statuses = {s["change"]["type"]: s["status"] for s in scenarios}
    assert statuses["baseline"] == "queued"
    assert all(statuses[t] == "failed" for t in FORK_TYPES)

    run = _wait_for_run(routes.start_run(dec["id"], db=db_session)["run_id"], db_session)
    assert run["scenarios"][f"{dec['id']}_baseline"] == "done"
    comp = routes.get_decision_comparison(dec["id"], db=db_session)
    assert list(comp["results"]) == [f"{dec['id']}_baseline"]
