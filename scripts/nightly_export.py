"""Nightly telemetry job (ticket DEV-53): CSV backup of a day + business pipeline.

For the target day (yesterday in UTC, or TARGET_DATE=YYYY-MM-DD):

1. Exports the rows of telemetry_events of that day to
   data/raw/telemetry_YYYY-MM-DD.csv, only if the file does not exist yet. The
   CSV is a backup for audit and recovery: the pipeline does NOT read it.
2. Launches the business performance pipeline (data/pipelines/pipeline.py) as
   a subprocess. The pipeline reads telemetry_events from the database and
   records its own phases in reporting.pipeline_runs.
3. Records the execution in public.job_runs through services/job_runner:
   pending -> processing -> completed | failed. The processing state is the
   lock (a second instance aborts silently) and a completed row for
   (nightly_export, target_date) makes a re-run a no-op.

It is a standalone process: it never imports FastAPI nor runs inside the API.
The trigger is the cron of the dedicated scheduler container
(scripts/scheduler/crontab), every day at 02:00 UTC.

    python scripts/nightly_export.py
    TARGET_DATE=2026-11-20 python scripts/nightly_export.py

Exit code: 0 completed or skipped (duplicate / locked), 1 failed.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import signal
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from time import gmtime
from typing import Any, Callable

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from sqlalchemy import DateTime, bindparam, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from services import job_runner  # noqa: E402

JOB_NAME = "nightly_export"
RAW_DIR = REPOSITORY_ROOT / "data" / "raw"
PIPELINE_SCRIPT = REPOSITORY_ROOT / "data" / "pipelines" / "pipeline.py"
PIPELINE_TIMEOUT_SECONDS = int(os.environ.get("PIPELINE_TIMEOUT_SECONDS", "1800"))
CSV_COLUMNS = ["id", "timestamp", "service", "event_type", "level", "value", "message", "tags"]
LOG_FORMAT = "%(asctime)s %(levelname)s job=%(job_name)s status=%(status)s %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%SZ"

_TS = DateTime(timezone=True)
log = logging.getLogger("scripts.nightly_export")


def resolve_target_date(environ: dict[str, str] | None = None) -> date:
    """TARGET_DATE (YYYY-MM-DD) if set; otherwise yesterday in UTC."""
    value = (environ if environ is not None else os.environ).get("TARGET_DATE", "").strip()
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise SystemExit(f"TARGET_DATE must be YYYY-MM-DD, got {value!r}") from None
    return datetime.now(timezone.utc).date() - timedelta(days=1)


def csv_path_for(target_date: date, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / f"telemetry_{target_date.isoformat()}.csv"


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(path)


def _csv_value(column: str, value: Any) -> Any:
    if value is None:
        return ""
    if column == "tags":
        parsed = json.loads(value) if isinstance(value, str) else value
        return json.dumps(parsed, sort_keys=True, ensure_ascii=False)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def export_telemetry_csv(engine: Engine, target_date: date, raw_dir: Path = RAW_DIR) -> dict[str, Any]:
    """Write the telemetry_events rows of target_date (UTC) to CSV, if not done yet.

    The file is written to a temporary name and renamed at the end, so a crash
    never leaves a half-written CSV that a later run would take as done.
    """
    path = csv_path_for(target_date, raw_dir)
    if path.exists():
        return {"csv_path": _display_path(path), "csv_written": False, "csv_rows": None}

    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    query = text(
        'select id, "timestamp", service, event_type, level, value, message, tags '
        'from telemetry_events where "timestamp" >= :start and "timestamp" < :end '
        'order by "timestamp", id'
    ).bindparams(bindparam("start", type_=_TS), bindparam("end", type_=_TS))

    raw_dir.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".csv.partial")
    rows = 0
    try:
        with engine.connect() as connection, open(partial, "w", newline="", encoding="utf-8") as handle:
            if engine.dialect.name == "postgresql":
                connection.execute(text("SET TRANSACTION READ ONLY"))
            writer = csv.writer(handle)
            writer.writerow(CSV_COLUMNS)
            result = connection.execute(query, {"start": start, "end": start + timedelta(days=1)})
            for row in result.mappings():
                writer.writerow([_csv_value(column, row[column]) for column in CSV_COLUMNS])
                rows += 1
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    return {"csv_path": _display_path(path), "csv_written": True, "csv_rows": rows}


def _pipeline_result(stdout: str) -> dict[str, Any]:
    """The JSON summary that pipeline.py prints last (run_id, status, rows...)."""
    lines = stdout.splitlines()
    starts = [index for index, line in enumerate(lines) if line == "{"]
    if not starts:
        return {}
    block = lines[starts[-1] :]
    end = next((index for index, line in enumerate(block) if line == "}"), None)
    if end is None:
        return {}
    try:
        return json.loads("\n".join(block[: end + 1]))
    except ValueError:
        return {}


def run_pipeline(target_date: date) -> dict[str, Any]:
    """Launch the business performance pipeline as a separate process."""
    command = [
        sys.executable,
        str(PIPELINE_SCRIPT),
        "--reference-date",
        target_date.isoformat(),
        "--trigger-type",
        "schedule",
    ]
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=PIPELINE_TIMEOUT_SECONDS,
    )
    result = _pipeline_result(completed.stdout)
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout).strip().splitlines()[-5:]
        raise RuntimeError(
            f"pipeline exited with code {completed.returncode}"
            f" (status={result.get('status', 'unknown')}): {' | '.join(tail)}"
        )
    return {
        "pipeline_exit_code": completed.returncode,
        "pipeline_run_id": result.get("run_id"),
        "pipeline_status": result.get("status"),
    }


def nightly_export(
    engine: Engine,
    target_date: date,
    raw_dir: Path = RAW_DIR,
    pipeline_runner: Callable[[date], dict[str, Any]] = run_pipeline,
) -> job_runner.JobOutcome:
    """Run the nightly job for target_date through the job_runs state machine."""

    def work() -> dict[str, Any]:
        details = export_telemetry_csv(engine, target_date, raw_dir)
        details.update(pipeline_runner(target_date))
        return details

    return job_runner.run_job(JOB_NAME, target_date, work, engine, log=log)


def _raise_on_stop_signal(signum: int, _frame: Any) -> None:
    # Turn SIGTERM (docker stop, cron kill) into an exception so the row ends failed.
    raise SystemExit(f"stopped by signal {signum}")


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)
    formatter.converter = gmtime  # timestamps in UTC, like target_date
    handler.setFormatter(formatter)
    for name in ("scripts.nightly_export", "services.job_runner"):
        logger = logging.getLogger(name)
        logger.handlers[:] = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False


def main() -> int:
    configure_logging()
    signal.signal(signal.SIGTERM, _raise_on_stop_signal)
    target_date = resolve_target_date()

    events = job_runner.job_log(JOB_NAME, log)

    try:
        from data.pipelines import db  # DATABASE_URL (env, services/api/.env or Prefect Secret)

        engine = db.get_engine()
    except Exception as exc:
        # Without a database there is no job_runs row to write: log it and fail.
        events.error(job_runner.FAILED, "database is not configured: %s", exc)
        return 1

    try:
        nightly_export(engine, target_date)
    except BaseException as exc:
        if not getattr(exc, "job_run_recorded", False):
            # Failed before a run could be recorded (e.g. the database is unreachable).
            events.error(job_runner.FAILED, "aborted before recording a run: %s: %s", type(exc).__name__, exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
