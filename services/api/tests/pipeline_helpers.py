"""SQLite-only fixtures shared by the reporting pipeline tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import event, insert, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from services.api.inventory import models as _inventory_models
from services.api.telemetry_storage import telemetry_events, telemetry_metadata


def make_engine() -> Engine:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    def attach_reporting(connection, _record):
        cursor = connection.cursor()
        cursor.execute("ATTACH DATABASE ':memory:' AS reporting")
        cursor.close()

    event.listen(engine, "connect", attach_reporting)
    return engine


def create_schema(engine: Engine) -> None:
    statements = (
        """
        create table reporting.weekly_location_performance (
          id text primary key default (lower(hex(randomblob(16)))),
          location_id text not null,
          country text not null,
          week_start text not null,
          total_purchase_cost real not null default 0,
          total_waste_cost real not null default 0,
          waste_ratio real not null default 0,
          stockout_events_count integer not null default 0,
          price_alert_events_count integer not null default 0,
          currency text not null,
          computed_at text,
          unique (location_id, week_start)
        )
        """,
        """
        create table reporting.location_dim (
          location_id text primary key,
          country text not null,
          currency text not null,
          name text
        )
        """,
        """
        create table reporting.pipeline_runs (
          run_id text primary key,
          pipeline_name text not null,
          trigger_type text not null,
          window_start text not null,
          window_end text not null,
          status text not null,
          phase text not null default 'open',
          started_at text not null,
          finished_at text,
          rows_extracted integer,
          rows_after_dedup integer,
          rows_rejected integer,
          rows_inserted integer,
          rows_updated integer,
          rows_unchanged integer,
          error_message text,
          resumed_from_run_id text,
          prefect_flow_run_id text,
          details text not null default '{}'
        )
        """,
        """
        create unique index reporting.ux_pipeline_runs_one_running
        on pipeline_runs (pipeline_name) where status = 'running'
        """,
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
    telemetry_metadata.create_all(engine)
    SQLModel.metadata.create_all(engine)


def seed_locations(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into reporting.location_dim "
                "(location_id, country, currency, name) values "
                "('1', 'CO', 'COP', 'Local 1'), "
                "('2', 'US', 'USD', 'Local 2'), "
                "('3', 'CO', 'COP', 'Local 3'), "
                "('4', 'CO', 'COP', 'Local 4')"
            )
        )


def insert_event(
    engine: Engine,
    event_type: str,
    ts: datetime,
    tags: dict[str, Any],
    event_id: str | None = None,
) -> str:
    identifier = event_id or str(uuid.uuid4())
    with engine.begin() as connection:
        connection.execute(
            insert(telemetry_events).values(
                id=identifier,
                timestamp=ts.astimezone(timezone.utc),
                service="backoffice",
                event_type=event_type,
                level="info",
                value=None,
                message=None,
                tags=tags,
            )
        )
    return identifier
