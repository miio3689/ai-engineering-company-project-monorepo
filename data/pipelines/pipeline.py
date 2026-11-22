"""Resilient business performance pipeline (Prefect 3). Main entry point.

Purpose (data/pipelines/PIPELINE_DESIGN.md, section 2.1): every week, per
location and country, produce the consolidated data of the "Reporte Semanal de
Costo y Merma por Local" read by Mariana (CEO) and Felipe (Director of
Operations). It reads telemetry_events (read only) and writes only to
reporting.weekly_location_performance and reporting.pipeline_runs.

Run it from the command line (repository root):

    uv run python data/pipelines/pipeline.py                     # recompute the last 4 weeks
    uv run python data/pipelines/pipeline.py --lookback-weeks 8
    uv run python data/pipelines/pipeline.py --serve             # schedule it every Monday 05:00 UTC

Expected frequency: weekly, Monday 05:00 UTC (midnight in Bogota), plus the
manual trigger POST /reporting/pipeline-runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import pandas as pd  # noqa: E402
from prefect import flow, get_run_logger, task  # noqa: E402
from prefect.exceptions import MissingContextError  # noqa: E402
from prefect.runtime import flow_run  # noqa: E402

from data.pipelines import db, queries, runs  # noqa: E402
from data.process import weekly_location_performance as process  # noqa: E402

EVAL_DIR = REPOSITORY_ROOT / "data" / "eval"


def _logger() -> Any:
    try:
        return get_run_logger()
    except MissingContextError:
        return logging.getLogger("data.pipelines")


def _flow_run_id() -> str | None:
    return flow_run.id


def _state_message(state: Any) -> str:
    return str(state.message or state.name)[:300]


def transform_cache_key(context: Any, parameters: dict[str, Any]) -> str:
    """Cache key of transform_weekly_metrics.

    It is built from the window plus a hash of the event ids and of location_dim.
    Telemetry events are immutable, so the same ids always give the same weekly
    result. The entry is valid for one hour (cache_expiration): a second run
    within the hour reuses the result instead of recomputing it, and any new
    event or change in location_dim changes the key.
    """
    digest = hashlib.sha256()
    digest.update(str(parameters["window_start"]).encode())
    digest.update(str(parameters["window_end"]).encode())
    ids = parameters["events"]["id"].astype(str).sort_values()
    digest.update(pd.util.hash_pandas_object(ids, index=False).to_numpy().tobytes())
    dim = parameters["location_dim"].astype(str)
    digest.update(pd.util.hash_pandas_object(dim, index=False).to_numpy().tobytes())
    return f"weekly-location-performance-transform:{digest.hexdigest()}"


# ---------------------------------------------------------------- tasks

# open_run touches the database. 2 retries: a transient failure is absorbed, but a
# lock conflict is not an error (it is returned as locked=True).
@task(name="open_run", retries=2, retry_delay_seconds=[5, 15])
def open_run_step(
    trigger_type: str,
    window_start: date,
    window_end: date,
    run_id: str | None,
    prefect_flow_run_id: str | None,
) -> dict[str, Any]:
    try:
        opened = runs.open_run(
            trigger_type=trigger_type,
            window_start=window_start,
            window_end=window_end,
            run_id=run_id,
            prefect_flow_run_id=prefect_flow_run_id,
        )
    except runs.PipelineLocked as locked:
        return {"run_id": locked.active_run_id, "locked": True}
    return {"run_id": opened, "locked": False}


# Database reads. 3 retries with growing waits (10, 30 and 90 s): enough to ride out a
# Supabase restart or a pooler hiccup (about 2 minutes) without hiding a real outage.
@task(name="extract_telemetry_events", retries=3, retry_delay_seconds=[10, 30, 90])
def extract_telemetry_events(window_start: date, window_end: date) -> dict[str, Any]:
    events, source_total = queries.extract_events(db.get_engine(), window_start, window_end)
    return {"events": events, "source_total_events": source_total}


@task(name="extract_location_dim", retries=3, retry_delay_seconds=[10, 30, 90])
def extract_location_dim() -> pd.DataFrame:
    location_dim = queries.load_location_dim(db.get_engine())
    if location_dim.empty:
        raise RuntimeError(
            "reporting.location_dim está vacía: ejecuta data/pipelines/sql/location_dim_seed.sql"
        )
    return location_dim


# OPTIONAL step (called with return_state=True): if the quality checks fail the run
# continues and finishes as completed_with_warnings. 2 retries: reads only.
@task(name="check_source_health", retries=2, retry_delay_seconds=[10, 30])
def check_source_health(
    events: pd.DataFrame,
    window_start: date,
    window_end: date,
) -> dict[str, Any]:
    facts, _ = process.prepare_events(events)
    entries, waste_exits = queries.read_domain_rows(
        db.get_engine(), window_start, window_end
    )
    return {
        "silent_locations": process.find_silent_locations(facts, window_start, window_end),
        "reconciliation": process.reconcile_with_domain(facts, entries, waste_exits),
    }


# Expensive Pandas transformation: cached for one hour (see transform_cache_key).
# It is a pure function, so it is not retried: a failure is a logic or data error.
@task(
    name="transform_weekly_metrics",
    cache_key_fn=transform_cache_key,
    cache_expiration=timedelta(hours=1),
    persist_result=True,
)
def transform_weekly_metrics(
    events: pd.DataFrame,
    location_dim: pd.DataFrame,
    window_start: date,
    window_end: date,
) -> dict[str, Any]:
    result = process.transform_weekly_metrics(events, location_dim, window_start, window_end)
    return {"weekly": result.weekly, "stats": result.stats}


# The load is one transaction with an upsert, so repeating it is safe: 3 retries.
@task(name="load_weekly_location_performance", retries=3, retry_delay_seconds=[10, 30, 90])
def load_weekly_location_performance(
    weekly: pd.DataFrame,
    window_start: date,
    window_end: date,
) -> dict[str, Any]:
    return queries.load_weekly(db.get_engine(), weekly, window_start, window_end)


# OPTIONAL, non-critical step: a snapshot of the result for validation in data/eval/.
@task(name="export_eval_snapshot")
def export_eval_snapshot(weekly: pd.DataFrame, run_id: str) -> str:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    path = EVAL_DIR / f"weekly_location_performance_{run_id}.json"
    records = weekly.assign(week_start=weekly["week_start"].astype(str)).to_dict(
        orient="records"
    )
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return str(path)


# Closing the run is what releases the lock: 3 retries.
@task(name="close_run", retries=3, retry_delay_seconds=[5, 15, 45])
def close_run_step(**kwargs: Any) -> None:
    runs.close_run(**kwargs)


# ----------------------------------------------------------------- flow

@flow(name="weekly-location-performance")
def weekly_location_performance_flow(
    reference_date: date | None = None,
    lookback_weeks: int = process.DEFAULT_LOOKBACK_WEEKS,
    trigger_type: str = "schedule",
    run_id: str | None = None,
) -> dict[str, Any]:
    """Recompute the last `lookback_weeks` ISO weeks and upsert them."""
    logger = _logger()
    window_start, window_end = process.compute_window(reference_date, lookback_weeks)

    opened = open_run_step(
        trigger_type, window_start, window_end, run_id, _flow_run_id()
    )
    if opened["locked"]:
        logger.warning("Otra corrida está en curso (%s): no se ejecuta.", opened["run_id"])
        return {
            "run_id": opened["run_id"],
            "status": "skipped_locked",
            "window_start": str(window_start),
            "window_end": str(window_end),
        }
    run_id = opened["run_id"]

    phase = "open"
    details: dict[str, Any] = {"warnings": []}
    warnings: list[str] = details["warnings"]
    counts: dict[str, Any] = {}
    status = "completed"
    try:
        phase = "extract"
        runs.set_phase(run_id, phase)
        extraction = extract_telemetry_events(window_start, window_end)
        location_dim = extract_location_dim()
        events = extraction["events"]
        source_total = extraction["source_total_events"]
        details["source_total_events"] = source_total

        # Optional step: a failure is recorded and the run continues.
        health = check_source_health(events, window_start, window_end, return_state=True)
        if health.is_completed():
            details["health"] = health.result()
            if details["health"]["silent_locations"] or details["health"]["reconciliation"]:
                warnings.append("health_checks_flagged")
        else:
            warnings.append("check_source_health_failed")
            details["health_error"] = _state_message(health)

        if source_total == 0:
            # No event of any type in the window: capture is down. Never overwrite
            # published figures with zeros.
            warnings.append("no_source_data")
            counts = {"rows_extracted": 0}
        else:
            phase = "transform"
            runs.set_phase(run_id, phase)
            transformed = transform_weekly_metrics(
                events, location_dim, window_start, window_end
            )
            stats = transformed["stats"]
            details["transform"] = stats
            if stats["events_without_cost"]:
                warnings.append("events_without_cost")
            if stats["rows_rejected"]:
                warnings.append("events_rejected")

            phase = "load"
            runs.set_phase(run_id, phase)
            loaded = load_weekly_location_performance(
                transformed["weekly"], window_start, window_end
            )
            details["weeks_revised"] = loaded["weeks_revised"]

            snapshot = export_eval_snapshot(transformed["weekly"], run_id, return_state=True)
            if snapshot.is_completed():
                details["snapshot"] = snapshot.result()
            else:
                warnings.append("eval_snapshot_failed")
                details["snapshot_error"] = _state_message(snapshot)

            counts = {
                "rows_extracted": int(len(events)),
                "rows_after_dedup": int(
                    stats["events_in"]
                    - stats["duplicate_ids_dropped"]
                    - stats["duplicate_facts_dropped"]
                ),
                "rows_rejected": int(stats["rows_rejected"]),
                "rows_inserted": int(loaded["rows_inserted"]),
                "rows_updated": int(loaded["rows_updated"]),
                "rows_unchanged": int(loaded["rows_unchanged"]),
            }

        status = "completed_with_warnings" if warnings else "completed"
        close_run_step(
            run_id=run_id, status=status, phase="close", details=details, **counts
        )
        return {
            "run_id": run_id,
            "status": status,
            "window_start": str(window_start),
            "window_end": str(window_end),
            **counts,
            "warnings": warnings,
        }
    except Exception as exc:
        try:
            runs.close_run(
                run_id=run_id,
                status="failed",
                phase=phase,
                error_message=f"{type(exc).__name__}: {exc}"[:500],
                details=details,
            )
        except Exception:
            logger.exception("No se pudo cerrar la corrida %s como fallida.", run_id)
        raise


# ------------------------------------------------------------------ CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pipeline de desempeño de negocio: KPIs semanales por local."
    )
    parser.add_argument(
        "--reference-date",
        type=date.fromisoformat,
        default=None,
        help="Cualquier día (YYYY-MM-DD) de la semana de referencia. Por defecto, hoy en UTC.",
    )
    parser.add_argument(
        "--lookback-weeks",
        type=int,
        default=process.DEFAULT_LOOKBACK_WEEKS,
        help="Semanas ISO a recalcular, la de referencia incluida (por defecto 4).",
    )
    parser.add_argument(
        "--trigger-type",
        choices=["schedule", "manual", "backfill"],
        default="manual",
    )
    parser.add_argument("--run-id", default=None, help="Corrida ya abierta por el disparo manual.")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Programa el flow cada lunes 05:00 UTC y lo mantiene en ejecución.",
    )
    args = parser.parse_args(argv)

    if args.serve:
        weekly_location_performance_flow.serve(
            name="weekly-location-performance",
            cron="0 5 * * 1",
            parameters={"trigger_type": "schedule"},
        )
        return 0

    result = weekly_location_performance_flow(
        reference_date=args.reference_date,
        lookback_weeks=args.lookback_weeks,
        trigger_type=args.trigger_type,
        run_id=args.run_id,
    )
    print(json.dumps(result, default=str, indent=2))
    return 0 if result["status"] in ("completed", "completed_with_warnings") else 3


if __name__ == "__main__":
    raise SystemExit(main())
