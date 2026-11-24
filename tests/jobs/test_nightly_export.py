"""Tests of the nightly job (scripts/nightly_export.py) and services/job_runner.

In-memory SQLite with the same job_runs table (and its partial unique index)
as services/job_runner/sql/job_runs.sql; the pipeline subprocess is replaced
by a fake, so no database, API or Prefect server is needed.

    uv run --group test python -m pytest tests/jobs/test_nightly_export.py
"""

from __future__ import annotations

import csv
import json
import logging
import subprocess
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import DateTime, bindparam, create_engine, text
from sqlalchemy.pool import StaticPool

from scripts import nightly_export
from services import job_runner

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TARGET = date(2026, 11, 20)

JOB_RUNS_DDL = (
    """
    create table job_runs (
      id text primary key,
      job_name text not null,
      target_date text not null,
      status text not null default 'pending'
        check (status in ('pending', 'processing', 'completed', 'failed')),
      skip_reason text check (skip_reason in ('duplicate', 'locked')),
      started_at text,
      finished_at text,
      error_message text,
      details text not null default '{}',
      created_at text not null,
      check (skip_reason is null or status = 'completed')
    )
    """,
    "create index ix_job_runs_job_name_target_date on job_runs (job_name, target_date)",
    "create unique index ux_job_runs_one_processing on job_runs (job_name) where status = 'processing'",
    """
    create table telemetry_events (
      id text primary key, "timestamp" text not null, service text not null,
      event_type text not null, level text, value real, message text, tags text
    )
    """,
)


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as connection:
        for statement in JOB_RUNS_DDL:
            connection.exec_driver_sql(statement)
    yield engine
    engine.dispose()


def add_event(engine, ts: datetime, event_type="inbound_order_created", **tags):
    with engine.begin() as connection:
        connection.execute(
            text(
                'insert into telemetry_events (id, "timestamp", service, event_type, level, tags) '
                "values (:id, :ts, 'backoffice', :type, 'info', :tags)"
            ).bindparams(bindparam("ts", type_=DateTime(timezone=True))),
            {"id": str(uuid.uuid4()), "ts": ts, "type": event_type, "tags": json.dumps(tags)},
        )


@pytest.fixture
def events(engine):
    """Two events on TARGET and one on each neighbouring day (UTC)."""
    add_event(engine, datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc), location_id=1)
    add_event(engine, datetime(2026, 11, 20, 23, 59, 59, tzinfo=timezone.utc), location_id=4)
    add_event(engine, datetime(2026, 11, 19, 23, 59, 59, tzinfo=timezone.utc), location_id=2)
    add_event(engine, datetime(2026, 11, 21, 0, 0, tzinfo=timezone.utc), location_id=3)


class FakePipeline:
    def __init__(self, error: BaseException | None = None):
        self.calls: list[date] = []
        self.error = error

    def __call__(self, target_date: date) -> dict:
        self.calls.append(target_date)
        if self.error is not None:
            raise self.error
        return {"pipeline_exit_code": 0, "pipeline_run_id": "pipeline-run-1"}


def runs(engine) -> list[dict]:
    with engine.connect() as connection:
        rows = connection.execute(
            text("select id from job_runs order by created_at, rowid")
        ).scalars()
        return [job_runner.get_job_run(run_id, engine) for run_id in rows]


def run(engine, tmp_path, pipeline=None):
    return nightly_export.nightly_export(engine, TARGET, tmp_path, pipeline or FakePipeline())


# ---------------------------------------------------------------- target date

def test_target_date_defaults_to_yesterday_in_utc_and_can_be_overridden():
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    assert nightly_export.resolve_target_date({}) == yesterday
    assert nightly_export.resolve_target_date({"TARGET_DATE": "2026-11-20"}) == TARGET
    with pytest.raises(SystemExit, match="YYYY-MM-DD"):
        nightly_export.resolve_target_date({"TARGET_DATE": "20/11/2026"})


# ----------------------------------------------- state machine and CSV backup

def test_successful_run_exports_the_day_launches_pipeline_and_completes(engine, events, tmp_path):
    pipeline = FakePipeline()
    outcome = run(engine, tmp_path, pipeline)

    assert outcome.status == "completed" and outcome.skip_reason is None
    assert pipeline.calls == [TARGET]

    path = tmp_path / "telemetry_2026-11-20.csv"
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [json.loads(row["tags"])["location_id"] for row in rows] == [1, 4]  # only that UTC day
    assert list(rows[0]) == nightly_export.CSV_COLUMNS

    [record] = runs(engine)
    assert record["status"] == "completed"
    assert record["target_date"] == TARGET
    assert record["started_at"] and record["finished_at"] and record["error_message"] is None
    assert record["details"]["csv_rows"] == 2
    assert record["details"]["pipeline_run_id"] == "pipeline-run-1"


def test_day_without_events_still_writes_a_header_only_csv(engine, tmp_path):
    run(engine, tmp_path)
    content = (tmp_path / "telemetry_2026-11-20.csv").read_text(encoding="utf-8")
    assert content.strip() == ",".join(nightly_export.CSV_COLUMNS)


# ------------------------------------------------------------ idempotency

def test_second_run_on_the_same_day_is_a_no_op(engine, events, tmp_path):
    pipeline = FakePipeline()
    run(engine, tmp_path, pipeline)
    path = tmp_path / "telemetry_2026-11-20.csv"
    first_csv = path.read_bytes()

    outcome = run(engine, tmp_path, pipeline)

    assert outcome.skip_reason == "duplicate"
    assert pipeline.calls == [TARGET]  # the pipeline ran only once
    assert path.read_bytes() == first_csv
    assert len(list(tmp_path.glob("*.csv"))) == 1
    assert [(r["status"], r["skip_reason"]) for r in runs(engine)] == [
        ("completed", None),
        ("completed", "duplicate"),
    ]


def test_existing_csv_is_never_overwritten(engine, events, tmp_path):
    path = tmp_path / "telemetry_2026-11-20.csv"
    path.write_text("already exported\n", encoding="utf-8")

    outcome = run(engine, tmp_path)

    assert outcome.status == "completed"
    assert path.read_text(encoding="utf-8") == "already exported\n"
    assert outcome.details["csv_written"] is False


def test_another_day_is_not_a_duplicate(engine, events, tmp_path):
    run(engine, tmp_path)
    other = nightly_export.nightly_export(engine, date(2026, 11, 21), tmp_path, FakePipeline())
    assert other.skip_reason is None
    assert (tmp_path / "telemetry_2026-11-21.csv").exists()


# ----------------------------------------------------- lock (processing state)

def test_second_instance_aborts_silently_while_one_is_processing(engine, events, tmp_path):
    active = job_runner.create_job_run("nightly_export", TARGET, engine)
    job_runner.start_processing(active, "nightly_export", engine)
    pipeline = FakePipeline()

    outcome = run(engine, tmp_path, pipeline)  # does not raise

    assert outcome.status == "completed" and outcome.skip_reason == "locked"
    assert outcome.details == {"active_run_id": active}
    assert pipeline.calls == []
    assert not list(tmp_path.glob("*.csv"))
    assert job_runner.get_job_run(active, engine)["status"] == "processing"  # untouched


def test_processing_transition_is_atomic_for_two_simultaneous_instances(engine):
    first = job_runner.create_job_run("nightly_export", TARGET, engine)
    second = job_runner.create_job_run("nightly_export", TARGET, engine)
    job_runner.start_processing(first, "nightly_export", engine)

    with pytest.raises(job_runner.JobLocked) as raised:
        job_runner.start_processing(second, "nightly_export", engine)

    assert raised.value.active_run_id == first
    assert job_runner.get_job_run(second, engine)["status"] == "pending"


def test_lock_is_released_after_the_run_finishes(engine, events, tmp_path):
    run(engine, tmp_path)
    assert job_runner.has_processing_lock("nightly_export", engine) is None


# ----------------------------------------------------- failures never stay processing

def test_pipeline_failure_marks_the_run_failed_and_propagates(engine, events, tmp_path):
    pipeline = FakePipeline(error=RuntimeError("pipeline exited with code 3"))

    with pytest.raises(RuntimeError, match="code 3"):
        run(engine, tmp_path, pipeline)

    [record] = runs(engine)
    assert record["status"] == "failed"
    assert record["error_message"] == "RuntimeError: pipeline exited with code 3"
    assert record["finished_at"] is not None
    assert job_runner.has_processing_lock("nightly_export", engine) is None


def test_a_failed_day_is_retried_and_reuses_the_csv(engine, events, tmp_path):
    with pytest.raises(RuntimeError):
        run(engine, tmp_path, FakePipeline(error=RuntimeError("database timeout")))
    path = tmp_path / "telemetry_2026-11-20.csv"
    first_csv = path.read_bytes()

    retry = FakePipeline()
    outcome = run(engine, tmp_path, retry)

    assert outcome.status == "completed" and outcome.skip_reason is None
    assert retry.calls == [TARGET]
    assert path.read_bytes() == first_csv
    assert [r["status"] for r in runs(engine)] == ["failed", "completed"]


def test_stop_signal_during_the_run_ends_failed_not_processing(engine, events, tmp_path):
    with pytest.raises(SystemExit):
        run(engine, tmp_path, FakePipeline(error=SystemExit("stopped by signal 15")))

    [record] = runs(engine)
    assert record["status"] == "failed"
    assert "signal 15" in record["error_message"]


def test_export_failure_leaves_no_partial_csv(engine, tmp_path, monkeypatch):
    def broken_value(column, value):
        raise ValueError("corrupt row")

    add_event(engine, datetime(2026, 11, 20, 12, tzinfo=timezone.utc), location_id=1)
    monkeypatch.setattr(nightly_export, "_csv_value", broken_value)

    with pytest.raises(ValueError):
        run(engine, tmp_path)

    assert list(tmp_path.iterdir()) == []
    assert runs(engine)[0]["status"] == "failed"


def test_abandoned_processing_row_is_closed_as_failed(engine, events, tmp_path):
    zombie = job_runner.create_job_run("nightly_export", TARGET, engine)
    job_runner.start_processing(zombie, "nightly_export", engine)
    with engine.begin() as connection:  # killed with SIGKILL three hours ago
        connection.execute(
            text("update job_runs set started_at = :old where id = :id").bindparams(
                bindparam("old", type_=DateTime(timezone=True))
            ),
            {"old": datetime.now(timezone.utc) - timedelta(hours=3), "id": zombie},
        )

    outcome = run(engine, tmp_path)

    assert job_runner.get_job_run(zombie, engine)["status"] == "failed"
    assert outcome.status == "completed" and outcome.skip_reason is None


# ------------------------------------------------------------- observability

def test_every_log_line_has_timestamp_job_name_and_status(engine, events, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    run(engine, tmp_path)
    run(engine, tmp_path)  # duplicate
    with pytest.raises(RuntimeError):
        nightly_export.nightly_export(
            engine, date(2026, 11, 21), tmp_path, FakePipeline(error=RuntimeError("boom"))
        )

    formatter = logging.Formatter(nightly_export.LOG_FORMAT)
    lines = [formatter.format(record) for record in caplog.records]
    assert all(" job=nightly_export status=" in line for line in lines)
    assert any("INFO" in line and "status=completed" in line and "finished" in line for line in lines)
    assert any("INFO" in line and "already completed" in line for line in lines)
    assert any("ERROR" in line and "status=failed" in line and "boom" in line for line in lines)
    assert all(line[:4].isdigit() for line in lines)  # starts with the timestamp


# ------------------------------------------------------------ independence

def test_pipeline_summary_is_parsed_from_the_subprocess_output():
    stdout = 'prefect log line\n{\n  "run_id": "abc",\n  "status": "completed"\n}\nStopping server\n'
    assert nightly_export._pipeline_result(stdout) == {"run_id": "abc", "status": "completed"}
    assert nightly_export._pipeline_result("no json here") == {}


def test_script_is_a_standalone_process_that_never_loads_fastapi():
    code = (
        "import runpy, sys; "
        f"runpy.run_path({str(REPOSITORY_ROOT / 'scripts' / 'nightly_export.py')!r}, run_name='check'); "
        "print('fastapi' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=REPOSITORY_ROOT
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
