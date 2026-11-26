"""Dead Letter Queue: tasks that exhausted their retries (public.task_dead_letters)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, bindparam, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

_TS = DateTime(timezone=True)


def _engine(engine: Engine | None) -> Engine:
    if engine is not None:
        return engine
    from data.pipelines import db  # DATABASE_URL, loaded only in the worker

    return db.get_engine()


def record_dead_letter(
    *,
    task_id: str,
    task_name: str,
    attempt: int,
    error_message: str,
    traceback: str | None = None,
    task_kwargs: dict[str, Any] | None = None,
    engine: Engine | None = None,
) -> bool:
    """Store a permanently failed task. Returns False if it was already stored."""
    engine = _engine(engine)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "insert into task_dead_letters (id, task_id, task_name, attempt, "
                    "error_message, traceback, task_kwargs, failed_at) values (:id, "
                    ":task_id, :task_name, :attempt, :error_message, :traceback, "
                    ":task_kwargs, :failed_at)"
                ).bindparams(bindparam("failed_at", type_=_TS)),
                {
                    "id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "task_name": task_name,
                    "attempt": attempt,
                    "error_message": error_message,
                    "traceback": traceback,
                    "task_kwargs": json.dumps(task_kwargs or {}, default=str),
                    "failed_at": datetime.now(timezone.utc),
                },
            )
    except IntegrityError:  # redelivered message: already in the DLQ
        return False
    return True


def get_dead_letter(task_id: str, engine: Engine | None = None) -> dict[str, Any] | None:
    with _engine(engine).connect() as connection:
        row = (
            connection.execute(
                text(
                    "select task_id, task_name, attempt, error_message, traceback, "
                    "task_kwargs, failed_at from task_dead_letters where task_id = :task_id"
                ),
                {"task_id": task_id},
            )
            .mappings()
            .first()
        )
    if row is None:
        return None
    entry = dict(row)
    kwargs = entry["task_kwargs"]
    entry["task_kwargs"] = json.loads(kwargs) if isinstance(kwargs, str) else (kwargs or {})
    return entry
