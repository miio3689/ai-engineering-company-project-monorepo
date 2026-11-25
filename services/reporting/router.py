"""Business reporting endpoints.

The ETL logic lives in data/pipelines/; this module only exposes it over HTTP.
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from data.pipelines import queries as pipeline_queries
from data.pipelines import runs as pipeline_runs
from services.api.auth_security import get_current_user
from services.api.models import UserResponse
from services.async_tasks.pipeline_tasks import enqueue_pipeline_run

from .schemas import (
    PipelineRun,
    PipelineRunRequest,
    PipelineRunTriggered,
    WeeklyLocationPerformance,
)

router = APIRouter(prefix="/reporting", tags=["reporting"])
logger = logging.getLogger("api.reporting")


def _unavailable(exc: Exception) -> HTTPException:
    logger.error("Reporting database error (type: %s).", type(exc).__name__)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Servicio de reporting no disponible.",
    )


@router.get(
    "/weekly-location-performance",
    response_model=WeeklyLocationPerformance,
)
def weekly_location_performance(
    week_start: date | None = Query(
        default=None,
        description="Lunes de la semana (UTC). Por defecto, la última semana cerrada.",
    ),
    _current_user: UserResponse = Depends(get_current_user),
) -> dict:
    """KPIs of every location for one week (consumed by the Part 3 dashboard)."""
    try:
        return pipeline_queries.get_weekly_performance(week_start=week_start)
    except (SQLAlchemyError, RuntimeError) as exc:
        raise _unavailable(exc) from exc


@router.get("/pipeline-runs/latest", response_model=PipelineRun)
def latest_pipeline_run(
    _current_user: UserResponse = Depends(get_current_user),
) -> dict:
    """Status and metadata of the latest run of the pipeline."""
    try:
        run = pipeline_runs.get_latest_run()
    except (SQLAlchemyError, RuntimeError) as exc:
        raise _unavailable(exc) from exc
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todavía no hay ninguna corrida del pipeline.",
        )
    return run


@router.post(
    "/pipeline-runs",
    response_model=PipelineRunTriggered,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_pipeline_run(
    request: PipelineRunRequest | None = None,
    _current_user: UserResponse = Depends(get_current_user),
) -> dict:
    """Manual run: enqueue it in Celery and answer 202 with the task id at once.

    The API does no pipeline nor database work here: the Celery worker opens the
    run (and its lock) and executes the flow. If another run is active the task
    finishes with status skipped_locked.
    """
    options = request or PipelineRunRequest()
    try:
        task_id = enqueue_pipeline_run(options.week_start, options.lookback_weeks)
    except Exception as exc:  # Redis unreachable
        logger.error("Could not enqueue the pipeline run (type: %s).", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La cola de tareas no está disponible.",
        ) from exc
    return {"task_id": task_id, "status": "queued", "status_url": f"/tasks/{task_id}"}
