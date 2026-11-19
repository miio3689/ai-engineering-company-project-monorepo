"""Operational (technical) metrics computed from telemetry_events with Pandas.

Every metric function follows the same order: load (SQL) -> refine (Pandas) ->
convert types -> group -> aggregate -> serve. The period (start_date inclusive,
end_date exclusive, both UTC) is resolved ONCE by the endpoint and applied ONCE,
in SQL; the functions never apply their own default window. They have no side
effects: calling one twice with the same arguments returns the same result.
Results are lists of plain dicts, ready to be serialized as JSON. There are no
Python loops: everything is vectorized Pandas.

These are technical metrics (volume, errors, latency, availability of the
login), not business metrics.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.engine import Engine

from services.api.inventory.database import get_engine
from services.api.telemetry_storage import telemetry_events

DEFAULT_PERIOD_DAYS = 7
MAX_PERIOD_DAYS = 90
AUTH_EVENT_TYPES = ["login_failed", "login_succeeded"]
PAGE_LOAD_EVENT_TYPES = ["page_load_measured"]


def as_utc(value: datetime) -> datetime:
    """Naive datetimes are taken as UTC; aware ones are converted to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def resolve_period(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Resolve the period once: defaults are the last 7 days (end = now, UTC)."""
    current = as_utc(now) if now is not None else datetime.now(timezone.utc)
    end = as_utc(end_date) if end_date is not None else current
    start = (
        as_utc(start_date)
        if start_date is not None
        else end - timedelta(days=DEFAULT_PERIOD_DAYS)
    )
    if start >= end:
        raise ValueError("start_date debe ser anterior a end_date.")
    if end - start > timedelta(days=MAX_PERIOD_DAYS):
        raise ValueError(f"El período no puede superar {MAX_PERIOD_DAYS} días.")
    return start, end


def _load_events(
    engine: Engine | None,
    start_date: datetime,
    end_date: datetime,
    columns: list[Any],
    event_types: list[str] | None = None,
) -> pd.DataFrame:
    """LOAD (SQL): the time range and the event types are filtered in the query."""
    statement = select(*columns).where(
        telemetry_events.c.timestamp >= start_date,
        telemetry_events.c.timestamp < end_date,
    )
    if event_types is not None:
        statement = statement.where(telemetry_events.c.event_type.in_(event_types))
    with (engine or get_engine()).connect() as connection:
        return pd.read_sql_query(statement, connection)


def _add_date(events: pd.DataFrame) -> pd.DataFrame:
    """CONVERT TYPES: timestamps become datetime (UTC) BEFORE any grouping."""
    events = events.copy()
    events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True)
    events["date"] = events["timestamp"].dt.strftime("%Y-%m-%d")
    return events


def _with_rates(grouped: pd.DataFrame) -> pd.DataFrame:
    grouped = grouped.copy()
    grouped["error_rate"] = (grouped["errors"] / grouped["events"]).round(4)
    grouped["problem_rate"] = (
        (grouped["errors"] + grouped["warnings"]) / grouped["events"]
    ).round(4)
    return grouped


def _records(result: pd.DataFrame) -> list[dict[str, Any]]:
    """SERVE: a list of plain dicts, serializable as JSON."""
    return result.reset_index(drop=True).to_dict(orient="records")


def events_per_day(
    start_date: datetime,
    end_date: datetime,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """Which events happen and how often? Volume per day and event type."""
    columns = [telemetry_events.c.timestamp, telemetry_events.c.event_type]
    events = _load_events(engine, start_date, end_date, columns)
    events = events.dropna(subset=["event_type"])
    if events.empty:
        return []
    events = _add_date(events)
    result = events.groupby(["date", "event_type"], as_index=False).agg(
        events=("event_type", "count")
    )
    return _records(result.sort_values(["date", "event_type"]))


def error_rate_by_day(
    start_date: datetime,
    end_date: datetime,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """How healthy is the system each day? Errors and warnings over all events."""
    columns = [
        telemetry_events.c.timestamp,
        telemetry_events.c.event_type,
        telemetry_events.c.level,
    ]
    events = _load_events(engine, start_date, end_date, columns)
    if events.empty:
        return []
    events = _add_date(events)
    events["is_error"] = events["level"].eq("error")
    events["is_warning"] = events["level"].eq("warn")
    grouped = events.groupby("date", as_index=False).agg(
        events=("event_type", "count"),
        errors=("is_error", "sum"),
        warnings=("is_warning", "sum"),
    )
    return _records(_with_rates(grouped).sort_values("date"))


def error_rate_by_type(
    start_date: datetime,
    end_date: datetime,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """Which kinds of event signal problems? Errors and warnings per event type."""
    columns = [
        telemetry_events.c.timestamp,
        telemetry_events.c.event_type,
        telemetry_events.c.level,
    ]
    events = _load_events(engine, start_date, end_date, columns)
    events = events.dropna(subset=["event_type"])
    if events.empty:
        return []
    events = _add_date(events)
    events["is_error"] = events["level"].eq("error")
    events["is_warning"] = events["level"].eq("warn")
    grouped = events.groupby("event_type", as_index=False).agg(
        events=("event_type", "count"),
        errors=("is_error", "sum"),
        warnings=("is_warning", "sum"),
    )
    return _records(
        _with_rates(grouped).sort_values(
            ["problem_rate", "events"], ascending=[False, False]
        )
    )


def page_load_ms_by_route(
    start_date: datetime,
    end_date: datetime,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """How fast do screens load? Average and p95 load time per day and route."""
    columns = [
        telemetry_events.c.timestamp,
        telemetry_events.c.value,
        telemetry_events.c.tags,
    ]
    events = _load_events(
        engine, start_date, end_date, columns, PAGE_LOAD_EVENT_TYPES
    )
    if events.empty:
        return []
    events["route"] = events["tags"].str.get("route_template")
    events["value"] = pd.to_numeric(events["value"], errors="coerce")
    events = events.dropna(subset=["route", "value"])
    if events.empty:
        return []
    events = _add_date(events)
    load_ms = events.groupby(["date", "route"])["value"]
    result = pd.concat(
        {
            "samples": load_ms.count(),
            "avg_ms": load_ms.mean().round(1),
            "p95_ms": load_ms.quantile(0.95).round(1),
        },
        axis=1,
    ).reset_index()
    return _records(result.sort_values(["date", "route"]))


def auth_failure_rate(
    start_date: datetime,
    end_date: datetime,
    engine: Engine | None = None,
) -> list[dict[str, Any]]:
    """How often does login fail? login_failed over all login attempts, per day."""
    columns = [telemetry_events.c.timestamp, telemetry_events.c.event_type]
    events = _load_events(engine, start_date, end_date, columns, AUTH_EVENT_TYPES)
    if events.empty:
        return []
    events = _add_date(events)
    events["is_failure"] = events["event_type"].eq("login_failed")
    result = events.groupby("date", as_index=False).agg(
        attempts=("event_type", "count"),
        failures=("is_failure", "sum"),
    )
    result["failure_rate"] = (result["failures"] / result["attempts"]).round(4)
    return _records(result.sort_values("date"))


def build_report(
    start_date: datetime,
    end_date: datetime,
    engine: Engine | None = None,
) -> dict[str, Any]:
    """Run the whole pipeline for one period."""
    return {
        "period": {"from": start_date.isoformat(), "to": end_date.isoformat()},
        "metrics": {
            "events_per_day": events_per_day(start_date, end_date, engine),
            "error_rate_by_type": error_rate_by_type(start_date, end_date, engine),
            "error_rate_by_day": error_rate_by_day(start_date, end_date, engine),
            "page_load_ms_by_route": page_load_ms_by_route(
                start_date, end_date, engine
            ),
            "auth_failure_rate": auth_failure_rate(start_date, end_date, engine),
        },
    }
