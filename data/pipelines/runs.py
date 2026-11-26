"""Run log of the pipeline: lock, phase checkpoint and status.

The partial unique index ux_pipeline_runs_one_running allows a single "running"
row per pipeline: that row is the lock. A run that stays "running" for more than
STALE_RUN_MINUTES is considered abandoned and is closed as failed before a new
run takes the lock.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Date, DateTime, bindparam, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from data.pipelines import db

PIPELINE_NAME = "weekly_location_performance"
STALE_RUN_MINUTES = 30

_TS = DateTime(timezone=True)
_DAY = Date()

_RUN_COLUMNS = (
    "run_id, pipeline_name, trigger_type, window_start, window_end, status, phase, "
    "started_at, finished_at, rows_extracted, rows_after_dedup, rows_rejected, "
    "rows_inserted, rows_updated, rows_unchanged, error_message, resumed_from_run_id, "
    "prefect_flow_run_id, details"
)


class PipelineLocked(RuntimeError):
    """Another run of the same pipeline is already running."""

    def __init__(self, active_run_id: str | None):
        super().__init__(f"Ya hay una corrida en curso ({active_run_id}).")
        self.active_run_id = active_run_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _text_id(value: Any) -> str | None:
    return None if value is None else str(value)


def open_run(
    *,
    trigger_type: str,
    window_start: date,
    window_end: date,
    run_id: str | None = None,
    prefect_flow_run_id: str | None = None,
    engine: Engine | None = None,
) -> str:
    """Open a run and take the lock. Raises PipelineLocked if another run is active."""
    engine = engine or db.get_engine()

    if run_id is not None:
        # The manual trigger already opened the run (and the lock): adopt it.
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    "select run_id from reporting.pipeline_runs "
                    "where run_id = :run_id and status = 'running'"
                ),
                {"run_id": run_id},
            ).first()
            if row is None:
                raise ValueError(f"La corrida {run_id} no existe o ya no está en curso.")
            connection.execute(
                text(
                    "update reporting.pipeline_runs set prefect_flow_run_id = :flow_run_id "
                    "where run_id = :run_id"
                ),
                {"flow_run_id": prefect_flow_run_id, "run_id": run_id},
            )
        return run_id

    now = _now()
    with engine.begin() as connection:
        connection.execute(
            text(
                "update reporting.pipeline_runs set status = 'failed', finished_at = :now, "
                "error_message = 'abandoned: no finish after the stale timeout' "
                "where pipeline_name = :name and status = 'running' and started_at < :cutoff"
            ).bindparams(bindparam("now", type_=_TS), bindparam("cutoff", type_=_TS)),
            {
                "now": now,
                "name": PIPELINE_NAME,
                "cutoff": now - timedelta(minutes=STALE_RUN_MINUTES),
            },
        )
        last = connection.execute(
            text(
                "select run_id, status from reporting.pipeline_runs "
                "where pipeline_name = :name and status <> 'running' "
                "order by started_at desc limit 1"
            ),
            {"name": PIPELINE_NAME},
        ).first()
    resumed_from = _text_id(last[0]) if last is not None and last[1] == "failed" else None

    new_id = str(uuid.uuid4())
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "insert into reporting.pipeline_runs "
                    "(run_id, pipeline_name, trigger_type, window_start, window_end, status, "
                    "phase, started_at, resumed_from_run_id, prefect_flow_run_id, details) "
                    "values (:run_id, :name, :trigger_type, :window_start, :window_end, "
                    "'running', 'open', :started_at, :resumed_from, :flow_run_id, :details)"
                ).bindparams(
                    bindparam("window_start", type_=_DAY),
                    bindparam("window_end", type_=_DAY),
                    bindparam("started_at", type_=_TS),
                ),
                {
                    "run_id": new_id,
                    "name": PIPELINE_NAME,
                    "trigger_type": trigger_type,
                    "window_start": window_start,
                    "window_end": window_end,
                    "started_at": now,
                    "resumed_from": resumed_from,
                    "flow_run_id": prefect_flow_run_id,
                    "details": "{}",
                },
            )
    except IntegrityError:
        with engine.connect() as connection:
            active = connection.execute(
                text(
                    "select run_id from reporting.pipeline_runs "
                    "where pipeline_name = :name and status = 'running' limit 1"
                ),
                {"name": PIPELINE_NAME},
            ).scalar()
        raise PipelineLocked(_text_id(active)) from None
    return new_id


def set_phase(run_id: str, phase: str, engine: Engine | None = None) -> None:
    """Phase checkpoint: where the run was if it fails."""
    engine = engine or db.get_engine()
    with engine.begin() as connection:
        connection.execute(
            text("update reporting.pipeline_runs set phase = :phase where run_id = :run_id"),
            {"phase": phase, "run_id": run_id},
        )


def close_run(
    *,
    run_id: str,
    status: str,
    phase: str,
    rows_extracted: int | None = None,
    rows_after_dedup: int | None = None,
    rows_rejected: int | None = None,
    rows_inserted: int | None = None,
    rows_updated: int | None = None,
    rows_unchanged: int | None = None,
    error_message: str | None = None,
    details: dict[str, Any] | None = None,
    engine: Engine | None = None,
) -> None:
    """Write the final status, counters and quality details, and release the lock."""
    engine = engine or db.get_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                "update reporting.pipeline_runs set status = :status, phase = :phase, "
                "finished_at = :finished_at, rows_extracted = :rows_extracted, "
                "rows_after_dedup = :rows_after_dedup, rows_rejected = :rows_rejected, "
                "rows_inserted = :rows_inserted, rows_updated = :rows_updated, "
                "rows_unchanged = :rows_unchanged, error_message = :error_message, "
                "details = :details where run_id = :run_id"
            ).bindparams(bindparam("finished_at", type_=_TS)),
            {
                "status": status,
                "phase": phase,
                "finished_at": _now(),
                "rows_extracted": rows_extracted,
                "rows_after_dedup": rows_after_dedup,
                "rows_rejected": rows_rejected,
                "rows_inserted": rows_inserted,
                "rows_updated": rows_updated,
                "rows_unchanged": rows_unchanged,
                "error_message": error_message,
                "details": json.dumps(details or {}, default=str),
                "run_id": run_id,
            },
        )


def get_latest_run(engine: Engine | None = None) -> dict[str, Any] | None:
    """Status and metadata of the most recent run, or None if there is none."""
    engine = engine or db.get_engine()
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    f"select {_RUN_COLUMNS} from reporting.pipeline_runs "
                    "where pipeline_name = :name order by started_at desc limit 1"
                ),
                {"name": PIPELINE_NAME},
            )
            .mappings()
            .first()
        )
    if row is None:
        return None
    run = dict(row)
    for key in ("run_id", "resumed_from_run_id"):
        run[key] = _text_id(run[key])
    # Postgres returns date objects; drivers without a native date type return text.
    for key in ("window_start", "window_end"):
        if isinstance(run[key], str):
            run[key] = date.fromisoformat(run[key][:10])
    details = run["details"]
    run["details"] = json.loads(details) if isinstance(details, str) else (details or {})
    return run


def fail_run_if_running(
    run_id: str,
    error_message: str,
    engine: Engine | None = None,
) -> bool:
    """Close a run as failed if it is still running, and release the lock.

    Used by the Celery worker when the pipeline process dies or times out
    before closing its own run. A run the flow already closed is left as is.
    """
    engine = engine or db.get_engine()
    with engine.begin() as connection:
        result = connection.execute(
            text(
                "update reporting.pipeline_runs set status = 'failed', "
                "finished_at = :finished_at, error_message = :error_message "
                "where run_id = :run_id and status = 'running'"
            ).bindparams(bindparam("finished_at", type_=_TS)),
            {"finished_at": _now(), "error_message": error_message[:500], "run_id": run_id},
        )
    return bool(result.rowcount)
