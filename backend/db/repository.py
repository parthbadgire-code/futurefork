"""
FutureFork Database Repository & Seeder
Persists uploads, datasets, decisions, scenarios, runs, results and the result cache.
Seeds the bundled sample CSVs as ready-to-use financial datasets on startup.
"""

import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.db.models import (
    CacheModel,
    DatasetModel,
    DecisionModel,
    ResultModel,
    RunModel,
    ScenarioModel,
    UploadModel,
)
from backend.db.session import Base, SessionLocal, engine

logger = logging.getLogger("futurefork.db")

# Bundled sample CSVs seeded as ready-to-use datasets: (dataset_id, csv name, display name, type)
SAMPLE_DATASETS = [
    ("sample_personal", "personal_upi.csv", "Sample: Personal UPI Statement", "personal"),
    ("sample_institute", "institute_erp_1.8cr.csv", "Sample: Institute ERP Ledger (~₹1.8 Cr)", "institute"),
    ("sample_startup", "startup_pnl.csv", "Sample: Startup P&L / Burn", "startup"),
]


def build_dataset_record(
    instance: Any,
    dataset_id: str,
    name: str,
    dataset_type: str,
    source_filename: str,
    column_mapping: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Builds the persisted dataset record (summary + compiled instance + Node 0 metrics)."""
    from engine.solver import attach_simulation, evaluate_financial_baseline

    instance.dataset_id = dataset_id
    instance.name = name
    baseline = attach_simulation(evaluate_financial_baseline(instance, emergency_floor=0.0), instance)
    stats = {
        "months": len(instance.months),
        "categories": len(instance.categories),
        "starting_balance": instance.starting_balance,
        "total_inflow": round(float(sum(instance.inflows)), 2),
        "total_outflow": round(float(sum(instance.total_outflows)), 2),
        "category_types": instance.category_types,
    }
    description = f"Financial dataset compiled from {source_filename}"
    summary = {
        "id": dataset_id,
        "name": name,
        "description": description,
        "dataset_type": dataset_type,
        "stats": stats,
        "baseline_metrics": baseline.metrics,
    }
    return {
        "id": dataset_id,
        "name": name,
        "description": description,
        "stats": stats,
        "baseline_metrics": baseline.metrics,
        "payload": {
            "summary": summary,
            "instance": instance.to_dict(),
            "column_mapping": column_mapping or {},
            "source_filename": source_filename,
        },
    }


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        repo = Repository(db)
        for dataset_id, csv_name, display_name, dataset_type in SAMPLE_DATASETS:
            if repo.get_dataset(dataset_id):
                continue
            try:
                from data.loader import load_sample_instance

                instance = load_sample_instance(csv_name)
                repo.save_dataset(
                    build_dataset_record(instance, dataset_id, display_name, dataset_type, csv_name)
                )
            except Exception as exc:  # a broken sample must not stop the API from starting
                logger.warning("Could not seed sample dataset %s: %s", dataset_id, exc)
    finally:
        db.close()


class Repository:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # MEMBER 5: Upload buffer (inspect → commit flow)
    # ------------------------------------------------------------------

    def save_upload(
        self,
        upload_id: str,
        csv_bytes: bytes,
        filename: str,
        preview_rows: List[Dict[str, Any]],
        column_mapping: Dict[str, Any],
        ttl_minutes: int = 15,
    ) -> UploadModel:
        """Persist raw CSV bytes (base64) with a TTL expiry for /datasets/inspect."""
        encoded = base64.b64encode(csv_bytes).decode("utf-8")
        expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=ttl_minutes)
        model = UploadModel(
            upload_id=upload_id,
            filename=filename,
            csv_bytes=encoded,
            preview_rows=preview_rows,
            column_mapping=column_mapping,
            expires_at=expires,
        )
        self.db.merge(model)
        self.db.commit()
        return model

    def get_upload(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a non-expired upload by ID."""
        row = self.db.query(UploadModel).filter(UploadModel.upload_id == upload_id).first()
        if not row:
            return None
        if row.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            # TTL expired — delete and return None
            self.db.delete(row)
            self.db.commit()
            return None
        return {
            "upload_id": row.upload_id,
            "filename": row.filename,
            "csv_bytes": base64.b64decode(row.csv_bytes),
            "preview_rows": row.preview_rows,
            "column_mapping": row.column_mapping,
            "expires_at": row.expires_at.isoformat(),
        }

    def delete_upload(self, upload_id: str) -> None:
        row = self.db.query(UploadModel).filter(UploadModel.upload_id == upload_id).first()
        if row:
            self.db.delete(row)
            self.db.commit()

    # ------------------------------------------------------------------
    # Dataset queries
    # ------------------------------------------------------------------

    def list_datasets(self) -> List[Dict[str, Any]]:
        rows = self.db.query(DatasetModel).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "stats": r.stats,
                "baseline_metrics": r.baseline_metrics,
            }
            for r in rows
        ]

    def save_dataset(self, ds_dict: Dict[str, Any]) -> DatasetModel:
        """Upsert a dataset bundle (used by /datasets/commit)."""
        model = DatasetModel(
            id=ds_dict["id"],
            name=ds_dict["name"],
            description=ds_dict.get("description", ""),
            stats=ds_dict["stats"],
            baseline_metrics=ds_dict["baseline_metrics"],
            payload=ds_dict.get("payload"),
        )
        self.db.merge(model)
        self.db.commit()
        return model

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        r = self.db.query(DatasetModel).filter(DatasetModel.id == dataset_id).first()
        if not r:
            return None
        return {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "stats": r.stats,
            "baseline_metrics": r.baseline_metrics,
            "payload": r.payload,
        }

    # ------------------------------------------------------------------
    # Decision queries
    # ------------------------------------------------------------------

    def save_decision(self, spec: Dict[str, Any]) -> DecisionModel:
        model = DecisionModel(
            id=spec["id"],
            text=spec["text"],
            dataset_id=spec["dataset_id"],
            status=spec["status"],
            message=spec.get("message"),
            spec=spec,
        )
        self.db.merge(model)
        self.db.commit()
        return model

    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        row = self.db.query(DecisionModel).filter(DecisionModel.id == decision_id).first()
        return row.spec if row else None

    # ------------------------------------------------------------------
    # Scenario queries
    # ------------------------------------------------------------------

    def save_scenarios(self, scenarios: List[Dict[str, Any]]):
        for s in scenarios:
            model = ScenarioModel(
                id=s["id"],
                decision_id=s["decision_id"],
                parent_id=s.get("parent_id"),
                name=s["name"],
                description=s.get("description", ""),
                change=s["change"],
                status=s.get("status", "queued"),
            )
            self.db.merge(model)
        self.db.commit()

    def get_scenarios(self, decision_id: str) -> List[Dict[str, Any]]:
        rows = self.db.query(ScenarioModel).filter(ScenarioModel.decision_id == decision_id).all()
        return [
            {
                "id": r.id,
                "decision_id": r.decision_id,
                "parent_id": r.parent_id,
                "name": r.name,
                "description": r.description,
                "change": r.change,
                "status": r.status,
            }
            for r in rows
        ]

    def update_scenario_status(self, scenario_id: str, status: str):
        row = self.db.query(ScenarioModel).filter(ScenarioModel.id == scenario_id).first()
        if row:
            row.status = status
            self.db.commit()

    # ------------------------------------------------------------------
    # Run queries
    # ------------------------------------------------------------------

    def create_run(self, run_id: str, decision_id: str, scenario_ids: List[str]) -> RunModel:
        statuses = {s_id: "queued" for s_id in scenario_ids}
        run = RunModel(
            id=run_id,
            decision_id=decision_id,
            overall_status="queued",
            progress_percent=0.0,
            scenario_statuses=statuses,
        )
        self.db.add(run)
        self.db.commit()
        return run

    def update_run_status(
        self,
        run_id: str,
        overall_status: str,
        progress_percent: float,
        scenario_statuses: Dict[str, str],
    ):
        run = self.db.query(RunModel).filter(RunModel.id == run_id).first()
        if run:
            run.overall_status = overall_status
            run.progress_percent = progress_percent
            run.scenario_statuses = scenario_statuses
            self.db.commit()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        r = self.db.query(RunModel).filter(RunModel.id == run_id).first()
        if not r:
            return None
        return {
            "run_id": r.id,
            "decision_id": r.decision_id,
            "overall_status": r.overall_status,
            "progress_percent": r.progress_percent,
            "scenarios": r.scenario_statuses,
        }

    # ------------------------------------------------------------------
    # Result queries
    # ------------------------------------------------------------------

    def save_result(self, result: Dict[str, Any]):
        """Stores a raw engine result (see integrations.call_evaluate_scenario)."""
        model = ResultModel(
            scenario_id=result["scenario_id"],
            decision_id=result.get("decision_id"),
            branch_type=result.get("branch_type"),
            payload=result,
        )
        self.db.merge(model)
        self.db.commit()

    def get_result(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """Returns the raw engine result dict for a scenario, or None."""
        r = self.db.query(ResultModel).filter(ResultModel.scenario_id == scenario_id).first()
        return dict(r.payload) if r else None

    # ------------------------------------------------------------------
    # Caching
    # ------------------------------------------------------------------

    def get_cached_result(self, key: str) -> Optional[Dict[str, Any]]:
        row = self.db.query(CacheModel).filter(CacheModel.cache_key == key).first()
        return row.result if row else None

    def set_cached_result(self, key: str, val: Dict[str, Any]):
        entry = CacheModel(cache_key=key, result=val)
        self.db.merge(entry)
        self.db.commit()
