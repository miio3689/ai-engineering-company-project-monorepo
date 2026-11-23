"""Tests for telemetry validation, mapping, and isolated SQLite storage."""

import json
import os
import re
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from services.api.app import main
from services.api.inventory import database
from services.api.telemetry_contract import load_contract
from services.api.telemetry_models import TelemetryEvent
from services.api.telemetry_storage import (
    ERROR_EVENT_TYPES,
    MESSAGE_TEMPLATES,
    VALUE_PROPERTY_BY_EVENT_TYPE,
    WARN_EVENT_TYPES,
    event_level,
    event_message,
    event_to_row,
    event_value,
    telemetry_events,
    telemetry_metadata,
)


def make_event(event_type="page_viewed", properties=None, **overrides):
    event_data = {
        "eventId": str(uuid.uuid4()),
        "timestamp": "2026-11-15T14:32:08.120Z",
        "sessionId": "0b9a3c4e-6d1f-4e2a-8c57-1f3e9a7b2d64",
        "userId": "42",
        "event_type": event_type,
        "schemaVersion": "1.0.0",
        "requestId": "none",
        "properties": (
            {"route_template": "/inventory/products", "section": "inventory"}
            if properties is None
            else properties
        ),
    }
    event_data.update(overrides)
    return event_data


def inbound_order_properties():
    return {
        "location_id": 1,
        "country": "CO",
        "product_id": 7,
        "product_category": "meat",
        "quantity": 10,
        "unit": "kg",
        "currency": "COP",
        "inbound_order_id": 44,
        "supplier_name": "Proveedor Brasaland",
    }


def stock_waste_properties(unit_cost=None):
    properties = {
        "location_id": 1,
        "country": "CO",
        "product_id": 7,
        "product_category": "meat",
        "quantity": 2,
        "unit": "kg",
        "currency": "COP",
        "outbound_order_id": 45,
        "reason": "expired",
    }
    if unit_cost is not None:
        properties["unit_cost"] = unit_cost
    return properties


def event_properties(event_type):
    properties_by_type = {
        "page_viewed": {
            "route_template": "/inventory/products",
            "section": "inventory",
        },
        "login_failed": {
            "failure_reason": "invalid_credentials",
            "attempt_number_in_session": 2,
        },
        "inbound_order_created": inbound_order_properties(),
        "api_error_returned": {
            "method": "POST",
            "route_template": "/inventory/orders",
            "status_code": 503,
            "error_category": "database_unavailable",
        },
        "frontend_error_captured": {
            "error_name": "TypeError",
            "error_fingerprint": "deadbeef",
            "route_template": "/inventory/products",
            "handled": True,
        },
    }
    return properties_by_type[event_type]


class TelemetryEventsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        telemetry_metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)

        def override_get_db():
            with Session(self.engine) as session:
                yield session

        self.get_db_override = override_get_db
        self.previous_get_db_override = main.app.dependency_overrides.get(
            database.get_db
        )
        main.app.dependency_overrides[database.get_db] = override_get_db
        self.addCleanup(self._restore_get_db_override)

        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def _restore_get_db_override(self):
        if self.previous_get_db_override is None:
            main.app.dependency_overrides.pop(database.get_db, None)
        else:
            main.app.dependency_overrides[database.get_db] = (
                self.previous_get_db_override
            )

    def post(self, events):
        return self.client.post("/telemetry/events", json={"events": events})

    def rows(self):
        with self.engine.connect() as connection:
            return connection.execute(
                select(telemetry_events).order_by(telemetry_events.c.event_type)
            ).mappings().all()

    def test_valid_batch_stores_all_fields_for_each_event(self):
        events = [
            make_event(),
            make_event("login_failed", properties=event_properties("login_failed")),
            make_event(
                "inbound_order_created",
                properties=event_properties("inbound_order_created"),
            ),
        ]

        response = self.post(events)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(), {"received": 3, "stored": 3, "rejected": 0}
        )
        rows_by_id = {str(row["id"]): row for row in self.rows()}
        self.assertEqual(len(rows_by_id), 3)
        for sent in events:
            row = rows_by_id[sent["eventId"]]
            expected_timestamp = datetime.fromisoformat(
                sent["timestamp"].replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            actual_timestamp = row["timestamp"]
            if actual_timestamp.tzinfo is None:
                actual_timestamp = actual_timestamp.replace(tzinfo=timezone.utc)
            self.assertEqual(actual_timestamp, expected_timestamp)
            self.assertEqual(row["service"], "backoffice")
            self.assertEqual(row["event_type"], sent["event_type"])
            self.assertIn(row["level"], {"info", "warn", "error"})
            self.assertEqual(row["tags"], {
                **sent["properties"],
                "session_id": sent["sessionId"],
                "user_id": sent["userId"],
                "request_id": sent["requestId"],
                "schema_version": sent["schemaVersion"],
            })
            if sent["event_type"] == "inbound_order_created":
                self.assertEqual(row["value"], 10.0)
                self.assertTrue(row["message"].startswith("Entrada de 10 kg"))

    def test_mixed_batch_rejects_bad_events_without_cancelling_valid_event(self):
        missing_event_id = make_event()
        del missing_event_id["eventId"]
        unknown_type = make_event("catalog_event")
        extra_property = make_event(properties={
            "route_template": "/inventory/products",
            "section": "inventory",
            "email": "private@example.com",
        })
        bad_enum = make_event(properties={
            "route_template": "/inventory/products",
            "section": "otra",
        })
        naive_timestamp = make_event(timestamp="2026-11-15T14:32:08.120")
        valid = make_event()

        response = self.post(
            [valid, missing_event_id, unknown_type, extra_property, bad_enum, naive_timestamp]
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(), {"received": 6, "stored": 1, "rejected": 5}
        )
        self.assertEqual([str(row["id"]) for row in self.rows()], [valid["eventId"]])

    def test_waste_unit_cost_is_optional_positive_and_not_allowed_for_consumption(self):
        valid = make_event(
            "stock_waste_registered",
            properties=stock_waste_properties(12.5),
            schemaVersion="1.1.0",
        )
        response = self.post([valid])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"received": 1, "stored": 1, "rejected": 0})
        stored = {str(row["id"]): row for row in self.rows()}[valid["eventId"]]
        self.assertEqual(stored["tags"]["unit_cost"], 12.5)

        for cost in (0, -1):
            with self.subTest(unit_cost=cost):
                invalid = make_event(
                    "stock_waste_registered",
                    properties=stock_waste_properties(cost),
                    schemaVersion="1.1.0",
                )
                rejected = self.post([invalid])
                self.assertEqual(rejected.status_code, 200, rejected.text)
                self.assertEqual(
                    rejected.json(),
                    {"received": 1, "stored": 0, "rejected": 1},
                )

        consumption = make_event(
            "outbound_order_created",
            properties={
                **stock_waste_properties(),
                "unit_cost": 12.5,
            },
            schemaVersion="1.1.0",
        )
        rejected = self.post([consumption])
        self.assertEqual(rejected.status_code, 200, rejected.text)
        self.assertEqual(
            rejected.json(),
            {"received": 1, "stored": 0, "rejected": 1},
        )

    def test_non_object_events_count_as_rejected(self):
        valid = make_event()
        response = self.post([1, None, "not an event", valid])

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(), {"received": 4, "stored": 1, "rejected": 3}
        )
        self.assertEqual(len(self.rows()), 1)

    def test_request_shape_empty_batches_and_limits(self):
        invalid_bodies = (
            ("no es json", "text/plain"),
            ("[]", "application/json"),
            ('{"missing": []}', "application/json"),
            ('{"events": "not a list"}', "application/json"),
            ('{"events": null}', "application/json"),
        )
        for body, content_type in invalid_bodies:
            with self.subTest(body=body):
                response = self.client.post(
                    "/telemetry/events",
                    content=body,
                    headers={"Content-Type": content_type},
                )
                self.assertEqual(response.status_code, 422)

        empty_response = self.post([])
        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(
            empty_response.json(), {"received": 0, "stored": 0, "rejected": 0}
        )
        too_many = self.post([None] * 101)
        self.assertEqual(too_many.status_code, 413)
        too_large = self.client.post(
            "/telemetry/events",
            content=b" " * (256 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(too_large.status_code, 413)

    def test_accepts_text_plain_send_beacon_body(self):
        response = self.client.post(
            "/telemetry/events",
            content=json.dumps({"events": [make_event()]}),
            headers={"Content-Type": "text/plain;charset=UTF-8"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(), {"received": 1, "stored": 1, "rejected": 0}
        )

    def test_valid_batch_executes_exactly_one_bulk_insert(self):
        inserts = []

        def record_insert(_conn, _cursor, statement, _parameters, _context, _many):
            if statement.lstrip().upper().startswith("INSERT") and "telemetry_events" in statement:
                inserts.append(statement)

        event.listen(self.engine, "before_cursor_execute", record_insert)
        try:
            response = self.post([make_event() for _ in range(5)])
        finally:
            event.remove(self.engine, "before_cursor_execute", record_insert)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(inserts), 1)

    def test_reposting_same_batch_is_idempotent(self):
        batch = [make_event(), make_event()]

        first = self.post(batch)
        second = self.post(batch)

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(
            second.json(), {"received": 2, "stored": 2, "rejected": 0}
        )
        self.assertEqual(len(self.rows()), 2)

    def test_database_error_returns_503_and_leaves_table_empty(self):
        with patch(
            "services.api.routes.telemetry.store_events",
            side_effect=OperationalError("insert", {}, Exception("database")),
        ):
            response = self.post([make_event()])

        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.rows(), [])

    def test_missing_database_url_without_override_returns_503(self):
        main.app.dependency_overrides.pop(database.get_db, None)
        try:
            with patch.dict(os.environ):
                os.environ.pop("DATABASE_URL", None)
                response = self.client.post(
                    "/telemetry/events", json={"events": [make_event()]}
                )
        finally:
            main.app.dependency_overrides[database.get_db] = self.get_db_override

        self.assertEqual(response.status_code, 503)

    def test_logs_counts_and_event_types_without_identifiers_or_properties(self):
        accepted = make_event(
            userId="987654321",
            sessionId="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )
        rejected = make_event(
            "page_viewed",
            properties={
                "route_template": "/inventory/products",
                "section": "secret-section-value",
                "email": "private@example.com",
            },
            userId="123456789",
            sessionId="11111111-2222-3333-4444-555555555555",
        )

        with self.assertLogs("api.telemetry", level="INFO") as logs:
            response = self.post([accepted, rejected])
        output = "\n".join(logs.output)

        self.assertEqual(response.status_code, 200)
        self.assertIn("received=2 stored=1 rejected=1", output)
        self.assertIn("page_viewed", output)
        for private_value in (
            accepted["userId"],
            accepted["sessionId"],
            rejected["userId"],
            rejected["sessionId"],
            "secret-section-value",
            "private@example.com",
            "email",
        ):
            self.assertNotIn(private_value, output)

    def test_schema_version_requires_supported_major_version(self):
        unsupported = make_event(schemaVersion="2.0.0")
        compatible_minor = make_event(schemaVersion="1.4.2")

        response = self.post([unsupported, compatible_minor])

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(), {"received": 2, "stored": 1, "rejected": 1}
        )
        self.assertEqual(
            [str(row["id"]) for row in self.rows()], [compatible_minor["eventId"]]
        )

    def test_tags_preserve_allowlisted_properties_and_reserved_keys_do_not_collide(self):
        sent = make_event()
        response = self.post([sent])
        self.assertEqual(response.status_code, 200, response.text)
        row = self.rows()[0]
        self.assertEqual(
            {key: value for key, value in row["tags"].items() if key not in {
                "session_id", "user_id", "request_id", "schema_version"
            }},
            sent["properties"],
        )

        reserved = {"session_id", "user_id", "request_id", "schema_version"}
        contract = load_contract()
        allowlisted = {
            key
            for definition in contract["events"].values()
            for key in definition["schema"]["properties"]["properties"]["properties"]
        }
        self.assertFalse(allowlisted & reserved)

    def test_service_schema_copy_matches_documented_contract(self):
        docs_path = Path(__file__).resolve().parents[3] / "docs" / "telemetry" / "event-schemas.json"
        if not docs_path.exists():
            self.skipTest("docs/ no existe en este entorno")
        service_path = Path(__file__).resolve().parents[1] / "telemetry_schemas" / "event-schemas.json"
        with docs_path.open(encoding="utf-8") as docs_file:
            docs_contract = json.load(docs_file)
        with service_path.open(encoding="utf-8") as service_file:
            service_contract = json.load(service_file)
        self.assertEqual(service_contract, docs_contract)

    def test_openapi_does_not_declare_telemetry_request_body(self):
        operation = main.app.openapi()["paths"]["/telemetry/events"]["post"]
        self.assertNotIn("requestBody", operation)

    def test_schema_table_and_envelope_remain_immutable_and_exact(self):
        api_root = Path(__file__).resolve().parents[1]
        for source_path in (
            api_root / "telemetry_storage.py",
            api_root / "routes" / "telemetry.py",
        ):
            source = source_path.read_text(encoding="utf-8")
            self.assertNotIn(".update(", source)
            self.assertNotIn("delete(", source)
            self.assertNotIn("UPDATE ", source)

        sql_source = (api_root / "sql" / "telemetry_events.sql").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("ix_telemetry_events_timestamp", sql_source)
        self.assertIn("ix_telemetry_events_event_type", sql_source)
        self.assertIn("using gin (tags)", sql_source)
        self.assertIn("enable row level security", sql_source)
        self.assertIn("gen_random_uuid()", sql_source)
        self.assertNotIn("create trigger", sql_source)

        expected_columns = {
            "id", "timestamp", "service", "event_type",
            "level", "value", "message", "tags",
        }
        self.assertEqual(set(telemetry_events.c.keys()), expected_columns)
        self.assertEqual(len(telemetry_events.indexes), 3)
        self.assertEqual(
            set(TelemetryEvent.model_fields),
            {
                "eventId", "timestamp", "sessionId", "userId",
                "event_type", "schemaVersion", "requestId", "properties",
            },
        )

    def test_event_level_mapping(self):
        self.assertEqual(event_level("api_error_returned", {}), "error")
        self.assertEqual(event_level("login_failed", {}), "warn")
        self.assertEqual(event_level("page_viewed", {}), "info")
        self.assertEqual(
            event_level("frontend_error_captured", {"handled": True}), "warn"
        )
        self.assertEqual(
            event_level("frontend_error_captured", {"handled": False}), "error"
        )

    def test_event_value_mapping(self):
        self.assertEqual(
            event_value("inbound_order_created", {"quantity": 10}), 10.0
        )
        self.assertEqual(
            event_value("ingredient_price_variance_detected", {"variance_pct": 12.5}),
            12.5,
        )
        self.assertIsNone(event_value("page_viewed", {"section": "inventory"}))

    def test_message_mapping_does_not_include_envelope_identifiers(self):
        inbound = make_event(
            "inbound_order_created",
            properties=event_properties("inbound_order_created"),
            userId="42424242",
            sessionId="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )
        inbound_model = TelemetryEvent.model_validate(inbound)
        message = event_message(inbound_model.event_type, inbound_model.properties)
        page = make_event()
        page_model = TelemetryEvent.model_validate(page)

        self.assertTrue(message.startswith("Entrada de 10 kg"))
        self.assertIsNone(event_message(page_model.event_type, page_model.properties))
        self.assertNotIn(inbound["userId"], message)
        self.assertNotIn(inbound["sessionId"], message)

    def test_mapping_tables_match_contract_allowlists(self):
        contract = load_contract()
        event_types = set(contract["events"])
        self.assertTrue(set(VALUE_PROPERTY_BY_EVENT_TYPE) <= event_types)
        self.assertTrue(set(MESSAGE_TEMPLATES) <= event_types)
        self.assertTrue(ERROR_EVENT_TYPES <= event_types)
        self.assertTrue(WARN_EVENT_TYPES <= event_types)

        allowlists = {
            event_type: set(
                definition["schema"]["properties"]["properties"]["properties"]
            )
            for event_type, definition in contract["events"].items()
        }
        for event_type, property_name in VALUE_PROPERTY_BY_EVENT_TYPE.items():
            self.assertIn(property_name, allowlists[event_type])
        for event_type, template in MESSAGE_TEMPLATES.items():
            markers = set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", template))
            self.assertTrue(markers <= allowlists[event_type])


if __name__ == "__main__":
    unittest.main()
