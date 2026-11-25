"""Business performance pipeline as a Celery task (ticket DEV-55).

POST /reporting/pipeline-runs only enqueues this task with two small values
(reference date and number of weeks) and answers 202 with the task id. The
worker opens the run in reporting.pipeline_runs (taking its lock) and runs
data/pipelines/pipeline.py in its own process, so Prefect and Pandas never run
inside the API. pipeline_runs keeps recording the ETL phases; the Celery result
carries the run id and the row counts.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from services.async_tasks.base import TrackedTask, logger
from services.celery_app import TASK_SOFT_TIME_LIMIT, celery_app

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_SCRIPT = REPOSITORY_ROOT / "data" / "pipelines" / "pipeline.py"
# The pipeline process gets less time than the task, so a timeout is handled here.
PIPELINE_TIMEOUT_SECONDS = int(
    os.environ.get("PIPELINE_TIMEOUT_SECONDS", str(max(TASK_SOFT_TIME_LIMIT - 60, 1)))
)
TASK_NAME = "reporting.run_weekly_location_performance"


def pipeline_command(run_id: str, reference_date: str | None, lookback_weeks: int) -> list[str]:
    command = [
        sys.executable,
        str(PIPELINE_SCRIPT),
        "--run-id",
        run_id,
        "--trigger-type",
        "manual",
        "--lookback-weeks",
        str(lookback_weeks),
    ]
    if reference_date:
        command += ["--reference-date", reference_date]
    return command


def _summary(stdout: str) -> dict[str, Any]:
    """The JSON summary that pipeline.py prints last (run_id, status, rows...)."""
    lines = stdout.splitlines()
    starts = [index for index, line in enumerate(lines) if line == "{"]
    if not starts:
        return {}
    block = lines[starts[-1] :]
    end = next((index for index, line in enumerate(block) if line == "}"), None)
    try:
        return json.loads("\n".join(block[: end + 1])) if end is not None else {}
    except ValueError:
        return {}


def run_pipeline_process(run_id: str, reference_date: str | None, lookback_weeks: int) -> dict[str, Any]:
    """Run the flow for an already opened run; raise if it does not complete."""
    completed = subprocess.run(
        pipeline_command(run_id, reference_date, lookback_weeks),
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=PIPELINE_TIMEOUT_SECONDS,
    )
    summary = _summary(completed.stdout)
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout).strip().splitlines()[-5:]
        raise RuntimeError(
            f"pipeline exited with code {completed.returncode}"
            f" (status={summary.get('status', 'unknown')}): {' | '.join(tail)}"
        )
    return summary


@celery_app.task(bind=True, base=TrackedTask, name=TASK_NAME)
def run_weekly_location_performance(
    self: TrackedTask,
    reference_date: str | None = None,
    lookback_weeks: int = 4,
) -> dict[str, Any]:
    """Recompute the weekly KPIs. Retried 3 times with backoff; then the DLQ."""
    from data.pipelines import runs
    from data.process.weekly_location_performance import compute_window

    day = date.fromisoformat(reference_date) if reference_date else None
    window_start, window_end = compute_window(day, lookback_weeks)
    try:
        run_id = runs.open_run(
            trigger_type="manual", window_start=window_start, window_end=window_end
        )
    except runs.PipelineLocked as locked:
        # Not an error: another run (the cron or another request) is computing
        # the same table right now. Same outcome as the flow's skipped_locked.
        logger.info(
            "task_id=%s run %s is already running: skipped", self.request.id, locked.active_run_id
        )
        return {"status": "skipped_locked", "active_run_id": locked.active_run_id}
    except Exception as exc:  # database unreachable: retry with backoff
        self.retry_with_backoff(exc)

    try:
        summary = run_pipeline_process(run_id, reference_date, lookback_weeks)
    except Exception as exc:
        # If the process died or timed out before closing its run, close it so
        # the lock is released for the next attempt.
        try:
            runs.fail_run_if_running(run_id, f"celery task {self.request.id}: {type(exc).__name__}: {exc}")
        except Exception:
            logger.exception("task_id=%s could not close run %s", self.request.id, run_id)
        self.retry_with_backoff(exc)
    return {"run_id": run_id, **summary}


def enqueue_pipeline_run(reference_date: date | None, lookback_weeks: int) -> str:
    """Producer side (API): put a light message in Redis and return the task id.

    Fails fast (about 1 s) if Redis is unreachable, so the API answers 503
    instead of hanging.
    """
    result = run_weekly_location_performance.apply_async(
        kwargs={
            "reference_date": reference_date.isoformat() if reference_date else None,
            "lookback_weeks": lookback_weeks,
        },
        retry=True,
        retry_policy={"max_retries": 1, "interval_start": 0, "interval_step": 0.5},
    )
    return result.id
