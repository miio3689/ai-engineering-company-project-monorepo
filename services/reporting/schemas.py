"""Response and request models of the reporting endpoints."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LocationPerformance(BaseModel):
    location_id: str
    country: str
    total_purchase_cost: float
    total_waste_cost: float
    waste_ratio: float
    stockout_events_count: int
    price_alert_events_count: int
    currency: str


class WeeklyLocationPerformance(BaseModel):
    week_start: date | None
    locations: list[LocationPerformance]


class PipelineRun(BaseModel):
    run_id: str
    pipeline_name: str
    trigger_type: str
    window_start: date
    window_end: date
    status: str
    phase: str
    started_at: datetime
    finished_at: datetime | None
    rows_extracted: int | None
    rows_after_dedup: int | None
    rows_rejected: int | None
    rows_inserted: int | None
    rows_updated: int | None
    rows_unchanged: int | None
    error_message: str | None
    resumed_from_run_id: str | None
    prefect_flow_run_id: str | None
    details: dict[str, Any]


class PipelineRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week_start: date | None = Field(
        default=None,
        description="Cualquier día de la semana de referencia. Por defecto, hoy en UTC.",
    )
    lookback_weeks: int = Field(default=4, ge=1, le=12)


class PipelineRunTriggered(BaseModel):
    run_id: str
    status: str
