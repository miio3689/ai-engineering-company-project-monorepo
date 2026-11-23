"""SQLite-only tests for pipeline run locking and lifecycle management."""

from datetime import date, datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from sqlalchemy import DateTime, bindparam, text

from data.pipelines import runs
from services.api.tests.pipeline_helpers import create_schema, make_engine


START = date(2026, 11, 16)
END = date(2026, 11, 23)


class PipelineRunsTests(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine()
        create_schema(self.engine)
        self.addCleanup(self.engine.dispose)
        self.db_patch = patch("data.pipelines.db.get_engine", return_value=self.engine)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def open(self, **kwargs):
        return runs.open_run(
            trigger_type="manual",
            window_start=START,
            window_end=END,
            engine=self.engine,
            **kwargs,
        )

    def row(self, run_id):
        with self.engine.connect() as connection:
            return connection.execute(
                text("select * from reporting.pipeline_runs where run_id = :run_id"),
                {"run_id": run_id},
            ).mappings().one()

    def test_open_run_creates_running_record_and_lock(self):
        run_id = self.open()
        row = self.row(run_id)
        self.assertEqual(row["status"], "running")
        self.assertEqual(row["phase"], "open")
        self.assertEqual(row["pipeline_name"], runs.PIPELINE_NAME)
        self.assertEqual(row["trigger_type"], "manual")

    def test_second_open_run_reports_active_lock_id(self):
        run_id = self.open()
        with self.assertRaises(runs.PipelineLocked) as raised:
            self.open()
        self.assertEqual(raised.exception.active_run_id, run_id)

    def test_stale_running_run_is_failed_and_next_run_resumes_it(self):
        stale_id = "stale-run-id"
        started = datetime.now(timezone.utc) - timedelta(minutes=runs.STALE_RUN_MINUTES + 1)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "insert into reporting.pipeline_runs "
                    "(run_id, pipeline_name, trigger_type, window_start, window_end, "
                    "status, phase, started_at, details) values "
                    "(:id, :name, 'schedule', :start, :end, 'running', 'extract', :started, '{}')"
                    # Same timestamp type as runs.open_run, so the stale cutoff compares like for like.
                ).bindparams(bindparam("started", type_=DateTime(timezone=True))),
                {
                    "id": stale_id,
                    "name": runs.PIPELINE_NAME,
                    "start": START.isoformat(),
                    "end": END.isoformat(),
                    "started": started,
                },
            )
        new_id = self.open()
        stale = self.row(stale_id)
        self.assertEqual(stale["status"], "failed")
        self.assertIn("abandoned", stale["error_message"])
        self.assertEqual(self.row(new_id)["resumed_from_run_id"], stale_id)

    def test_open_run_adopts_existing_run_and_rejects_missing_run(self):
        run_id = self.open()
        adopted = runs.open_run(
            trigger_type="manual",
            window_start=START,
            window_end=END,
            run_id=run_id,
            prefect_flow_run_id="prefect-test-id",
            engine=self.engine,
        )
        self.assertEqual(adopted, run_id)
        self.assertEqual(self.row(run_id)["prefect_flow_run_id"], "prefect-test-id")
        with self.assertRaises(ValueError):
            runs.open_run(
                trigger_type="manual",
                window_start=START,
                window_end=END,
                run_id="missing",
                engine=self.engine,
            )

    def test_phase_and_close_persist_status_counters_error_and_details(self):
        run_id = self.open()
        runs.set_phase(run_id, "load", engine=self.engine)
        runs.close_run(
            run_id=run_id,
            status="failed",
            phase="load",
            rows_extracted=12,
            rows_after_dedup=10,
            rows_rejected=2,
            rows_inserted=3,
            rows_updated=4,
            rows_unchanged=5,
            error_message="load failed",
            details={"quality": ["warning"]},
            engine=self.engine,
        )
        row = self.row(run_id)
        self.assertEqual(row["phase"], "load")
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["rows_extracted"], 12)
        self.assertEqual(row["rows_after_dedup"], 10)
        self.assertEqual(row["rows_rejected"], 2)
        self.assertEqual(row["rows_inserted"], 3)
        self.assertEqual(row["rows_updated"], 4)
        self.assertEqual(row["rows_unchanged"], 5)
        self.assertEqual(row["error_message"], "load failed")
        latest = runs.get_latest_run(engine=self.engine)
        self.assertEqual(latest["details"], {"quality": ["warning"]})
        self.assertIsInstance(latest["run_id"], str)

    def test_latest_run_returns_none_when_empty_and_latest_metadata_when_present(self):
        self.assertIsNone(runs.get_latest_run(engine=self.engine))
        first = self.open()
        runs.close_run(
            run_id=first,
            status="completed",
            phase="close",
            details={"first": True},
            engine=self.engine,
        )
        second = self.open()
        latest = runs.get_latest_run(engine=self.engine)
        self.assertEqual(latest["run_id"], second)
        self.assertIsInstance(latest["window_start"], date)
        self.assertEqual(latest["details"], {})

    def test_trigger_opens_lock_before_launch_and_returns_run_id(self):
        def verify_launch(run_id, reference_date, lookback_weeks):
            self.assertEqual(self.row(run_id)["status"], "running")
            self.assertEqual(lookback_weeks, 3)

        with patch.object(runs, "launch_flow_process", side_effect=verify_launch) as launch:
            result = runs.trigger_run(
                reference_date=START,
                lookback_weeks=3,
                engine=self.engine,
            )
        self.assertEqual(result["status"], "running")
        launch.assert_called_once()
        self.assertEqual(result["run_id"], launch.call_args.args[0])

    def test_trigger_launch_failure_closes_run_failed_and_reraises(self):
        with patch.object(
            runs, "launch_flow_process", side_effect=OSError("cannot launch")
        ):
            with self.assertRaisesRegex(OSError, "cannot launch"):
                runs.trigger_run(engine=self.engine)
        latest = runs.get_latest_run(engine=self.engine)
        self.assertEqual(latest["status"], "failed")
        self.assertEqual(latest["phase"], "open")
        self.assertIn("launch failed", latest["error_message"])

    def test_trigger_with_active_run_does_not_launch(self):
        self.open()
        with patch.object(runs, "launch_flow_process") as launch:
            with self.assertRaises(runs.PipelineLocked):
                runs.trigger_run(engine=self.engine)
        launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
