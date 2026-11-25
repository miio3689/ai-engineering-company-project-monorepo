"""State of the asynchronous Celery tasks (ticket DEV-55)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel

from services.api.auth_security import get_current_user
from services.api.models import UserResponse
from services.celery_app import celery_app

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = logging.getLogger("api.tasks")


class TaskStatus(BaseModel):
    task_id: str
    # Celery state in lower case: pending, started, retry, success or failure.
    # Celery reports an unknown or expired task id as pending too.
    status: str
    result: Any = None


def _result(state: str, task: AsyncResult) -> Any:
    if state == "SUCCESS":
        return task.result
    if state in {"FAILURE", "RETRY"}:
        error = task.result  # the exception of the last attempt
        return {"error": f"{type(error).__name__}: {error}"} if error is not None else None
    return None


@router.get("/{task_id}", response_model=TaskStatus)
def get_task_status(
    task_id: str = Path(description="task_id devuelto por el endpoint que encoló la tarea."),
    _current_user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Current state of a task and its result once it is available (read from Redis)."""
    try:
        uuid.UUID(task_id)
    except ValueError as exc:
        raise HTTPException(422, "task_id no válido.") from exc

    task = AsyncResult(task_id, app=celery_app)
    try:
        state = task.state
        result = _result(state, task)
    except Exception as exc:  # Redis unreachable
        logger.error("Could not read task state (type: %s).", type(exc).__name__)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "La cola de tareas no está disponible."
        ) from exc
    return {"task_id": task_id, "status": state.lower(), "result": result}
