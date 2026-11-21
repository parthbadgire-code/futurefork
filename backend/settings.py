"""
FutureFork backend settings, read once from the environment (and `.env` if present).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT.lower() == "production"

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
    ).split(",")
    if o.strip()
]

NUM_SIMULATION_RUNS = int(os.getenv("NUM_SIMULATION_RUNS", "300"))
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))
CACHE_ENABLED = _bool("CACHE_ENABLED", True)
