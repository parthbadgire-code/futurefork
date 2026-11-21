"""
FutureFork Database Models
Stores flexible payloads as JSON/JSONB across SQLite and Supabase Postgres.

Member 5 additions:
  - UploadModel  : transient raw-CSV store with 15-min TTL and ColumnMapping cache
"""


from sqlalchemy import JSON, Column, DateTime, Float, String, Text, func

from backend.db.session import Base

# ---------------------------------------------------------------------------
# MEMBER 5: Upload buffer for POST /datasets/inspect → POST /datasets/commit
# ---------------------------------------------------------------------------

class UploadModel(Base):
    __tablename__ = "uploads"

    upload_id    = Column(String(100), primary_key=True, index=True)
    filename     = Column(String(500), nullable=True)
    csv_bytes    = Column(Text, nullable=False)          # base64-encoded raw CSV bytes
    preview_rows = Column(JSON,  nullable=True)          # 5-row preview list[dict]
    column_mapping = Column(JSON, nullable=True)         # proposed ColumnMapping dict
    expires_at   = Column(DateTime, nullable=False)      # created_at + 15 min TTL
    created_at   = Column(DateTime, default=func.now())


# ---------------------------------------------------------------------------
# EXISTING MODELS (unchanged)
# ---------------------------------------------------------------------------

class DatasetModel(Base):
    __tablename__ = "datasets"

    id               = Column(String(100), primary_key=True, index=True)
    name             = Column(String(255), nullable=False)
    description      = Column(Text, nullable=True)
    stats            = Column(JSON, nullable=False)
    baseline_metrics = Column(JSON, nullable=False)
    payload          = Column(JSON, nullable=True)   # Full dataset bundle
    created_at       = Column(DateTime, default=func.now())


class DecisionModel(Base):
    __tablename__ = "decisions"

    id         = Column(String(100), primary_key=True, index=True)
    text       = Column(Text, nullable=False)
    dataset_id = Column(String(100), nullable=False, index=True)
    status     = Column(String(50), default="ok")
    message    = Column(Text, nullable=True)
    spec       = Column(JSON, nullable=False)         # DecisionSpec dict
    created_at = Column(DateTime, default=func.now())


class ScenarioModel(Base):
    __tablename__ = "scenarios"

    id          = Column(String(100), primary_key=True, index=True)
    decision_id = Column(String(100), nullable=False, index=True)
    parent_id   = Column(String(100), nullable=True)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    change      = Column(JSON, nullable=False)
    status      = Column(String(50), default="queued")  # queued|running|done|failed
    created_at  = Column(DateTime, default=func.now())


class RunModel(Base):
    __tablename__ = "runs"

    id               = Column(String(100), primary_key=True, index=True)
    decision_id      = Column(String(100), nullable=False, index=True)
    overall_status   = Column(String(50), default="queued")  # queued|running|done|failed
    progress_percent = Column(Float, default=0.0)
    scenario_statuses = Column(JSON, default=dict)           # Dict[scenario_id, status]
    created_at       = Column(DateTime, default=func.now())
    updated_at       = Column(DateTime, default=func.now(), onupdate=func.now())


class ResultModel(Base):
    __tablename__ = "results"

    scenario_id = Column(String(100), primary_key=True, index=True)
    decision_id = Column(String(100), nullable=True, index=True)
    branch_type = Column(String(50), nullable=True)
    payload     = Column(JSON, nullable=False)   # raw engine ScenarioEvaluationResult dict
    created_at  = Column(DateTime, default=func.now())


class CacheModel(Base):
    __tablename__ = "cache"

    cache_key  = Column(String(255), primary_key=True, index=True)
    result     = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=func.now())
