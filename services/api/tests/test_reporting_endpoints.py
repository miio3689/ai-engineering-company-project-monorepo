"""Reporting API contract tests backed exclusively by in-memory SQLite."""

from datetime import date, datetime, timezone
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import text

from data.pipelines import db, runs
from services.api.app import main
from services.api.auth_security import get_current_user
from services.api.models import UserResponse
from services.api.tests.pipeline_helpers import create_schema, make_engine, seed_locations
from services.reporting import router as reporting_router


class ReportingEndpointTests(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine()
        create_schema(self.engine)
        seed_locations(self.engine)
        self.addCleanup(self.engine.dispose)
        self.db_patch = patch("data.pipelines.db.get_engine", return_value=self.engine)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.previous_user_override = main.app.dependency_overrides.get(get_current_user)
        self.user = UserResponse(
            id=7001,
            email="reporting-tests@example.com",
            is_active=True,
            role="user",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        main.app.dependency_overrides[get_current_user] = lambda: self.user
        self.addCleanup(self._restore_user_override)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def _restore_user_override(self):
        if self.previous_user_override is None:
            main.app.dependency_overrides.pop(get_current_user, None)
        else:
            main.app.dependency_overrides[get_current_user] = self.previous_user_override

    def _insert_week(self, location_id, week, **values):
        defaults = {
            "country": "US" if location_id == "2" else "CO",
            "total_purchase_cost": 100,
            "total_waste_cost": 10,
            "waste_ratio": 0.1,
            "stockout_events_count": 2,
            "price_alert_events_count": 3,
            "currency": "USD" if location_id == "2" else "COP",
        }
        defaults.update(values)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "insert into reporting.weekly_location_performance "
                    "(location_id, country, week_start, total_purchase_cost, "
                    "total_waste_cost, waste_ratio, stockout_events_count, "
                    "price_alert_events_count, currency) values "
                    "(:location, :country, :week, :purchase, :waste, :ratio, "
                    ":stockouts, :alerts, :currency)"
                ),
                {
                    "location": location_id,
                    "week": week,
                    "country": defaults["country"],
                    "purchase": defaults["total_purchase_cost"],
                    "waste": defaults["total_waste_cost"],
                    "ratio": defaults["waste_ratio"],
                    "stockouts": defaults["stockout_events_count"],
                    "alerts": defaults["price_alert_events_count"],
                    "currency": defaults["currency"],
                },
            )

    def test_all_three_routes_require_authentication(self):
        main.app.dependency_overrides.pop(get_current_user, None)
        requests = (
            ("GET", "/reporting/weekly-location-performance"),
            ("GET", "/reporting/pipeline-runs/latest"),
            ("POST", "/reporting/pipeline-runs"),
        )
        for method, path in requests:
            with self.subTest(method=method, path=path):
                response = self.client.request(method, path)
                self.assertEqual(response.status_code, 401, response.text)

    def test_weekly_metrics_returns_exact_contract_and_numeric_location_order(self):
        self._insert_week("10", "2026-11-09")
        self._insert_week("2", "2026-11-09")
        self._insert_week("1", "2026-11-09")
        response = self.client.get(
            "/reporting/weekly-location-performance?week_start=2026-11-09"
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["week_start"], "2026-11-09")
        self.assertEqual([row["location_id"] for row in payload["locations"]], ["1", "2", "10"])
        self.assertEqual(
            set(payload["locations"][0]),
            {
                "location_id",
                "country",
                "total_purchase_cost",
                "total_waste_cost",
                "waste_ratio",
                "stockout_events_count",
                "price_alert_events_count",
                "currency",
            },
        )

    # "Today" is fixed inside the week of 2026-11-16, so the latest closed week is 2026-11-09.
    @patch("data.pipelines.queries._utc_today", return_value=date(2026, 11, 18))
    def test_default_week_uses_latest_closed_week_or_latest_available(self, _today):
        self._insert_week("1", "2026-11-09", total_purchase_cost=90)
        self._insert_week("1", "2026-11-16", total_purchase_cost=10)
        response = self.client.get("/reporting/weekly-location-performance")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["week_start"], "2026-11-09")
        self.assertEqual(response.json()["locations"][0]["total_purchase_cost"], 90)

        with self.engine.begin() as connection:
            connection.execute(text("delete from reporting.weekly_location_performance"))
        self._insert_week("1", "2026-11-16", total_purchase_cost=10)
        response = self.client.get("/reporting/weekly-location-performance")
        self.assertEqual(response.json()["week_start"], "2026-11-16")

    def test_no_weekly_data_returns_null_and_empty_locations(self):
        response = self.client.get("/reporting/weekly-location-performance")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"week_start": None, "locations": []})

    def test_latest_run_is_404_when_empty_and_returns_run_metadata(self):
        self.assertEqual(
            self.client.get("/reporting/pipeline-runs/latest").status_code, 404
        )
        run_id = runs.open_run(
            trigger_type="schedule",
            window_start=date(2026, 11, 9),
            window_end=date(2026, 11, 23),
            engine=self.engine,
        )
        runs.close_run(
            run_id=run_id,
            status="completed",
            phase="close",
            rows_extracted=12,
            rows_after_dedup=10,
            rows_inserted=4,
            rows_updated=2,
            rows_unchanged=4,
            details={"checks": "ok"},
            engine=self.engine,
        )
        response = self.client.get("/reporting/pipeline-runs/latest")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["run_id"], run_id)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["window_start"], "2026-11-09")
        self.assertEqual(payload["rows_extracted"], 12)
        self.assertEqual(payload["details"], {"checks": "ok"})

    def test_manual_trigger_returns_accepted_and_launches_mocked_flow(self):
        with patch.object(reporting_router.pipeline_runs, "launch_flow_process") as launch:
            response = self.client.post(
                "/reporting/pipeline-runs",
                json={"week_start": "2026-11-16", "lookback_weeks": 2},
            )
        self.assertEqual(response.status_code, 202, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "running")
        launch.assert_called_once()
        self.assertEqual(launch.call_args.args[0], payload["run_id"])
        self.assertEqual(launch.call_args.args[1], date(2026, 11, 16))
        self.assertEqual(launch.call_args.args[2], 2)

    def test_manual_trigger_returns_conflict_if_run_is_active(self):
        runs.open_run(
            trigger_type="schedule",
            window_start=date(2026, 11, 9),
            window_end=date(2026, 11, 23),
            engine=self.engine,
        )
        with patch.object(reporting_router.pipeline_runs, "launch_flow_process") as launch:
            response = self.client.post("/reporting/pipeline-runs")
        self.assertEqual(response.status_code, 409, response.text)
        launch.assert_not_called()

    def test_manual_trigger_validates_request_and_defaults(self):
        for payload in (
            {"lookback_weeks": 0},
            {"unexpected": True},
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/reporting/pipeline-runs", json=payload)
                self.assertEqual(response.status_code, 422, response.text)

        with patch.object(reporting_router.pipeline_runs, "launch_flow_process") as launch:
            response = self.client.post("/reporting/pipeline-runs")
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(launch.call_args.args[1], None)
        self.assertEqual(launch.call_args.args[2], 4)

    def test_reporting_openapi_exposes_three_operations_and_response_models(self):
        openapi = self.client.get("/openapi.json").json()
        paths = openapi["paths"]
        self.assertIn("/reporting/weekly-location-performance", paths)
        self.assertIn("/reporting/pipeline-runs/latest", paths)
        self.assertIn("/reporting/pipeline-runs", paths)
        self.assertIn("WeeklyLocationPerformance", str(paths["/reporting/weekly-location-performance"]["get"]["responses"]))
        self.assertIn("PipelineRun", str(paths["/reporting/pipeline-runs/latest"]["get"]["responses"]))
        self.assertIn("PipelineRunTriggered", str(paths["/reporting/pipeline-runs"]["post"]["responses"]))

    def test_reporting_service_layer_has_no_pipeline_or_database_implementation(self):
        reporting_dir = Path(__file__).resolve().parents[2] / "reporting"
        for path in reporting_dir.glob("*.py"):
            source = path.read_text(encoding="utf-8").lower()
            for forbidden in ("import pandas", "import prefect", "insert into", "update reporting"):
                self.assertNotIn(forbidden, source, f"{path}: {forbidden}")


if __name__ == "__main__":
    unittest.main()
