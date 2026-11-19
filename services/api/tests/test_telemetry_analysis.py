"""Tests for the vectorized telemetry report analysis pipeline."""

import ast
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import event, insert
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from services.api.telemetry_storage import telemetry_events, telemetry_metadata
from services.telemetry import analysis


UTC = timezone.utc
START = datetime(2026, 11, 16, tzinfo=UTC)
END = datetime(2026, 11, 19, tzinfo=UTC)


class TelemetryAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        telemetry_metadata.create_all(self.engine)
        rows = []

        def add(day, hour, minute, second, event_type, level="info", value=None, tags=None):
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "timestamp": datetime(2026, 11, day, hour, minute, second, tzinfo=UTC),
                    "service": "backoffice",
                    "event_type": event_type,
                    "level": level,
                    "value": value,
                    "tags": tags,
                }
            )

        add(16, 12, 0, 0, "page_viewed")
        add(16, 23, 59, 59, "page_viewed")
        add(16, 18, 0, 0, "login_succeeded")
        add(17, 0, 0, 0, "page_viewed")
        add(17, 12, 0, 0, "page_viewed")
        add(17, 9, 0, 0, "login_failed", "warn")
        add(17, 9, 1, 0, "login_failed", "warn")
        add(17, 9, 2, 0, "login_succeeded")
        add(17, 9, 3, 0, "login_succeeded")
        add(17, 9, 4, 0, "login_succeeded")
        route = {"route_template": "/inventory/products"}
        add(17, 10, 0, 0, "page_load_measured", value=1000, tags=route)
        add(17, 10, 1, 0, "page_load_measured", value=2000, tags=route)
        add(17, 10, 2, 0, "page_load_measured", value=3000, tags=route)
        add(17, 10, 3, 0, "page_load_measured", value=4000, tags={"route_template": "/login"})
        add(17, 10, 4, 0, "page_load_measured", value=5000, tags={})
        add(17, 10, 5, 0, "page_load_measured", tags=route)
        add(18, 12, 0, 0, "page_viewed")
        add(18, 13, 0, 0, "page_viewed")
        add(18, 14, 0, 0, "api_error_returned", "error")
        add(18, 15, 0, 0, "api_error_returned", "error")
        with self.engine.begin() as connection:
            connection.execute(insert(telemetry_events), rows)
        self.get_engine_patch = patch(
            "services.telemetry.analysis.get_engine", return_value=self.engine
        )
        self.get_engine_patch.start()
        self.addCleanup(self.get_engine_patch.stop)
        self.addCleanup(self.engine.dispose)

    def call_metrics(self, name, start=START, end=END):
        return getattr(analysis, name)(start, end, self.engine)

    def test_events_per_day_counts_and_sort_order(self):
        result = self.call_metrics("events_per_day")
        self.assertEqual(
            result,
            [
                {"date": "2026-11-16", "event_type": "login_succeeded", "events": 1},
                {"date": "2026-11-16", "event_type": "page_viewed", "events": 2},
                {"date": "2026-11-17", "event_type": "login_failed", "events": 2},
                {"date": "2026-11-17", "event_type": "login_succeeded", "events": 3},
                {"date": "2026-11-17", "event_type": "page_load_measured", "events": 6},
                {"date": "2026-11-17", "event_type": "page_viewed", "events": 2},
                {"date": "2026-11-18", "event_type": "api_error_returned", "events": 2},
                {"date": "2026-11-18", "event_type": "page_viewed", "events": 2},
            ],
        )
        self.assertTrue(all(set(row) == {"date", "event_type", "events"} for row in result))

    def test_range_is_inclusive_at_start_and_exclusive_at_end(self):
        result = analysis.events_per_day(
            datetime(2026, 11, 16, 23, 59, 59, tzinfo=UTC),
            datetime(2026, 11, 17, tzinfo=UTC),
            self.engine,
        )
        self.assertEqual(result, [{"date": "2026-11-16", "event_type": "page_viewed", "events": 1}])

    def test_events_are_grouped_by_utc_day(self):
        result = analysis.events_per_day(START, datetime(2026, 11, 17, 0, 0, 1, tzinfo=UTC), self.engine)
        page_views = [row for row in result if row["event_type"] == "page_viewed"]
        self.assertEqual([row["date"] for row in page_views], ["2026-11-16", "2026-11-17"])
        self.assertEqual([row["events"] for row in page_views], [2, 1])

    def test_error_rates_by_day_and_type(self):
        daily = self.call_metrics("error_rate_by_day")
        self.assertEqual(daily, [
            {"date": "2026-11-16", "events": 3, "errors": 0, "warnings": 0, "error_rate": 0.0, "problem_rate": 0.0},
            {"date": "2026-11-17", "events": 13, "errors": 0, "warnings": 2, "error_rate": 0.0, "problem_rate": 0.1538},
            {"date": "2026-11-18", "events": 4, "errors": 2, "warnings": 0, "error_rate": 0.5, "problem_rate": 0.5},
        ])
        by_type = self.call_metrics("error_rate_by_type")
        self.assertEqual(
            {row["event_type"]: row for row in by_type}["api_error_returned"],
            {"event_type": "api_error_returned", "events": 2, "errors": 2, "warnings": 0, "error_rate": 1.0, "problem_rate": 1.0},
        )
        self.assertEqual(
            {row["event_type"]: row for row in by_type}["login_failed"],
            {"event_type": "login_failed", "events": 2, "errors": 0, "warnings": 2, "error_rate": 0.0, "problem_rate": 1.0},
        )
        self.assertEqual(
            [row["problem_rate"] for row in by_type],
            sorted((row["problem_rate"] for row in by_type), reverse=True),
        )

    def test_page_load_metrics_filter_missing_values_and_types(self):
        self.assertEqual(self.call_metrics("page_load_ms_by_route"), [
            {"date": "2026-11-17", "route": "/inventory/products", "samples": 3, "avg_ms": 2000.0, "p95_ms": 2900.0},
            {"date": "2026-11-17", "route": "/login", "samples": 1, "avg_ms": 4000.0, "p95_ms": 4000.0},
        ])

    def test_auth_failure_rates_include_success_only_day(self):
        self.assertEqual(self.call_metrics("auth_failure_rate"), [
            {"date": "2026-11-16", "attempts": 1, "failures": 0, "failure_rate": 0.0},
            {"date": "2026-11-17", "attempts": 5, "failures": 2, "failure_rate": 0.4},
        ])

    def test_empty_window_returns_empty_lists(self):
        start = datetime(2026, 11, 20, tzinfo=UTC)
        end = datetime(2026, 11, 21, tzinfo=UTC)
        for name in (
            "events_per_day",
            "error_rate_by_day",
            "error_rate_by_type",
            "page_load_ms_by_route",
            "auth_failure_rate",
        ):
            with self.subTest(metric=name):
                self.assertEqual(getattr(analysis, name)(start, end, self.engine), [])

    def test_results_are_native_json_values_and_repeatable(self):
        for name in (
            "events_per_day",
            "error_rate_by_day",
            "error_rate_by_type",
            "page_load_ms_by_route",
            "auth_failure_rate",
        ):
            with self.subTest(metric=name):
                first = self.call_metrics(name)
                self.assertEqual(json.loads(json.dumps(first, allow_nan=False)), first)
                self.assertEqual(getattr(analysis, name)(START, END, self.engine), first)

    def test_sql_filters_time_range_and_event_types(self):
        statements = []

        def capture(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", capture)
        self.addCleanup(event.remove, self.engine, "before_cursor_execute", capture)
        for name in (
            "events_per_day",
            "error_rate_by_day",
            "error_rate_by_type",
            "page_load_ms_by_route",
            "auth_failure_rate",
        ):
            getattr(analysis, name)(START, END, self.engine)
        self.assertEqual(len(statements), 5)
        self.assertTrue(all("timestamp >=" in sql and "timestamp <" in sql for sql in statements))
        for index in (3, 4):
            self.assertIn("event_type IN", statements[index])

    def test_analysis_module_has_no_loops_or_comprehensions(self):
        source = Path(analysis.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = (ast.For, ast.While, ast.AsyncFor, ast.comprehension)
        self.assertFalse(any(isinstance(node, forbidden) for node in ast.walk(tree)))

    def test_resolve_period_defaults_limits_and_utc_conversion(self):
        now = datetime(2026, 11, 19, 12, tzinfo=UTC)
        start, end = analysis.resolve_period(now=now)
        self.assertEqual(end, now)
        self.assertEqual(start, now - timedelta(days=7))
        self.assertEqual(analysis.resolve_period(start_date=now - timedelta(days=1), now=now), (now - timedelta(days=1), now))
        self.assertEqual(analysis.resolve_period(end_date=now), (now - timedelta(days=7), now))
        self.assertEqual(analysis.as_utc(datetime(2026, 11, 19)), now.replace(hour=0))
        offset = datetime(2026, 11, 19, 12, tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual(analysis.as_utc(offset), datetime(2026, 11, 19, 10, tzinfo=UTC))
        with self.assertRaises(ValueError):
            analysis.resolve_period(start_date=now, end_date=now)
        with self.assertRaises(ValueError):
            analysis.resolve_period(start_date=now - timedelta(days=91), end_date=now)

    def test_build_report_has_exact_shape(self):
        report = analysis.build_report(START, END, self.engine)
        self.assertEqual(set(report), {"period", "metrics"})
        self.assertEqual(report["period"], {"from": START.isoformat(), "to": END.isoformat()})
        self.assertEqual(set(report["metrics"]), {
            "events_per_day",
            "error_rate_by_type",
            "error_rate_by_day",
            "page_load_ms_by_route",
            "auth_failure_rate",
        })


if __name__ == "__main__":
    unittest.main()
