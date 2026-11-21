"""
FutureFork Orchestration Runner
Evaluates every scenario branch of a decision in the background with per-scenario
status, result caching, and error isolation (one failed fork never fails the others).
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from backend import settings
from backend.db.repository import Repository
from backend.db.session import SessionLocal
from backend.orchestration.caching import compute_cache_key
from backend.orchestration.integrations import call_evaluate_scenario, load_instance

logger = logging.getLogger("futurefork.runner")

# Thread pool for background runs (one decision run per worker)
background_executor = ThreadPoolExecutor(max_workers=4)


def execute_decision_pipeline(decision_id: str, run_id: str):
    """Background task: evaluates all queued scenarios of a decision with the real engine."""
    db = SessionLocal()
    repo = Repository(db)

    try:
        decision = repo.get_decision(decision_id)
        if not decision:
            logger.error(f"Decision {decision_id} not found in DB")
            repo.update_run_status(run_id, "failed", 0.0, {})
            return

        dataset_id = decision.get("dataset_id", "")
        dataset_row = repo.get_dataset(dataset_id)
        instance = load_instance(dataset_row["payload"] if dataset_row else {})

        scenarios = repo.get_scenarios(decision_id)
        if not scenarios:
            logger.error(f"No scenarios found for decision {decision_id}")
            repo.update_run_status(run_id, "failed", 0.0, {})
            return

        # Scenarios rejected during fan-out (e.g. unparseable cost) stay failed
        scenario_statuses = {
            s["id"]: ("failed" if s.get("status") == "failed" else "queued") for s in scenarios
        }
        repo.update_run_status(run_id, "running", 10.0, scenario_statuses)

        n_sims, seed = settings.NUM_SIMULATION_RUNS, settings.RANDOM_SEED
        total = len(scenarios)
        finished = sum(1 for st in scenario_statuses.values() if st == "failed")

        for sc in scenarios:
            sc_id = sc["id"]
            if scenario_statuses[sc_id] == "failed":
                continue

            scenario_statuses[sc_id] = "running"
            repo.update_scenario_status(sc_id, "running")
            repo.update_run_status(run_id, "running", 10.0 + (finished / total) * 85.0, scenario_statuses)

            change = sc.get("change", {})
            cache_key = compute_cache_key(dataset_id, change, seed=seed, n_sims=n_sims)
            cached = repo.get_cached_result(cache_key) if settings.CACHE_ENABLED else None

            try:
                if cached:
                    logger.info(f"Cache hit for scenario {sc_id} (key: {cache_key[:8]}...)")
                    res: Dict[str, Any] = dict(cached)
                    res["scenario_id"] = sc_id
                    res["decision_id"] = decision_id
                else:
                    start = time.time()
                    res = call_evaluate_scenario(instance, sc, n_sims=n_sims, seed=seed)
                    if settings.CACHE_ENABLED:
                        repo.set_cached_result(cache_key, res)
                    logger.info(f"Evaluated scenario {sc_id} in {time.time() - start:.2f}s")

                repo.save_result(res)
                scenario_statuses[sc_id] = "done"
                repo.update_scenario_status(sc_id, "done")
            except Exception as ex:
                logger.exception(f"Error evaluating scenario {sc_id}: {ex}")
                scenario_statuses[sc_id] = "failed"
                repo.update_scenario_status(sc_id, "failed")

            finished += 1
            repo.update_run_status(run_id, "running", 10.0 + (finished / total) * 85.0, scenario_statuses)

        any_done = any(st == "done" for st in scenario_statuses.values())
        repo.update_run_status(run_id, "done" if any_done else "failed", 100.0, scenario_statuses)
        logger.info(f"Pipeline finished for decision {decision_id}, run {run_id}")

    except Exception as e:
        logger.exception(f"Pipeline failed for run {run_id}: {e}")
        repo.update_run_status(run_id, "failed", 0.0, {})
    finally:
        db.close()


def dispatch_decision_run(decision_id: str, run_id: str):
    """Schedules the background pipeline without blocking the HTTP response."""
    background_executor.submit(execute_decision_pipeline, decision_id, run_id)
