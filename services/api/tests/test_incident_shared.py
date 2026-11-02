"""Synthetic tests for shared incident validation and CSV transformations."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from services.api.shared_paths import ensure_shared_python_path

ensure_shared_python_path()

from brasaland_shared.incidents import (
    BRANCH_LABELS,
    CATEGORY_LABELS,
    CSV_CATEGORY_MAP,
    CSV_LOCATION_MAP,
    CSV_STATUS_MAP,
    INCIDENT_ORIGINS,
    INCIDENT_STATUSES,
    ORIGIN_LABELS,
    STATUS_LABELS,
    STATUS_TRANSITIONS,
    transform_csv_record,
    validate_record,
)
from scripts.analyze import calculate_metrics


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def valid_csv_record(**overrides):
    return {
        "incident_id": "SYN-001",
        "date": "2026-10-28",
        "location_id": "COL-01",
        "category": "SUPPLY",
        "description": "A synthetic supply issue",
        "status": "OPEN",
        "customer_id": "",
        "satisfaction_score": "",
        "reporter_id": "SYN-EMP-1",
    } | overrides


class SharedIncidentTests(unittest.TestCase):
    def test_existing_csv_validation_rules_are_preserved(self):
        self.assertEqual(validate_record(valid_csv_record()), (True, []))
        valid, failures = validate_record(
            valid_csv_record(
                location_id="UNKNOWN",
                category="UNKNOWN",
                description="bad",
                reporter_id="",
            )
        )
        self.assertFalse(valid)
        self.assertEqual(
            failures,
            [
                "missing_or_invalid_location_id",
                "missing_or_invalid_category",
                "empty_or_short_description",
                "missing_reporter_id",
            ],
        )

    def test_closed_rows_still_require_a_valid_satisfaction_score(self):
        valid, failures = validate_record(
            valid_csv_record(status="CLOSED", satisfaction_score="")
        )
        self.assertFalse(valid)
        self.assertIn("closed_without_satisfaction_score", failures)

    def test_transform_maps_fields_and_uses_utc_midnight(self):
        transformed = transform_csv_record(
            valid_csv_record(
                status="CLOSED",
                category="FOOD_QUALITY",
                location_id="COL-10",
                description=f"  {'x' * 125}  ",
                satisfaction_score="4",
            )
        )
        self.assertEqual(transformed["title"], "x" * 118)
        self.assertEqual(transformed["description"], f"  {'x' * 125}  ")
        self.assertEqual(transformed["category"], "customer_complaint")
        self.assertEqual(transformed["status"], "resolved")
        self.assertEqual(transformed["origin"], "customer")
        self.assertEqual(transformed["branch"], "central")
        self.assertEqual(transformed["created_at"], "2026-10-28T00:00:00+00:00")

    def test_transform_uses_central_as_the_unmapped_branch_default(self):
        transformed = transform_csv_record(
            valid_csv_record(location_id="UNMAPPED")
        )
        self.assertEqual(transformed["branch"], "central")

    def test_transform_rejects_unmapped_status_category_and_invalid_date(self):
        for overrides, message in (
            ({"status": "UNKNOWN"}, "unsupported CSV status"),
            ({"category": "UNKNOWN"}, "unsupported CSV category"),
            ({"date": "28-10-2026"}, "date must use YYYY-MM-DD format"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    transform_csv_record(valid_csv_record(**overrides))

    def test_model_constants_have_labels_and_terminal_transitions(self):
        self.assertEqual(len(BRANCH_LABELS), 15)
        self.assertEqual(len(CATEGORY_LABELS), 8)
        self.assertEqual(
            set(INCIDENT_STATUSES),
            {"open", "in_progress", "resolved", "discarded"},
        )
        self.assertEqual(set(INCIDENT_ORIGINS), {"customer", "branch", "internal"})
        self.assertEqual(STATUS_LABELS["open"], "Abierta")
        self.assertEqual(CATEGORY_LABELS["pos_system"], "Sistema de caja (TPV)")
        self.assertEqual(ORIGIN_LABELS["customer"], "Cliente")
        self.assertEqual(STATUS_TRANSITIONS["resolved"], frozenset())
        self.assertEqual(STATUS_TRANSITIONS["discarded"], frozenset())
        self.assertEqual(CSV_STATUS_MAP["CLOSED"], "resolved")
        self.assertEqual(CSV_CATEGORY_MAP["EQUIPMENT"], "equipment_failure")
        self.assertEqual(CSV_LOCATION_MAP["COL-10"], "central")

    def test_analyzer_runs_as_script_with_synthetic_csv(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "synthetic.csv"
            csv_path.write_text(
                "incident_id,date,location_id,category,description,status,"
                "customer_id,satisfaction_score,reporter_id\n"
                "SYN-001,2026-10-28,COL-01,SUPPLY,"
                "Synthetic delivery delay,OPEN,,,SYN-EMP-1\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(REPOSITORY_ROOT / "scripts" / "analyze.py"), str(csv_path)],
                input="n\n",
                capture_output=True,
                text=True,
                cwd=REPOSITORY_ROOT,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TOTAL RECORDS IN FILE", result.stdout)
        self.assertIn("Valid records ................ 1", result.stdout)

    def test_analyzer_remains_importable_as_a_module(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from scripts.analyze import validate_record; "
                "assert validate_record({'location_id': 'COL-01', "
                "'category': 'SUPPLY', 'description': 'valid row', "
                "'reporter_id': 'reporter', 'status': 'OPEN'}) == (True, [])",
            ],
            capture_output=True,
            text=True,
            cwd=REPOSITORY_ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_metrics_keep_the_existing_result_shape(self):
        metrics = calculate_metrics([valid_csv_record()])
        self.assertEqual(metrics["valid_records"], 1)
        self.assertEqual(metrics["category_counts"]["SUPPLY"], 1)
        self.assertEqual(metrics["status_counts"]["OPEN"], 1)


if __name__ == "__main__":
    unittest.main()
