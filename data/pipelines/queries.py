"""SQL of the business performance pipeline.

telemetry_events and the domain tables are only read. The pipeline writes only
to the reporting schema. Timestamps and dates are bound with explicit types so
the same statements work on PostgreSQL (Supabase) and on SQLite (tests).
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterator

import pandas as pd
from sqlalchemy import Date, DateTime, bindparam, text
from sqlalchemy.engine import Connection, Engine

from data.pipelines import db
from data.process.weekly_location_performance import (
    SOURCE_EVENT_TYPES,
    classify_rows,
    monday_of,
)

_TS = DateTime(timezone=True)
_DAY = Date()

_UPSERT_SQL = text(
    """
    insert into reporting.weekly_location_performance
        (location_id, country, week_start, total_purchase_cost, total_waste_cost,
         waste_ratio, stockout_events_count, price_alert_events_count, currency,
         computed_at)
    values
        (:location_id, :country, :week_start, :total_purchase_cost, :total_waste_cost,
         :waste_ratio, :stockout_events_count, :price_alert_events_count, :currency,
         :computed_at)
    on conflict (location_id, week_start) do update set
        country = excluded.country,
        total_purchase_cost = excluded.total_purchase_cost,
        total_waste_cost = excluded.total_waste_cost,
        waste_ratio = excluded.waste_ratio,
        stockout_events_count = excluded.stockout_events_count,
        price_alert_events_count = excluded.price_alert_events_count,
        currency = excluded.currency,
        computed_at = excluded.computed_at
    """
).bindparams(
    bindparam("week_start", type_=_DAY),
    bindparam("computed_at", type_=_TS),
)


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def _to_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


@contextmanager
def read_only_connection(engine: Engine) -> Iterator[Connection]:
    """Connection for reading telemetry: a READ ONLY transaction on PostgreSQL."""
    with engine.connect() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("SET TRANSACTION READ ONLY"))
        yield connection


def extract_events(
    engine: Engine,
    window_start: date,
    window_end: date,
) -> tuple[pd.DataFrame, int]:
    """Business-relevant events of the window and the total of events of any type.

    The time range and the event types are filtered in SQL. The total (any type)
    is the capture heartbeat used to tell "no activity" from "capture down".
    """
    params = {"start": _start_of_day(window_start), "end": _start_of_day(window_end)}
    events_sql = text(
        'select id, "timestamp", event_type, tags from telemetry_events '
        'where "timestamp" >= :start and "timestamp" < :end and event_type in :types'
    ).bindparams(
        bindparam("start", type_=_TS),
        bindparam("end", type_=_TS),
        bindparam("types", expanding=True),
    )
    total_sql = text(
        'select count(*) from telemetry_events '
        'where "timestamp" >= :start and "timestamp" < :end'
    ).bindparams(bindparam("start", type_=_TS), bindparam("end", type_=_TS))
    with read_only_connection(engine) as connection:
        events = pd.read_sql_query(
            events_sql, connection, params={**params, "types": SOURCE_EVENT_TYPES}
        )
        total = connection.execute(total_sql, params).scalar_one()
    events["tags"] = events["tags"].map(_as_dict)
    return events, int(total)


def load_location_dim(engine: Engine) -> pd.DataFrame:
    with read_only_connection(engine) as connection:
        return pd.read_sql_query(
            text("select location_id, country, currency from reporting.location_dim"),
            connection,
        )


def read_domain_rows(
    engine: Engine,
    window_start: date,
    window_end: date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Inbound entries and waste exits of the window (read only, for reconciliation)."""
    params = {"start": _start_of_day(window_start), "end": _start_of_day(window_end)}
    entries_sql = text(
        "select created_at from ingredient_entry "
        "where created_at >= :start and created_at < :end"
    ).bindparams(bindparam("start", type_=_TS), bindparam("end", type_=_TS))
    exits_sql = text(
        "select created_at from ingredient_exit "
        "where reason = 'waste' and created_at >= :start and created_at < :end"
    ).bindparams(bindparam("start", type_=_TS), bindparam("end", type_=_TS))
    with read_only_connection(engine) as connection:
        entries = pd.read_sql_query(entries_sql, connection, params=params)
        waste_exits = pd.read_sql_query(exits_sql, connection, params=params)
    return entries, waste_exits


def read_existing_weeks(
    connection: Connection,
    window_start: date,
    window_end: date,
) -> pd.DataFrame:
    sql = text(
        "select location_id, country, week_start, total_purchase_cost, total_waste_cost, "
        "waste_ratio, stockout_events_count, price_alert_events_count, currency "
        "from reporting.weekly_location_performance "
        "where week_start >= :start and week_start < :end"
    ).bindparams(bindparam("start", type_=_DAY), bindparam("end", type_=_DAY))
    return pd.read_sql_query(
        sql, connection, params={"start": window_start, "end": window_end}
    )


def load_weekly(
    engine: Engine,
    weekly: pd.DataFrame,
    window_start: date,
    window_end: date,
) -> dict[str, Any]:
    """Idempotent load: ONE transaction, upsert by (location_id, week_start).

    The stored rows of the window are compared with the new ones and only new or
    changed rows are written, so running the pipeline twice on the same data
    leaves the table exactly as it was. If anything fails the whole transaction
    rolls back: no partial load is ever visible.
    """
    computed_at = datetime.now(timezone.utc)
    with engine.begin() as connection:
        existing = read_existing_weeks(connection, window_start, window_end)
        rows, counts = classify_rows(weekly, existing)
        if rows:
            connection.execute(
                _UPSERT_SQL,
                [{**row, "computed_at": computed_at} for row in rows],
            )
    return counts


def _default_week(connection: Connection) -> date | None:
    """Most recent CLOSED week; if there is none, the most recent computed week."""
    cutoff = monday_of(datetime.now(timezone.utc).date()) - timedelta(days=7)
    closed = connection.execute(
        text(
            "select max(week_start) from reporting.weekly_location_performance "
            "where week_start <= :cutoff"
        ).bindparams(bindparam("cutoff", type_=_DAY)),
        {"cutoff": cutoff},
    ).scalar()
    if closed is not None:
        return _to_date(closed)
    latest = connection.execute(
        text("select max(week_start) from reporting.weekly_location_performance")
    ).scalar()
    return _to_date(latest) if latest is not None else None


def get_weekly_performance(
    week_start: date | None = None,
    engine: Engine | None = None,
) -> dict[str, Any]:
    """KPIs of every location for one week (contract of the company BRIEFING)."""
    engine = engine or db.get_engine()
    with read_only_connection(engine) as connection:
        target = week_start or _default_week(connection)
        if target is None:
            return {"week_start": None, "locations": []}
        rows = (
            connection.execute(
                text(
                    "select location_id, country, total_purchase_cost, total_waste_cost, "
                    "waste_ratio, stockout_events_count, price_alert_events_count, currency "
                    "from reporting.weekly_location_performance where week_start = :week"
                ).bindparams(bindparam("week", type_=_DAY)),
                {"week": target},
            )
            .mappings()
            .all()
        )
    locations = [
        {
            "location_id": str(row["location_id"]),
            "country": row["country"],
            "total_purchase_cost": float(row["total_purchase_cost"]),
            "total_waste_cost": float(row["total_waste_cost"]),
            "waste_ratio": float(row["waste_ratio"]),
            "stockout_events_count": int(row["stockout_events_count"]),
            "price_alert_events_count": int(row["price_alert_events_count"]),
            "currency": row["currency"],
        }
        for row in rows
    ]
    locations.sort(
        key=lambda item: int(item["location_id"]) if item["location_id"].isdigit() else 10**9
    )
    return {"week_start": target, "locations": locations}
