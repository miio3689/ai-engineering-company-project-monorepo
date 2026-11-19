"""Tests for the authenticated telemetry report endpoint."""

from datetime import datetime, timedelta, timezone
import os
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool

from services.api import auth_security
from services.api.app import main
from services.api.cache import InProcessTTLCache
from services.api.models import UserResponse, UserRole
from services.api.telemetry_storage import telemetry_events, telemetry_metadata
from services.api.routes import telemetry_report as telemetry_report_route
from services.telemetry import analysis


UTC = timezone.utc
METRIC_KEYS = {
    "events_per_day",
    "error_rate_by_day",
    "error_rate_by_type",
    "page_load_ms_by_route",
    "auth_failure_rate",
}


class TelemetryReportEndpointTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        telemetry_metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(
                insert(telemetry_events),
                [
                    {
                        "id": uuid.uuid4(),
                        "timestamp": datetime(2026, 11, 17, 12, tzinfo=UTC),
                        "service": "backoffice",
                        "event_type": "page_viewed",
                        "level": "info",
                        "value": None,
                        "tags": {},
                    }
                ],
            )
        self.user = UserResponse(
            id=1,
            email="telemetry-test@example.com",
            is_active=True,
            role=UserRole.user,
            created_at="2026-01-01T00:00:00+00:00",
        )
        main.app.dependency_overrides[auth_security.get_current_user] = lambda: self.user
        self.addCleanup(main.app.dependency_overrides.clear)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.original_cache = telemetry_report_route.report_cache
        self.clock = [100.0]
        telemetry_report_route.report_cache = InProcessTTLCache(clock=lambda: self.clock[0])
        self.addCleanup(self._restore_cache)
        self.engine_patch = patch("services.telemetry.analysis.get_engine", return_value=self.engine)
        self.engine_patch.start()
        self.addCleanup(self.engine_patch.stop)
        self.addCleanup(self.engine.dispose)

    def _restore_cache(self):
        telemetry_report_route.report_cache = self.original_cache

    def get_report(self, query=""):
        return self.client.get(f"/telemetry/report{query}")

    def test_authentication_is_required(self):
        main.app.dependency_overrides.clear()
        response = self.get_report()
        self.assertEqual(response.status_code, 401)

    def test_response_shape_and_no_nan(self):
        response = self.get_report("?start_date=2026-11-16T00:00:00Z&end_date=2026-11-19T00:00:00Z")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(set(payload), {"period", "metrics"})
        self.assertEqual(set(payload["metrics"]), METRIC_KEYS)
        self.assertTrue(all(isinstance(value, list) for value in payload["metrics"].values()))
        self.assertNotIn("NaN", response.text)

    def test_explicit_and_default_periods(self):
        response = self.get_report("?start_date=2026-11-16T02:00:00%2B02:00&end_date=2026-11-19T00:00:00Z")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["period"]["from"], "2026-11-16T00:00:00+00:00")
        self.assertEqual(response.json()["period"]["to"], "2026-11-19T00:00:00+00:00")
        default = self.get_report()
        self.assertEqual(default.status_code, 200)
        period = default.json()["period"]
        self.assertEqual(
            datetime.fromisoformat(period["to"]) - datetime.fromisoformat(period["from"]),
            timedelta(days=7),
        )

    def test_cache_ttl_distinct_parameters_and_default_key(self):
        with patch.object(telemetry_report_route, "build_report", wraps=analysis.build_report) as build:
            query = "?start_date=2026-11-16T00:00:00Z&end_date=2026-11-19T00:00:00Z"
            self.assertEqual(self.get_report(query).status_code, 200)
            self.assertEqual(self.get_report(query).status_code, 200)
            self.assertEqual(build.call_count, 1)
            self.clock[0] += 61
            self.assertEqual(self.get_report(query).status_code, 200)
            self.assertEqual(build.call_count, 2)
            other_query = "?start_date=2026-11-16T00:00:00Z&end_date=2026-11-18T00:00:00Z"
            self.assertEqual(self.get_report(other_query).status_code, 200)
            self.assertEqual(build.call_count, 3)

        with patch.object(telemetry_report_route, "build_report", wraps=analysis.build_report) as build:
            self.assertEqual(self.get_report().status_code, 200)
            self.assertEqual(self.get_report().status_code, 200)
            self.assertEqual(build.call_count, 1)

    def test_invalid_periods_and_dates_return_422(self):
        self.assertEqual(
            self.get_report("?start_date=2026-11-18T00:00:00Z&end_date=2026-11-18T00:00:00Z").status_code,
            422,
        )
        self.assertEqual(
            self.get_report("?start_date=2026-01-01T00:00:00Z&end_date=2026-04-02T00:00:00Z").status_code,
            422,
        )
        self.assertEqual(self.get_report("?start_date=no-es-fecha").status_code, 422)

    def test_missing_database_url_and_database_errors_return_503(self):
        self.engine_patch.stop()
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.get_report().status_code, 503)

        with patch.object(
            telemetry_report_route,
            "build_report",
            side_effect=OperationalError("SELECT", {}, RuntimeError("db")),
        ) as build:
            first = self.get_report("?start_date=2026-11-16T00:00:00Z&end_date=2026-11-19T00:00:00Z")
            second = self.get_report("?start_date=2026-11-16T00:00:00Z&end_date=2026-11-19T00:00:00Z")
            self.assertEqual((first.status_code, second.status_code), (503, 503))
            self.assertEqual(build.call_count, 2)

    def test_openapi_declares_response_model_query_parameters_and_alias(self):
        openapi = main.app.openapi()
        operation = openapi["paths"]["/telemetry/report"]["get"]
        self.assertEqual(
            operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/TelemetryReport",
        )
        self.assertEqual({parameter["name"] for parameter in operation["parameters"]}, {"start_date", "end_date"})
        period_schema = openapi["components"]["schemas"]["ReportPeriod"]
        self.assertIn("from", period_schema["properties"])
        self.assertNotIn("from_", period_schema["properties"])


if __name__ == "__main__":
    unittest.main()
