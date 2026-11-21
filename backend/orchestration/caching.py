"""
FutureFork Cache Engine
Caches scenario evaluations by a deterministic hash of the dataset, the change spec,
the simulation settings, and the engine result format version.
"""

import hashlib
import json
from typing import Any, Dict

# Bump when the stored engine result format changes so stale entries are never reused.
CACHE_VERSION = 2


def compute_cache_key(
    dataset_id: str,
    change: Dict[str, Any],
    seed: int = 42,
    n_sims: int = 300,
) -> str:
    raw = json.dumps(
        {
            "v": CACHE_VERSION,
            "dataset_id": dataset_id,
            "change_type": change.get("type"),
            "change_params": change.get("params", {}),
            "seed": seed,
            "n_sims": n_sims,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
