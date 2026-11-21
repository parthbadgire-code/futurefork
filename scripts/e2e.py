"""
FutureFork End-to-End CLI Test
Full pipeline: Upload CSV → Inspect → Commit Node 0 → Prompt Decision → 4 Branches → Compare

Usage:
  python scripts/e2e.py                    # In-process (sandboxed, no server needed)
  python scripts/e2e.py --url http://...   # Against a live deployed API
  python scripts/e2e.py --csv path/to.csv  # Use your own CSV

Done-condition: script exits with code 0 and prints "X PASSED, 0 FAILED".
"""

import argparse
import asyncio
import io
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# In-process mode: use a throwaway database (never the developer's ./futurefork.db)
if "--url" not in sys.argv and "DATABASE_URL" not in os.environ:
    import tempfile
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp(prefix='futurefork-e2e-')) / 'e2e.db'}"

from backend.api import routes
from backend.db.repository import SessionLocal, init_db

# ---------------------------------------------------------------------------
# Demo financial prompts  (3 user types)
# ---------------------------------------------------------------------------
PERSONAL_PROMPTS = [
    "Buy a ₹1.2L laptop on 12-month EMI without dropping below ₹30k emergency savings",
    "Take a ₹2L vacation without dropping below ₹50k reserve",
]
INSTITUTE_PROMPTS = [
    "Buy 40 GPU lab PCs for ₹60L without dropping below ₹25L treasury reserve",
    "Upgrade server infrastructure for ₹18L over next quarter without touching salary fund",
]
STARTUP_PROMPTS = [
    "Hire 2 senior engineers at ₹20L/yr CTC each without extending runway below 6 months",
    "Run a ₹8L marketing campaign in Q3 while keeping burn rate under ₹15L/month",
]
ALL_PROMPTS = PERSONAL_PROMPTS + INSTITUTE_PROMPTS + STARTUP_PROMPTS

MINIMAL_CSV = """\
Date,Description,Category,Amount,Type
2024-04-01,Rent Payment,Rent & Infrastructure,25000.00,outflow
2024-04-05,Swiggy Food,Food & Dining,450.00,outflow
2024-04-10,Salary Credit,Income,85000.00,inflow
2024-04-15,Electricity Bill,Utilities & Bills,1200.00,outflow
2024-04-20,Uber Ride,Travel & Transport,250.00,outflow
2024-05-01,Rent Payment,Rent & Infrastructure,25000.00,outflow
2024-05-10,Salary Credit,Income,85000.00,inflow
2024-05-15,Electricity Bill,Utilities & Bills,1300.00,outflow
2024-06-01,Rent Payment,Rent & Infrastructure,25000.00,outflow
2024-06-10,Salary Credit,Income,85000.00,inflow
2024-07-01,Rent Payment,Rent & Infrastructure,25000.00,outflow
2024-07-10,Salary Credit,Income,85000.00,inflow
2024-08-01,Rent Payment,Rent & Infrastructure,25000.00,outflow
2024-08-10,Salary Credit,Income,85000.00,inflow
2024-09-01,Rent Payment,Rent & Infrastructure,25000.00,outflow
2024-09-10,Salary Credit,Income,85000.00,inflow
2024-10-01,Rent Payment,Rent & Infrastructure,25000.00,outflow
2024-10-10,Salary Credit,Income,85000.00,inflow
2024-11-01,Rent Payment,Rent & Infrastructure,25000.00,outflow
2024-11-10,Salary Credit,Income,85000.00,inflow
2024-12-01,Rent Payment,Rent & Infrastructure,25000.00,outflow
2024-12-10,Salary Credit,Income,85000.00,inflow
2025-01-01,Rent Payment,Rent & Infrastructure,25000.00,outflow
2025-01-10,Salary Credit,Income,85000.00,inflow
2025-02-01,Rent Payment,Rent & Infrastructure,25000.00,outflow
2025-02-10,Salary Credit,Income,85000.00,inflow
2025-03-01,Rent Payment,Rent & Infrastructure,25000.00,outflow
2025-03-10,Salary Credit,Income,85000.00,inflow
""".encode("utf-8")


# ---------------------------------------------------------------------------
# In-Process Direct Client (no HTTP server needed)
# ---------------------------------------------------------------------------
class DirectClient:
    """Calls FastAPI route functions directly in-process."""

    def __init__(self):
        init_db()
        self.db = SessionLocal()

    async def inspect(self, csv_bytes: bytes, filename: str = "test.csv") -> dict:
        from fastapi import UploadFile
        file = UploadFile(filename=filename, file=io.BytesIO(csv_bytes))
        return await routes.inspect_dataset(file=file, db=self.db)

    def commit(self, upload_id: str, mapping: dict, name: str = "E2E Dataset",
               starting_balance: float = 50000.0) -> dict:
        req = routes.CommitRequest(
            upload_id=upload_id,
            confirmed_mapping=mapping,
            dataset_name=name,
            starting_balance=starting_balance,
        )
        return routes.commit_dataset(req, db=self.db)

    def list_datasets(self) -> list:
        return routes.list_datasets(db=self.db)

    def get_dataset(self, dataset_id: str) -> dict:
        return routes.get_dataset(dataset_id, db=self.db)

    def create_decision(self, text: str, dataset_id: str) -> dict:
        req = routes.CreateDecisionRequest(text=text, dataset_id=dataset_id)
        return routes.create_decision(req, db=self.db)

    def generate_scenarios(self, decision_id: str) -> list:
        return routes.generate_scenarios_endpoint(decision_id, db=self.db)

    def start_run(self, decision_id: str) -> dict:
        return routes.start_run(decision_id, db=self.db)

    def get_run_status(self, run_id: str) -> dict:
        return routes.get_run_status(run_id, db=self.db)

    def get_scenario_result(self, scenario_id: str) -> dict:
        return routes.get_scenario_result(scenario_id, db=self.db)

    def get_comparison(self, decision_id: str) -> dict:
        return routes.get_decision_comparison(decision_id, db=self.db)

    def branch_scenario(self, parent_id: str, name: str, change: dict) -> dict:
        req = routes.BranchScenarioRequest(name=name, change=change)
        return routes.branch_scenario_endpoint(parent_id, req, db=self.db)

    def health(self) -> dict:
        return routes.health_check()

    def close(self):
        self.db.close()


# ---------------------------------------------------------------------------
# Live HTTP Client
# ---------------------------------------------------------------------------
class LiveClient:
    def __init__(self, base_url: str):
        import httpx
        self.c = httpx.Client(base_url=base_url, timeout=60.0)

    async def inspect(self, csv_bytes: bytes, filename: str = "test.csv") -> dict:
        return self.c.post(
            "/datasets/inspect",
            files={"file": (filename, io.BytesIO(csv_bytes), "text/csv")},
        ).json()

    def commit(self, upload_id: str, mapping: dict, name: str = "E2E Dataset",
               starting_balance: float = 50000.0) -> dict:
        return self.c.post("/datasets/commit", json={
            "upload_id": upload_id,
            "confirmed_mapping": mapping,
            "dataset_name": name,
            "starting_balance": starting_balance,
        }).json()

    def list_datasets(self) -> list:
        return self.c.get("/datasets").json()

    def get_dataset(self, dataset_id: str) -> dict:
        return self.c.get(f"/datasets/{dataset_id}").json()

    def create_decision(self, text: str, dataset_id: str) -> dict:
        return self.c.post("/decisions", json={"text": text, "dataset_id": dataset_id}).json()

    def generate_scenarios(self, decision_id: str) -> list:
        return self.c.post(f"/decisions/{decision_id}/scenarios").json()

    def start_run(self, decision_id: str) -> dict:
        return self.c.post(f"/decisions/{decision_id}/run").json()

    def get_run_status(self, run_id: str) -> dict:
        return self.c.get(f"/runs/{run_id}").json()

    def get_scenario_result(self, scenario_id: str) -> dict:
        return self.c.get(f"/scenarios/{scenario_id}/result").json()

    def get_comparison(self, decision_id: str) -> dict:
        return self.c.get(f"/decisions/{decision_id}/compare").json()

    def branch_scenario(self, parent_id: str, name: str, change: dict) -> dict:
        return self.c.post(
            f"/scenarios/{parent_id}/branch",
            json={"name": name, "change": change},
        ).json()

    def health(self) -> dict:
        return self.c.get("/health").json()

    def close(self):
        self.c.close()


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------
def run_e2e(base_url: str = None, csv_path: str = None):
    print("=" * 62, flush=True)
    print("  FutureFork E2E Pipeline Test — Member 5", flush=True)
    print("=" * 62, flush=True)

    if base_url:
        client = LiveClient(base_url)
        mode = f"Live HTTP ({base_url})"
    else:
        client = DirectClient()
        mode = "In-Process Direct Client"

    print(f"Mode : {mode}", flush=True)
    csv_bytes = Path(csv_path).read_bytes() if csv_path else MINIMAL_CSV
    print(f"CSV  : {csv_path or '(built-in minimal demo CSV)'}\n", flush=True)

    passed = 0
    failed = 0

    def ok(cond: bool, label: str, detail: str = ""):
        nonlocal passed, failed
        if cond:
            print(f"  ✅  {label}", flush=True)
            passed += 1
        else:
            print(f"  ❌  {label}" + (f"  →  {detail}" if detail else ""), flush=True)
            failed += 1

    def section(title: str):
        print(f"\n── {title} {'─' * max(0, 55 - len(title))}", flush=True)

    try:
        loop = asyncio.new_event_loop()

        # ── 1. Health ────────────────────────────────────────────────
        section("1. Health & Liveness")
        h = client.health()
        ok(h.get("status") == "ok", "GET /health → status ok")

        # ── 2. POST /datasets/inspect ────────────────────────────────
        section("2. POST /datasets/inspect  (CSV Upload)")
        t0 = time.perf_counter()
        inspect_res = loop.run_until_complete(
            client.inspect(csv_bytes, filename="e2e_demo.csv")
        )
        elapsed_inspect = time.perf_counter() - t0

        ok("upload_id" in inspect_res, "Response contains upload_id",
           str(inspect_res.get("error", "")))
        ok(inspect_res.get("upload_id", "").startswith("upl_"),
           "upload_id has correct prefix 'upl_'")
        ok("proposed_mapping" in inspect_res, "Response contains proposed_mapping")
        ok("preview_rows" in inspect_res, "Response contains preview_rows")
        ok(len(inspect_res.get("preview_rows", [])) >= 1, "Preview has ≥ 1 row")
        ok("date_col" in inspect_res.get("proposed_mapping", {}),
           "proposed_mapping has date_col")
        ok(elapsed_inspect < 2.0, f"Inspect latency < 2s (actual: {elapsed_inspect:.2f}s)")

        upload_id = inspect_res["upload_id"]
        mapping = inspect_res["proposed_mapping"]

        # ── 3. POST /datasets/commit ─────────────────────────────────
        section("3. POST /datasets/commit  (Ingest + Node 0)")
        t0 = time.perf_counter()
        commit_res = client.commit(
            upload_id=upload_id,
            mapping=mapping,
            name="E2E Demo — Personal UPI",
            starting_balance=75000.0,
        )
        elapsed_commit = time.perf_counter() - t0

        ok("dataset_id" in commit_res, "Response contains dataset_id",
           str(commit_res.get("error", "")))
        ok(commit_res.get("dataset_id", "").startswith("ds_"),
           "dataset_id has correct prefix 'ds_'")
        ok("stats" in commit_res, "Response contains stats")
        ok("baseline_metrics" in commit_res, "Response contains baseline_metrics")
        ok(elapsed_commit < 1.0, f"Commit latency < 1s (actual: {elapsed_commit:.2f}s)")

        dataset_id = commit_res["dataset_id"]
        print(f"      dataset_id = {dataset_id}", flush=True)

        # Verify dataset is now queryable
        ds = client.get_dataset(dataset_id)
        ok(ds.get("id") == dataset_id, "GET /datasets/{id} returns committed dataset")

        datasets = client.list_datasets()
        ok(any(d["id"] == dataset_id for d in datasets),
           "GET /datasets includes newly committed dataset")

        # ── 4. POST /decisions ───────────────────────────────────────
        section("4. POST /decisions  (Financial Prompt → 4 Policy Forks)")
        prompt = PERSONAL_PROMPTS[0]
        print(f"      Prompt: \"{prompt}\"", flush=True)
        spec = client.create_decision(text=prompt, dataset_id=dataset_id)
        dec_id = spec.get("id", "")
        ok(bool(dec_id), "Decision spec has an id", str(spec.get("error", "")))
        ok(spec.get("status") == "ok", f"Decision parsed ({spec.get('status')})")
        params = spec.get("change", {}).get("params", {})
        ok(params.get("total_cost", 0) > 0, f"Parsed purchase cost ₹{params.get('total_cost', 0):,.0f}")
        print(f"      decision_id = {dec_id}  |  preference = {spec.get('change', {}).get('type')}", flush=True)

        # ── 5. POST /decisions/{id}/scenarios ────────────────────────
        section("5. POST /decisions/{id}/scenarios  (4 Branches)")
        scenarios = client.generate_scenarios(dec_id)
        sc_types = [s["change"]["type"] for s in scenarios]
        ok(sc_types == ["baseline", "upfront", "emi", "phased", "trim"],
           f"Baseline + 4 forks generated ({sc_types})")
        ok(all(s["status"] == "queued" for s in scenarios), "All forks ready to evaluate")
        baseline_id = scenarios[0]["id"]

        # ── 6. POST /decisions/{id}/run ──────────────────────────────
        section("6. POST /decisions/{id}/run  (CP-SAT + Monte Carlo)")
        run_res = client.start_run(dec_id)
        run_id = run_res.get("run_id", "")
        ok(run_id.startswith("run_"), f"Run dispatched  run_id={run_id}")

        # ── 7. Poll GET /runs/{id} ───────────────────────────────────
        section("7. GET /runs/{id}  (Poll to Done)")
        deadline = time.time() + 15.0
        run_data: dict = {}
        while time.time() < deadline:
            run_data = client.get_run_status(run_id)
            status_val = run_data.get("overall_status", "")
            print(f"      … status={status_val}", end="\r", flush=True)
            if status_val in ("done", "failed"):
                break
            time.sleep(0.4)
        print()
        ok(run_data.get("overall_status") == "done",
           f"Pipeline finished  status={run_data.get('overall_status')}")
        ok(set((run_data.get("scenarios") or {}).values()) == {"done"},
           "Every fork evaluated by CP-SAT + Monte Carlo")

        # ── 8. GET /decisions/{id}/compare ───────────────────────────
        section("8. GET /decisions/{id}/compare  (Side-by-Side + AI)")
        comp = client.get_comparison(dec_id)
        ok(comp.get("decision_id") == dec_id, "Comparison has correct decision_id")
        ok("scenarios" in comp, "Comparison has scenarios list")
        results = comp.get("results", {})
        ok(len(results) == 5, f"Comparison has 5 results (got {len(results)})")
        for r in results.values():
            m = r["metrics"]
            print(f"      {r['branch_type']:<9} survival {m['survival_score_pct']:5.1f}%  "
                  f"cash-out risk {m['cash_out_risk_pct']:5.1f}%  runway {m['runway_months']:4.1f} mo",
                  flush=True)
        explanation = comp.get("explanation", {})
        ok(bool(explanation.get("summary")), "Comparison has an explanation")
        ok(explanation.get("guard_passed") is True, "Explanation passed the Numeric Guard")

        # ── 9. POST /scenarios/{id}/branch ───────────────────────────
        section("9. POST /scenarios/{id}/branch  (Phase-2 Child Fork)")
        child = client.branch_scenario(
            parent_id=baseline_id,
            name="Custom: 12-month EMI",
            change={"type": "emi", "params": {"emi_months": 12}},
        )
        ok(child.get("parent_id") == baseline_id, "Child scenario has correct parent_id")
        ok(child.get("id", "").startswith("branch_"), "Child scenario id starts with 'branch_'")
        ok(child.get("status") == "done", f"Child fork evaluated ({child.get('status')})")

        # ── 10. Multi-prompt smoke test ──────────────────────────────
        section("10. Multi-Prompt Smoke Test  (6 prompts × 3 user types)")
        for prompt in ALL_PROMPTS:
            try:
                spec2 = client.create_decision(text=prompt, dataset_id=dataset_id)
                ok(
                    spec2.get("status") == "ok",
                    f"Prompt parsed: \"{prompt[:55]}…\"",
                )
            except Exception as exc2:
                ok(False, f"Prompt failed: \"{prompt[:55]}…\"", str(exc2))

    finally:
        loop.close() if not base_url else None
        client.close()

    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 62, flush=True)
    total = passed + failed
    print(
        f"  E2E Results: {passed}/{total} PASSED  |  {failed} FAILED",
        flush=True,
    )
    print("=" * 62, flush=True)

    if failed > 0:
        sys.exit(1)
    print("\n🚀  All checks passed — backend pipeline is green!", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FutureFork E2E Test Suite")
    parser.add_argument("--url", type=str, default=None,
                        help="Base URL of deployed API (omit for in-process mode)")
    parser.add_argument("--csv", type=str, default=None,
                        help="Path to a CSV file to use instead of built-in demo data")
    args = parser.parse_args()
    run_e2e(base_url=args.url, csv_path=args.csv)
