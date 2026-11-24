"""State control of background jobs (table public.job_runs).

Independent of FastAPI: it only needs a SQLAlchemy engine, so the nightly
scripts in scripts/ use it in their own process, never in the API process.
"""

from .job_runner import (
    COMPLETED,
    FAILED,
    PENDING,
    PROCESSING,
    JobLocked,
    JobOutcome,
    complete_job_run,
    create_job_run,
    fail_job_run,
    fail_stale_processing,
    get_job_run,
    has_completed_for_date,
    has_processing_lock,
    job_log,
    record_skipped,
    run_job,
    start_processing,
)

__all__ = [
    "COMPLETED",
    "FAILED",
    "PENDING",
    "PROCESSING",
    "JobLocked",
    "JobOutcome",
    "complete_job_run",
    "create_job_run",
    "fail_job_run",
    "fail_stale_processing",
    "get_job_run",
    "has_completed_for_date",
    "has_processing_lock",
    "job_log",
    "record_skipped",
    "run_job",
    "start_processing",
]
