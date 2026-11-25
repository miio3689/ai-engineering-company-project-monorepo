"""Base class of the Brasaland Celery tasks: retries with backoff, logs and DLQ.

Every log line carries task_id, task name, attempt, resulting state and
duration; failures also carry the full error. A task that fails after its last
retry (or with an error that is not retried) is written to the Dead Letter
Queue (public.task_dead_letters).
"""

from __future__ import annotations

import os
import time
import traceback as traceback_module
from typing import Any, NoReturn

from celery import Task
from celery.utils.log import get_task_logger

from services.async_tasks import dead_letters

logger = get_task_logger("services.async_tasks")

MAX_RETRIES = 3
# Exponential backoff between attempts: 10 s, 20 s, 40 s (never an immediate retry).
RETRY_BASE_SECONDS = int(os.environ.get("TASK_RETRY_BASE_SECONDS", "10"))


def retry_countdown(retries_done: int, base: int | None = None) -> int:
    """Seconds to wait before the next attempt, doubling after every failure."""
    return (RETRY_BASE_SECONDS if base is None else base) * 2**retries_done


class TrackedTask(Task):
    """Celery Task with structured logs, exponential backoff and a DLQ."""

    abstract = True
    max_retries = MAX_RETRIES
    _started: dict[str, float] = {}

    # ------------------------------------------------------------ helpers

    @property
    def attempt(self) -> int:
        """1 for the first execution, 2 for the first retry, and so on."""
        return int(self.request.retries or 0) + 1

    def _duration_ms(self, task_id: str | None, pop: bool = True) -> int:
        started = (self._started.pop if pop else self._started.get)(task_id, None)
        return int((time.monotonic() - started) * 1000) if started is not None else 0

    def _log(self, level: int, state: str, task_id: str | None, duration_ms: int, extra: str = "") -> None:
        logger.log(
            level,
            "task_id=%s task=%s attempt=%d/%d state=%s duration_ms=%d%s",
            task_id,
            self.name,
            self.attempt,
            self.max_retries + 1,
            state,
            duration_ms,
            f" {extra}" if extra else "",
        )

    def retry_with_backoff(self, exc: BaseException) -> NoReturn:
        """Schedule the next attempt with exponential backoff, or fail for good."""
        task_id = self.request.id
        if self.request.retries >= self.max_retries:
            raise exc  # retries exhausted: on_failure moves it to the DLQ
        countdown = retry_countdown(self.request.retries)
        self._log(
            30,  # WARNING
            "retry",
            task_id,
            self._duration_ms(task_id),
            f"next_attempt_in={countdown}s error={type(exc).__name__}: {exc}",
        )
        raise self.retry(exc=exc, countdown=countdown)

    # -------------------------------------------------------------- hooks

    def before_start(self, task_id: str, args: Any, kwargs: Any) -> None:
        self._started[task_id] = time.monotonic()
        self._log(20, "started", task_id, 0)

    def on_success(self, retval: Any, task_id: str, args: Any, kwargs: Any) -> None:
        self._log(20, "success", task_id, self._duration_ms(task_id))

    def on_failure(self, exc: BaseException, task_id: str, args: Any, kwargs: Any, einfo: Any) -> None:
        error = f"{type(exc).__name__}: {exc}"
        trace = str(einfo) if einfo is not None else "".join(
            traceback_module.format_exception(type(exc), exc, exc.__traceback__)
        )
        self._log(40, "failure", task_id, self._duration_ms(task_id), f"error={error}\n{trace}")
        try:
            stored = dead_letters.record_dead_letter(
                task_id=task_id,
                task_name=self.name,
                attempt=self.attempt,
                error_message=error,
                traceback=trace,
                task_kwargs=dict(kwargs or {}),
            )
        except Exception:
            logger.exception("task_id=%s task=%s could not be written to the DLQ", task_id, self.name)
            return
        self._log(
            40,
            "dead_letter",
            task_id,
            0,
            "moved to the DLQ (task_dead_letters)" if stored else "already in the DLQ",
        )
