"""Lifecycle of a background job in public.job_runs.

State machine of every execution:

    pending -> processing -> completed
                          -> failed

* pending: the row is created before anything else happens.
* processing: set before doing any work. It IS the lock: while a row of a job
  is in processing, any other instance of that job aborts silently. The partial
  unique index ux_job_runs_one_processing makes the transition atomic, so two
  instances started at the same moment cannot both reach processing.
* completed: only when all the work finished. A skipped execution (the day was
  already completed, or the lock was taken) is recorded as completed with a
  skip_reason, and never counts as a completed day.
* failed: any exception (or a stop signal) moves the row to failed with its
  message; the finally block guarantees that no row is left in processing.

Every function receives the SQLAlchemy engine, so the module works with
PostgreSQL (Supabase) and with SQLite (tests).
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import Date, DateTime, bindparam, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

PENDING = "pending"
PROCESSING = "processing"
COMPLETED = "completed"
FAILED = "failed"

SKIP_DUPLICATE = "duplicate"
SKIP_LOCKED = "locked"

# A processing row older than this was abandoned by a killed process (SIGKILL,
# power loss): it is closed as failed so it never blocks the job forever.
DEFAULT_STALE_AFTER = timedelta(hours=2)

_TS = DateTime(timezone=True)
_DAY = Date()
_ERROR_LIMIT = 2000

logger = logging.getLogger("services.job_runner")


class JobLocked(RuntimeError):
    """Another execution of the same job is in processing."""

    def __init__(self, job_name: str, active_run_id: str | None):
        super().__init__(f"{job_name} is already processing (run {active_run_id}).")
        self.active_run_id = active_run_id


@dataclass
class JobOutcome:
    run_id: str
    status: str
    skip_reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


class _JobLog:
    """Logger whose every line carries the job name and the resulting status."""

    def __init__(self, job_name: str, base: logging.Logger):
        self.job_name = job_name
        self.base = base

    def _log(self, level: int, status: str, message: str, *args: Any, **kwargs: Any) -> None:
        extra = {"job_name": self.job_name, "status": status}
        self.base.log(level, message, *args, extra=extra, **kwargs)

    def info(self, status: str, message: str, *args: Any) -> None:
        self._log(logging.INFO, status, message, *args)

    def error(self, status: str, message: str, *args: Any, exc_info: Any = None) -> None:
        self._log(logging.ERROR, status, message, *args, exc_info=exc_info)


def job_log(job_name: str, base: logging.Logger | None = None) -> _JobLog:
    return _JobLog(job_name, base or logger)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _text_id(value: Any) -> str | None:
    return None if value is None else str(value)


# ------------------------------------------------------------ queries

def create_job_run(job_name: str, target_date: date, engine: Engine) -> str:
    """Insert the row of a new execution in pending and return its id."""
    run_id = str(uuid.uuid4())
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into job_runs (id, job_name, target_date, status, details, created_at) "
                "values (:id, :job_name, :target_date, :status, :details, :created_at)"
            ).bindparams(
                bindparam("target_date", type_=_DAY), bindparam("created_at", type_=_TS)
            ),
            {
                "id": run_id,
                "job_name": job_name,
                "target_date": target_date,
                "status": PENDING,
                "details": "{}",
                "created_at": _now(),
            },
        )
    return run_id


def has_processing_lock(job_name: str, engine: Engine) -> str | None:
    """Id of the execution of this job that is in processing, or None."""
    with engine.connect() as connection:
        active = connection.execute(
            text(
                "select id from job_runs where job_name = :job_name "
                "and status = :status limit 1"
            ),
            {"job_name": job_name, "status": PROCESSING},
        ).scalar()
    return _text_id(active)


def has_completed_for_date(job_name: str, target_date: date, engine: Engine) -> bool:
    """True if the job already did its work for that day (skipped runs do not count)."""
    with engine.connect() as connection:
        found = connection.execute(
            text(
                "select 1 from job_runs where job_name = :job_name "
                "and target_date = :target_date and status = :status "
                "and skip_reason is null limit 1"
            ).bindparams(bindparam("target_date", type_=_DAY)),
            {"job_name": job_name, "target_date": target_date, "status": COMPLETED},
        ).first()
    return found is not None


def start_processing(run_id: str, job_name: str, engine: Engine) -> None:
    """pending -> processing (takes the lock). Raises JobLocked if it is taken."""
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "update job_runs set status = :status, started_at = :started_at "
                    "where id = :id and status = :pending"
                ).bindparams(bindparam("started_at", type_=_TS)),
                {"status": PROCESSING, "started_at": _now(), "id": run_id, "pending": PENDING},
            )
    except IntegrityError:
        raise JobLocked(job_name, has_processing_lock(job_name, engine)) from None


def _finish(
    run_id: str,
    status: str,
    engine: Engine,
    *,
    error_message: str | None = None,
    skip_reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "update job_runs set status = :status, finished_at = :finished_at, "
                "error_message = :error_message, skip_reason = :skip_reason, "
                "details = :details where id = :id"
            ).bindparams(bindparam("finished_at", type_=_TS)),
            {
                "status": status,
                "finished_at": _now(),
                "error_message": error_message,
                "skip_reason": skip_reason,
                "details": json.dumps(details or {}, default=str),
                "id": run_id,
            },
        )


def complete_job_run(run_id: str, engine: Engine, details: dict[str, Any] | None = None) -> None:
    _finish(run_id, COMPLETED, engine, details=details)


def fail_job_run(
    run_id: str,
    error_message: str,
    engine: Engine,
    details: dict[str, Any] | None = None,
) -> None:
    _finish(run_id, FAILED, engine, error_message=error_message[:_ERROR_LIMIT], details=details)


def record_skipped(
    run_id: str,
    skip_reason: str,
    engine: Engine,
    details: dict[str, Any] | None = None,
) -> None:
    """Close an execution that did no work: completed with its skip_reason."""
    _finish(run_id, COMPLETED, engine, skip_reason=skip_reason, details=details)


def fail_stale_processing(
    job_name: str,
    engine: Engine,
    stale_after: timedelta = DEFAULT_STALE_AFTER,
) -> int:
    """Close as failed the processing rows abandoned by a killed process."""
    now = _now()
    with engine.begin() as connection:
        result = connection.execute(
            text(
                "update job_runs set status = :failed, finished_at = :now, "
                "error_message = :message where job_name = :job_name "
                "and status = :processing and started_at < :cutoff"
            ).bindparams(bindparam("now", type_=_TS), bindparam("cutoff", type_=_TS)),
            {
                "failed": FAILED,
                "now": now,
                "message": f"abandoned: still processing after {stale_after}",
                "job_name": job_name,
                "processing": PROCESSING,
                "cutoff": now - stale_after,
            },
        )
    return int(result.rowcount or 0)


def get_job_run(run_id: str, engine: Engine) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    "select id, job_name, target_date, status, skip_reason, started_at, "
                    "finished_at, error_message, details, created_at "
                    "from job_runs where id = :id"
                ),
                {"id": run_id},
            )
            .mappings()
            .first()
        )
    if row is None:
        return None
    run = dict(row)
    run["id"] = _text_id(run["id"])
    if isinstance(run["target_date"], str):
        run["target_date"] = date.fromisoformat(run["target_date"][:10])
    details = run["details"]
    run["details"] = json.loads(details) if isinstance(details, str) else (details or {})
    return run


# ------------------------------------------------------- state machine

def run_job(
    job_name: str,
    target_date: date,
    work: Callable[[], dict[str, Any]],
    engine: Engine,
    *,
    stale_after: timedelta = DEFAULT_STALE_AFTER,
    log: logging.Logger | None = None,
) -> JobOutcome:
    """Run `work` once for (job_name, target_date) through the job_runs state machine.

    * The day already completed -> skipped as duplicate (work is not called).
    * Another execution in processing -> skipped as locked, silently.
    * work() raises -> failed with the message, and the exception propagates.
    """
    events = job_log(job_name, log)
    abandoned = fail_stale_processing(job_name, engine, stale_after)
    if abandoned:
        events.error(FAILED, "closed %d abandoned processing run(s) as failed", abandoned)

    run_id = create_job_run(job_name, target_date, engine)
    events.info(PENDING, "run %s created for target_date=%s", run_id, target_date)

    if has_completed_for_date(job_name, target_date, engine):
        record_skipped(run_id, SKIP_DUPLICATE, engine)
        events.info(COMPLETED, "skipped: target_date=%s was already completed", target_date)
        return JobOutcome(run_id, COMPLETED, SKIP_DUPLICATE)

    active = has_processing_lock(job_name, engine)
    if active is None:
        try:
            start_processing(run_id, job_name, engine)
        except JobLocked as locked:
            active = locked.active_run_id or "unknown"
    if active is not None:
        details = {"active_run_id": active}
        record_skipped(run_id, SKIP_LOCKED, engine, details)
        events.info(COMPLETED, "skipped: run %s is already processing", active)
        return JobOutcome(run_id, COMPLETED, SKIP_LOCKED, details)

    status = PROCESSING
    try:
        # Another instance may have completed the day between the first check and
        # taking the lock: check again now that this execution holds it.
        if has_completed_for_date(job_name, target_date, engine):
            record_skipped(run_id, SKIP_DUPLICATE, engine)
            status = COMPLETED
            events.info(status, "skipped: target_date=%s was already completed", target_date)
            return JobOutcome(run_id, status, SKIP_DUPLICATE)

        events.info(PROCESSING, "started for target_date=%s", target_date)
        details = work() or {}
        complete_job_run(run_id, engine, details)
        status = COMPLETED
        events.info(status, "finished for target_date=%s %s", target_date, json.dumps(details, default=str))
        return JobOutcome(run_id, status, details=details)
    except BaseException as exc:  # also SystemExit/KeyboardInterrupt: never leave processing
        message = f"{type(exc).__name__}: {exc}"
        fail_job_run(run_id, message, engine)
        status = FAILED
        events.error(status, "failed for target_date=%s: %s", target_date, message, exc_info=exc)
        exc.job_run_recorded = True  # callers know it is already in job_runs and in the log
        raise
    finally:
        if status == PROCESSING:  # last line of defence: the row must not stay in processing
            try:
                fail_job_run(run_id, "interrupted before reaching a final state", engine)
            except Exception:
                events.error(PROCESSING, "could not close run %s", run_id, exc_info=True)
