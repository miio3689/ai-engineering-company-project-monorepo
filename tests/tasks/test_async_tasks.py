"""Tests of the Celery tasks (ticket DEV-55) without Redis nor a real database.

Tasks are executed in-process with `task.apply()` (Celery's eager mode, where a
retry runs again immediately instead of after its countdown); the database is
in-memory SQLite and the pipeline subprocess is replaced by a fake.

    uv run --group test python -m pytest tests/tasks/test_async_tasks.py
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from data.pipelines import runs
# First: services.api.tests sets the fake JWT_SECRET_KEY that the API needs to import.
from services.api.tests.pipeline_helpers import create_schema, make_engine
from services.api.app import main
from services.api.auth_security import get_current_user
from services.api.models import UserResponse
from services.api.routes import tasks as tasks_route
from services.async_tasks import base, dead_letters, pipeline_tasks
from services.celery_app import celery_app

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TASK = pipeline_tasks.run_weekly_location_performance
TASK_ID = "6f1c2b0e-8d4a-4c55-9b7e-2a9d3e4f5a60"


@pytest.fixture
def engine():
    engine = make_engine()
    create_schema(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            create table task_dead_letters (
              id text primary key, task_id text not null unique, task_name text not null,
              attempt integer not null, error_message text not null, traceback text,
              task_kwargs text not null default '{}', failed_at text not null
            )
            """
        )
    with patch("data.pipelines.db.get_engine", return_value=engine):
        yield engine
    engine.dispose()


class FakePipeline:
    """Replaces the pipeline subprocess; fails the first `failures` calls."""

    def __init__(self, failures: int = 0, error: Exception | None = None):
        self.failures = failures
        self.error = error or RuntimeError("pipeline exited with code 1: database timeout")
        self.calls: list[tuple] = []

    def __call__(self, run_id, reference_date, lookback_weeks):
        self.calls.append((run_id, reference_date, lookback_weeks))
        if len(self.calls) <= self.failures:
            raise self.error
        runs.close_run(run_id=run_id, status="completed", phase="close")
        return {"run_id": run_id, "status": "completed", "rows_inserted": 56}


def apply(fake: FakePipeline, **kwargs):
    with patch.object(pipeline_tasks, "run_pipeline_process", side_effect=fake):
        return TASK.apply(kwargs={"reference_date": "2026-11-16", "lookback_weeks": 4, **kwargs}, task_id=TASK_ID)


def running_runs(engine) -> int:
    with engine.connect() as connection:
        return connection.exec_driver_sql(
            "select count(*) from reporting.pipeline_runs where status = 'running'"
        ).scalar()


# -------------------------------------------------------------- task logic

def test_task_runs_the_pipeline_for_its_own_run_and_returns_the_summary(engine):
    fake = FakePipeline()
    result = apply(fake)

    assert result.state == "SUCCESS"
    assert result.result["status"] == "completed"
    assert result.result["rows_inserted"] == 56
    [(run_id, reference_date, lookback)] = fake.calls
    assert result.result["run_id"] == run_id
    assert (reference_date, lookback) == ("2026-11-16", 4)
    assert runs.get_latest_run(engine=engine)["trigger_type"] == "manual"


def test_failed_attempt_is_retried_and_then_succeeds_without_dlq(engine):
    fake = FakePipeline(failures=1)
    result = apply(fake)

    assert result.state == "SUCCESS"
    assert len(fake.calls) == 2
    assert fake.calls[0][0] != fake.calls[1][0]  # every attempt opens its own run
    assert dead_letters.get_dead_letter(TASK_ID) is None
    assert running_runs(engine) == 0  # the failed attempt released its lock


def test_three_retries_with_exponential_backoff_then_dead_letter_queue(engine, caplog):
    caplog.set_level(logging.INFO, logger="services.async_tasks")
    fake = FakePipeline(failures=10)
    result = apply(fake)

    assert result.state == "FAILURE"
    assert len(fake.calls) == 4  # initial attempt + max_retries=3

    retries = [r.getMessage() for r in caplog.records if "state=retry" in r.getMessage()]
    assert [line.split("next_attempt_in=")[1].split("s ")[0] for line in retries] == ["10", "20", "40"]
    assert all("database timeout" in line for line in retries)

    entry = dead_letters.get_dead_letter(TASK_ID)
    assert entry["attempt"] == 4
    assert entry["task_name"] == "reporting.run_weekly_location_performance"
    assert entry["error_message"] == "RuntimeError: pipeline exited with code 1: database timeout"
    assert "Traceback" in entry["traceback"]
    assert entry["task_kwargs"] == {"reference_date": "2026-11-16", "lookback_weeks": 4}
    assert running_runs(engine) == 0  # no attempt left a zombie run


def test_countdown_doubles_after_every_failure():
    assert [base.retry_countdown(n, base=10) for n in range(3)] == [10, 20, 40]
    assert TASK.max_retries == 3


def test_pipeline_timeout_is_a_retried_failure(engine):
    timeout = subprocess.TimeoutExpired(cmd="pipeline.py", timeout=1)
    fake = FakePipeline(failures=1, error=timeout)
    assert apply(fake).state == "SUCCESS"
    assert len(fake.calls) == 2


def test_active_run_finishes_the_task_as_skipped_locked_without_retrying(engine):
    active = runs.open_run(
        trigger_type="schedule",
        window_start=date(2026, 10, 26),
        window_end=date(2026, 11, 23),
        engine=engine,
    )
    fake = FakePipeline()
    result = apply(fake)

    assert result.state == "SUCCESS"
    assert result.result == {"status": "skipped_locked", "active_run_id": active}
    assert fake.calls == []


def test_dead_letter_is_not_duplicated_by_a_redelivered_message(engine):
    entry = dict(task_id=TASK_ID, task_name="t", attempt=4, error_message="boom")
    assert dead_letters.record_dead_letter(**entry) is True
    assert dead_letters.record_dead_letter(**entry) is False


# ------------------------------------------------------------ observability

def test_every_log_line_has_task_id_attempt_state_and_duration(engine, caplog):
    caplog.set_level(logging.INFO, logger="services.async_tasks")
    apply(FakePipeline(failures=1))

    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("task_id=")]
    states = [line.split("state=")[1].split()[0] for line in lines]
    assert states == ["started", "retry", "started", "success"]
    assert all(f"task_id={TASK_ID}" in line for line in lines)
    assert "attempt=1/4" in lines[1] and "attempt=2/4" in lines[3]
    assert all("duration_ms=" in line for line in lines)


def test_final_failure_logs_the_full_error(engine, caplog):
    caplog.set_level(logging.INFO, logger="services.async_tasks")
    apply(FakePipeline(failures=10))
    failure = next(r for r in caplog.records if "state=failure" in r.getMessage())
    assert failure.levelno == logging.ERROR
    assert "database timeout" in failure.getMessage() and "Traceback" in failure.getMessage()


# ------------------------------------------------------- producer (the API)

def test_enqueued_message_carries_only_two_small_values():
    with patch.object(TASK, "apply_async") as apply_async:
        apply_async.return_value.id = TASK_ID
        assert pipeline_tasks.enqueue_pipeline_run(date(2026, 11, 16), 2) == TASK_ID
    kwargs = apply_async.call_args.kwargs["kwargs"]
    assert kwargs == {"reference_date": "2026-11-16", "lookback_weeks": 2}
    assert len(json.dumps(kwargs)) < 100  # ids and dates only, never data


@pytest.fixture
def client():
    user = UserResponse(
        id=7002,
        email="tasks-tests@example.com",
        is_active=True,
        role="user",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    main.app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.pop(get_current_user, None)


def test_post_answers_202_with_task_id_without_waiting(client):
    def slow_task_would_take(*_args):
        return TASK_ID  # enqueueing returns at once, whatever the task lasts

    with patch("services.reporting.router.enqueue_pipeline_run", side_effect=slow_task_would_take):
        started = time.perf_counter()
        response = client.post("/reporting/pipeline-runs", json={"lookback_weeks": 2})
        elapsed_ms = (time.perf_counter() - started) * 1000

    assert response.status_code == 202
    assert response.json()["task_id"] == TASK_ID
    assert elapsed_ms < 200


class FakeResult:
    def __init__(self, state, result=None):
        self.state = state
        self.result = result


@pytest.mark.parametrize(
    ("state", "result", "status", "payload"),
    [
        ("PENDING", None, "pending", None),
        ("STARTED", {"pid": 1}, "started", None),
        ("RETRY", RuntimeError("timeout"), "retry", {"error": "RuntimeError: timeout"}),
        ("SUCCESS", {"run_id": "r1", "status": "completed"}, "success", {"run_id": "r1", "status": "completed"}),
        ("FAILURE", RuntimeError("database timeout"), "failure", {"error": "RuntimeError: database timeout"}),
    ],
)
def test_get_task_reports_each_celery_state(client, state, result, status, payload):
    with patch.object(tasks_route, "AsyncResult", return_value=FakeResult(state, result)):
        response = client.get(f"/tasks/{TASK_ID}")
    assert response.status_code == 200
    assert response.json() == {"task_id": TASK_ID, "status": status, "result": payload}


def test_get_task_rejects_invalid_ids_and_reports_redis_outage(client):
    assert client.get("/tasks/not-a-task-id").status_code == 422

    class Broken:
        @property
        def state(self):
            raise ConnectionError("redis down")

    with patch.object(tasks_route, "AsyncResult", return_value=Broken()):
        assert client.get(f"/tasks/{TASK_ID}").status_code == 503


def test_get_task_requires_authentication():
    with TestClient(main.app) as anonymous:
        assert anonymous.get(f"/tasks/{TASK_ID}").status_code == 401


# --------------------------------------------------- configuration / worker

def test_celery_configuration_follows_the_ticket():
    conf = celery_app.conf
    assert conf.task_acks_late is True and conf.task_reject_on_worker_lost is True
    assert conf.task_track_started is True
    assert conf.task_time_limit > conf.task_soft_time_limit > 0
    assert conf.task_serializer == "json"


def test_broker_and_backend_come_from_redis_url_and_never_load_fastapi():
    code = (
        "import sys; from services.celery_app import celery_app; "
        "print(celery_app.conf.broker_url, celery_app.conf.result_backend, 'fastapi' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPOSITORY_ROOT,
        env={**__import__("os").environ, "REDIS_URL": "redis://broker.test:6379/3"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["redis://broker.test:6379/3", "redis://broker.test:6379/3", "False"]
