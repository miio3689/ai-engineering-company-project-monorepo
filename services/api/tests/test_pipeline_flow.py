"""Integration tests for the Prefect flow using only an in-memory SQLite engine."""

from contextlib import ExitStack
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from prefect.testing.utilities import prefect_test_harness
from sqlalchemy import event, text

from data.pipelines import pipeline, queries, runs
from services.api.tests.pipeline_helpers import (
    create_schema,
    insert_event,
    make_engine,
    seed_locations,
)


REFERENCE = date(2026, 11, 18)
WINDOW_START = date(2026, 10, 26)
WINDOW_END = date(2026, 11, 23)


class PipelineFlowTests(unittest.TestCase):
    def setUp(self):
        self.prefect_context = prefect_test_harness()
        self.prefect_context.__enter__()
        self.addCleanup(self.prefect_context.__exit__, None, None, None)
        self.engine = make_engine()
        create_schema(self.engine)
        seed_locations(self.engine)
        self.addCleanup(self.engine.dispose)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(
            patch("data.pipelines.db.get_engine", return_value=self.engine)
        )
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stack.enter_context(
            patch.object(pipeline, "EVAL_DIR", Path(self.temp.name) / "eval")
        )
        self._use_fast_tasks(retries=0)
        self._seed_events()

    def _use_fast_tasks(self, retries):
        for name in (
            "open_run_step",
            "extract_telemetry_events",
            "extract_location_dim",
            "check_source_health",
            "load_weekly_location_performance",
            "close_run_step",
        ):
            task = getattr(pipeline, name)
            self.stack.enter_context(
                patch.object(
                    pipeline,
                    name,
                    task.with_options(retries=retries, retry_delay_seconds=0),
                )
            )

    def _seed_events(self):
        self.inbound_time = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
        self.waste_time = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
        insert_event(
            self.engine,
            "inbound_order_created",
            self.inbound_time,
            {
                "location_id": 1,
                "country": "CO",
                "currency": "COP",
                "quantity": 2,
                "unit_cost": 10,
                "inbound_order_id": 101,
            },
        )
        insert_event(
            self.engine,
            "stock_waste_registered",
            self.waste_time,
            {
                "location_id": 1,
                "country": "CO",
                "currency": "COP",
                "quantity": 1,
                "unit_cost": 5,
                "outbound_order_id": 201,
            },
        )
    def _run(self, **kwargs):
        return pipeline.weekly_location_performance_flow(
            reference_date=REFERENCE,
            lookback_weeks=4,
            **kwargs,
        )

    def _published_rows(self):
        with self.engine.connect() as connection:
            return connection.execute(
                text(
                    "select id, location_id, week_start, total_purchase_cost, "
                    "total_waste_cost, waste_ratio, computed_at "
                    "from reporting.weekly_location_performance "
                    "order by location_id, week_start"
                )
            ).mappings().all()

    def _latest_run(self):
        return runs.get_latest_run(engine=self.engine)

    def test_complete_run_persists_expected_metrics_and_only_reads_telemetry(self):
        with patch.object(
            queries,
            "read_domain_rows",
            return_value=(
                pd.DataFrame({"created_at": [self.inbound_time]}),
                pd.DataFrame({"created_at": [self.waste_time]}),
            ),
        ):
            before = self._telemetry_snapshot()
            result = self._run()
        after = self._telemetry_snapshot()
        rows = self._published_rows()
        self.assertEqual(len(rows), 16)
        local_week = next(row for row in rows if row["location_id"] == "1" and row["week_start"] == "2026-11-16")
        self.assertEqual(local_week["total_purchase_cost"], 20)
        self.assertEqual(local_week["total_waste_cost"], 5)
        self.assertEqual(local_week["waste_ratio"], 0.25)
        self.assertEqual(result["status"], "completed")
        run = self._latest_run()
        self.assertEqual(run["rows_extracted"], 2)
        self.assertEqual(run["rows_after_dedup"], 2)
        self.assertEqual(run["rows_inserted"], 16)
        self.assertIn("transform", run["details"])
        self.assertEqual(before, after)

    def test_second_run_is_idempotent_including_identifiers_and_computed_at(self):
        with patch.object(
            queries,
            "read_domain_rows",
            return_value=(
                pd.DataFrame({"created_at": [self.inbound_time]}),
                pd.DataFrame({"created_at": [self.waste_time]}),
            ),
        ):
            self._run()
        before = self._published_rows()
        with patch.object(
            queries,
            "read_domain_rows",
            return_value=(
                pd.DataFrame({"created_at": [self.inbound_time]}),
                pd.DataFrame({"created_at": [self.waste_time]}),
            ),
        ):
            result = self._run()
        after = self._published_rows()
        self.assertEqual([dict(row) for row in before], [dict(row) for row in after])
        self.assertEqual(result["rows_inserted"], 0)
        self.assertEqual(result["rows_updated"], 0)
        self.assertEqual(result["rows_unchanged"], len(before))

    def test_transform_cache_reuses_result_until_event_ids_change(self):
        calls = []
        from data.process import weekly_location_performance as process

        original = process.transform_weekly_metrics

        def counted(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        with patch.object(process, "transform_weekly_metrics", side_effect=counted):
            with patch.object(
                queries,
                "read_domain_rows",
                return_value=(
                    pd.DataFrame({"created_at": [self.inbound_time]}),
                    pd.DataFrame({"created_at": [self.waste_time]}),
                ),
            ):
                self._run()
                self._run()
                self.assertEqual(len(calls), 1)
                insert_event(
                    self.engine,
                    "stock_threshold_triggered",
                    self.waste_time + timedelta(minutes=5),
                    {"location_id": 1, "currency": "COP", "triggering_outbound_order_id": 202},
                )
                self._run()
        self.assertEqual(len(calls), 2)

    def test_extraction_retries_then_succeeds_and_permanent_failure_closes_run(self):
        self._use_fast_tasks(retries=3)
        original = queries.extract_events
        calls = []

        def fail_once(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("temporary extraction failure")
            return original(*args, **kwargs)

        with patch.object(queries, "extract_events", side_effect=fail_once):
            with patch.object(
                queries,
                "read_domain_rows",
                return_value=(
                    pd.DataFrame({"created_at": [self.inbound_time]}),
                    pd.DataFrame({"created_at": [self.waste_time]}),
                ),
            ):
                result = self._run()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(calls), 2)

        with self.engine.begin() as connection:
            connection.execute(text("delete from reporting.weekly_location_performance"))
        with patch.object(
            queries, "extract_events", side_effect=RuntimeError("permanent extraction failure")
        ):
            with self.assertRaisesRegex(RuntimeError, "permanent extraction failure"):
                self._run()
        failed = self._latest_run()
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["phase"], "extract")
        self.assertIn("permanent extraction failure", failed["error_message"])
        self.assertEqual(self._published_rows(), [])

    def test_upsert_failure_is_atomic_and_retrying_flow_can_publish_cleanly(self):
        with patch.object(
            queries,
            "read_domain_rows",
            return_value=(
                pd.DataFrame({"created_at": [self.inbound_time]}),
                pd.DataFrame({"created_at": [self.waste_time]}),
            ),
        ):
            def fail_weekly_insert(_conn, _cursor, statement, _params, _context, _many):
                if "insert into reporting.weekly_location_performance" in statement.lower():
                    raise RuntimeError("simulated atomic load failure")

            event.listen(self.engine, "before_cursor_execute", fail_weekly_insert)
            try:
                with self.assertRaisesRegex(RuntimeError, "simulated atomic load failure"):
                    self._run()
            finally:
                event.remove(self.engine, "before_cursor_execute", fail_weekly_insert)
        self.assertEqual(self._published_rows(), [])
        self.assertEqual(self._latest_run()["phase"], "load")
        with patch.object(
            queries,
            "read_domain_rows",
            return_value=(
                pd.DataFrame({"created_at": [self.inbound_time]}),
                pd.DataFrame({"created_at": [self.waste_time]}),
            ),
        ):
            self._run()
        self.assertEqual(len(self._published_rows()), 16)

    def test_optional_health_and_snapshot_failures_do_not_abort_load(self):
        with patch.object(
            queries,
            "read_domain_rows",
            side_effect=RuntimeError("health unavailable"),
        ):
            result = self._run()
        self.assertEqual(result["status"], "completed_with_warnings")
        self.assertIn("check_source_health_failed", result["warnings"])
        self.assertEqual(len(self._published_rows()), 16)

        with self.engine.begin() as connection:
            connection.execute(text("delete from reporting.weekly_location_performance"))
        file_path = Path(self.temp.name) / "not-a-directory"
        file_path.write_text("block", encoding="utf-8")
        with patch.object(pipeline, "EVAL_DIR", file_path):
            with patch.object(
                queries,
                "read_domain_rows",
                return_value=(
                    pd.DataFrame({"created_at": [self.inbound_time]}),
                    pd.DataFrame({"created_at": [self.waste_time]}),
                ),
            ):
                result = self._run()
        self.assertEqual(result["status"], "completed_with_warnings")
        self.assertIn("eval_snapshot_failed", result["warnings"])
        self.assertEqual(len(self._published_rows()), 16)

    def test_no_source_data_preserves_existing_published_rows(self):
        with patch.object(
            queries,
            "read_domain_rows",
            return_value=(
                pd.DataFrame({"created_at": [self.inbound_time]}),
                pd.DataFrame({"created_at": [self.waste_time]}),
            ),
        ):
            self._run()
        before = [dict(row) for row in self._published_rows()]
        with self.engine.begin() as connection:
            connection.execute(text("delete from telemetry_events"))
        result = self._run()
        self.assertEqual(result["status"], "completed_with_warnings")
        self.assertIn("no_source_data", result["warnings"])
        self.assertEqual(before, [dict(row) for row in self._published_rows()])

    def test_late_event_revises_only_its_published_week(self):
        with patch.object(
            queries,
            "read_domain_rows",
            return_value=(
                pd.DataFrame({"created_at": [self.inbound_time]}),
                pd.DataFrame({"created_at": [self.waste_time]}),
            ),
        ):
            self._run()
            late_time = datetime(2026, 11, 16, 18, tzinfo=timezone.utc)
            insert_event(
                self.engine,
                "inbound_order_created",
                late_time,
                {
                    "location_id": 1,
                    "country": "CO",
                    "currency": "COP",
                    "quantity": 1,
                    "unit_cost": 10,
                    "inbound_order_id": 102,
                },
            )
            result = self._run()
        self.assertEqual(result["rows_updated"], 1)
        self.assertEqual(self._latest_run()["details"]["weeks_revised"], ["2026-11-16"])

    def test_active_run_skips_without_changing_published_rows(self):
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "insert into reporting.weekly_location_performance "
                    "(location_id, country, week_start, currency) "
                    "values ('1', 'CO', '2026-11-16', 'COP')"
                )
            )
        before = [dict(row) for row in self._published_rows()]
        runs.open_run(
            trigger_type="schedule",
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            engine=self.engine,
        )
        result = self._run()
        self.assertEqual(result["status"], "skipped_locked")
        self.assertEqual(before, [dict(row) for row in self._published_rows()])

    def test_empty_location_dimension_fails_run_explicitly(self):
        with self.engine.begin() as connection:
            connection.execute(text("delete from reporting.location_dim"))
        with self.assertRaisesRegex(RuntimeError, "location_dim"):
            self._run()
        self.assertEqual(self._latest_run()["status"], "failed")
        self.assertEqual(self._latest_run()["phase"], "extract")

    def test_data_sources_are_unchanged_by_pipeline_writes(self):
        before = self._telemetry_snapshot()
        with patch.object(
            queries,
            "read_domain_rows",
            return_value=(
                pd.DataFrame({"created_at": [self.inbound_time]}),
                pd.DataFrame({"created_at": [self.waste_time]}),
            ),
        ):
            self._run()
        self.assertEqual(before, self._telemetry_snapshot())

    def _telemetry_snapshot(self):
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    'select id, "timestamp", service, event_type, level, value, message, tags '
                    "from telemetry_events order by id"
                )
            ).mappings().all()
        return [json.dumps(dict(row), sort_keys=True, default=str) for row in rows]


if __name__ == "__main__":
    unittest.main()
