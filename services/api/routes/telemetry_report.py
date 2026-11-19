"""GET /telemetry/report: technical metrics computed by services/telemetry/analysis.py.

The pipeline is NOT calculated in every request: the result of each period is
kept in memory for 60 seconds (InProcessTTLCache). When no dates are sent, the
cache key is "default", so the default window (last 7 days, which moves with
the clock) also reuses the cached report. The report needs a logged-in user.
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pandas.errors import DatabaseError as PandasDatabaseError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from services.telemetry.analysis import as_utc, build_report, resolve_period

from ..auth_security import get_current_user
from ..cache import InProcessTTLCache
from ..models import UserResponse

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
logger = logging.getLogger("api.telemetry")

REPORT_CACHE_TTL_SECONDS = 60
report_cache = InProcessTTLCache()


class ReportPeriod(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str


class TelemetryReport(BaseModel):
    period: ReportPeriod
    metrics: dict[str, list[dict[str, Any]]]


def _key_part(value: datetime | None) -> str:
    return "default" if value is None else as_utc(value).isoformat()


@router.get("/report", response_model=TelemetryReport)
def get_report(
    start_date: datetime | None = Query(
        default=None,
        description="Inicio inclusivo del período, ISO 8601 (UTC). Por defecto, hace 7 días.",
    ),
    end_date: datetime | None = Query(
        default=None,
        description="Fin exclusivo del período, ISO 8601 (UTC). Por defecto, ahora.",
    ),
    _current_user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        start, end = resolve_period(start_date, end_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    cache_key = f"telemetry.report:{_key_part(start_date)}:{_key_part(end_date)}"

    def compute() -> dict[str, Any]:
        logger.info(
            "telemetry report computed: from=%s to=%s",
            start.isoformat(),
            end.isoformat(),
        )
        return build_report(start, end)

    try:
        return report_cache.get_or_set(
            cache_key, REPORT_CACHE_TTL_SECONDS, compute
        )
    except (SQLAlchemyError, PandasDatabaseError) as exc:
        logger.error(
            "Telemetry report database error (type: %s).", type(exc).__name__
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de telemetría no disponible.",
        ) from exc
