"""Storage of telemetry events: one bulk insert per batch, insert only.

The table is created in Supabase with services/api/sql/telemetry_events.sql
(8 columns, 3 indexes). This module only describes it with SQLAlchemy Core to
build the INSERT, in its own MetaData so the inventory create_all never touches
it. Telemetry events are immutable: this module only inserts rows. The mapping
of every column is documented in docs/telemetry/telemetry-plan.md (section 11).
"""

import uuid
from datetime import timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Index,
    MetaData,
    Numeric,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session

from .telemetry_models import TelemetryEvent

TELEMETRY_SERVICE = "backoffice"

telemetry_metadata = MetaData()

telemetry_events = Table(
    "telemetry_events",
    telemetry_metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("timestamp", DateTime(timezone=True), nullable=False),
    Column("service", Text, nullable=False),
    Column("event_type", Text, nullable=False),
    Column("level", Text),
    Column("value", Numeric(asdecimal=False)),
    Column("message", Text),
    Column("tags", JSON().with_variant(JSONB(), "postgresql")),
    Index("ix_telemetry_events_timestamp", "timestamp"),
    Index("ix_telemetry_events_event_type", "event_type"),
    Index("ix_telemetry_events_tags", "tags", postgresql_using="gin"),
)

# Severity by event type: "error" and "warn" below, everything else is "info".
ERROR_EVENT_TYPES = frozenset({"api_error_returned"})
WARN_EVENT_TYPES = frozenset(
    {
        "login_failed",
        "session_expired",
        "direct_stock_edit_rejected",
        "outbound_order_rejected",
        "stock_threshold_triggered",
        "ingredient_price_variance_detected",
    }
)

# Main numeric property copied to the "value" column (it also stays in tags).
VALUE_PROPERTY_BY_EVENT_TYPE = {
    "inbound_order_created": "quantity",
    "outbound_order_created": "quantity",
    "stock_waste_registered": "quantity",
    "stock_threshold_triggered": "quantity",
    "direct_stock_edit_rejected": "quantity",
    "ingredient_price_variance_detected": "variance_pct",
    "outbound_order_rejected": "quantity",
    "supplier_rate_changed": "new_rate",
    "login_failed": "attempt_number_in_session",
    "api_latency_recorded": "p95_ms",
    "page_load_measured": "load_ms",
    "flow_abandoned": "elapsed_ms",
}

# Readable summary for the "message" column. It never includes user or session ids.
MESSAGE_TEMPLATES = {
    "inbound_order_created": "Entrada de {quantity} {unit} (producto {product_id}) en el local {location_id} ({country})",
    "outbound_order_created": "Salida de {quantity} {unit} (producto {product_id}) en el local {location_id} ({country})",
    "stock_waste_registered": "Merma de {quantity} {unit} (producto {product_id}) en el local {location_id} ({country}): {reason}",
    "stock_threshold_triggered": "Stock bajo el mínimo: {quantity} {unit} (mínimo {threshold_quantity}) del producto {product_id} en el local {location_id}",
    "direct_stock_edit_rejected": "Intento de fijar el stock a {quantity} {unit} del producto {product_id} en el local {location_id}: rechazado",
    "ingredient_price_variance_detected": "Variación de precio del {variance_pct} % (referencia {baseline_unit_cost}, nuevo {unit_cost} {currency}) del producto {product_id}",
    "outbound_order_rejected": "Salida rechazada ({rejection_reason}) del producto {product_id} en el local {location_id}",
    "api_error_returned": "{method} {route_template} respondió {status_code}",
    "login_failed": "Inicio de sesión fallido ({failure_reason})",
    "session_expired": "Sesión caducada ({expiry_cause}) en {last_route}",
    "page_load_measured": "{route_template}: carga en {load_ms} ms",
    "frontend_error_captured": "Error de frontend {error_name} en {route_template}",
}


class _MissingAsQuestionMark(dict):
    def __missing__(self, key: str) -> str:
        return "?"


def event_level(event_type: str, properties: dict[str, Any]) -> str:
    if event_type in ERROR_EVENT_TYPES:
        return "error"
    if event_type == "frontend_error_captured":
        return "warn" if properties.get("handled") else "error"
    if event_type in WARN_EVENT_TYPES:
        return "warn"
    return "info"


def event_value(event_type: str, properties: dict[str, Any]) -> float | None:
    key = VALUE_PROPERTY_BY_EVENT_TYPE.get(event_type)
    value = properties.get(key) if key else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def event_message(event_type: str, properties: dict[str, Any]) -> str | None:
    template = MESSAGE_TEMPLATES.get(event_type)
    if template is None:
        return None
    return template.format_map(_MissingAsQuestionMark(properties))[:300]


def event_to_row(event: TelemetryEvent) -> dict[str, Any]:
    """Map one validated event to a telemetry_events row.

    tags keeps ALL the allowlisted properties plus the envelope identifiers
    session_id, user_id, request_id and schema_version (the id column already
    holds the eventId, which makes retries idempotent).
    """
    properties = event.properties
    return {
        "id": uuid.UUID(event.eventId),
        "timestamp": event.timestamp.astimezone(timezone.utc),
        "service": TELEMETRY_SERVICE,
        "event_type": event.event_type,
        "level": event_level(event.event_type, properties),
        "value": event_value(event.event_type, properties),
        "message": event_message(event.event_type, properties),
        "tags": {
            **properties,
            "session_id": event.sessionId,
            "user_id": event.userId,
            "request_id": event.requestId,
            "schema_version": event.schemaVersion,
        },
    }


def store_events(session: Session, rows: list[dict[str, Any]]) -> None:
    """Insert all rows with ONE multi-row INSERT in ONE transaction.

    Rows whose id already exists are ignored, so a retry of the same batch is
    harmless (the frontend retries failed batches).
    """
    if not rows:
        return
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        statement = (
            postgresql_insert(telemetry_events)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["id"])
        )
    elif dialect == "sqlite":
        statement = (
            sqlite_insert(telemetry_events)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["id"])
        )
    else:
        statement = telemetry_events.insert().values(rows)
    session.exec(statement)
    session.commit()
