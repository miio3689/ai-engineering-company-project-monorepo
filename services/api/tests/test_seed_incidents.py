"""Synthetic tests for the incident CSV seed; never use the real database."""

import csv
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from scripts import seed_incidents
from services.api import database
from services.api.app import main
from services.api.auth_security import get_current_user
from services.api.models import UserResponse, UserRole

CSV_FIELDS = (
    "incident_id",
    "date",
    "location_id",
    "category",
    "description",
    "status",
    "customer_id",
    "satisfaction_score",
    "reporter_id",
)


def csv_row(**overrides):
    return {
        "incident_id": "SYN-001",
        "date": "2026-10-28",
        "location_id": "COL-01",
        "category": "SUPPLY",
        "description": "Synthetic incident description",
        "status": "OPEN",
        "customer_id": "",
        "satisfaction_score": "",
        "reporter_id": "SYN-EMP-1",
    } | overrides


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


class SeedIncidentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.csv_path = self.directory / "synthetic.csv"
        self.database_patch = patch.object(
            database,
            "INCIDENTS_DATABASE_PATH",
            self.directory / "incidents.json",
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)

    def run_seed(self, rows: list[dict[str, str]]):
        write_csv(self.csv_path, rows)
        output = StringIO()
        with redirect_stdout(output):
            result = seed_incidents.seed_csv(self.csv_path)
        return result, output.getvalue()

    def test_maps_csv_status_category_and_branch_values(self):
        rows = [
            csv_row(
                incident_id="SYN-EQUIPMENT",
                category="EQUIPMENT",
                location_id="COL-01",
            ),
            csv_row(
                incident_id="SYN-FOOD",
                category="FOOD_QUALITY",
                location_id="COL-10",
                status="CLOSED",
                satisfaction_score="4",
            ),
            csv_row(
                incident_id="SYN-CUSTOMER",
                category="CUSTOMER_COMPLAINT",
                location_id="COL-02",
                status="DISCARDED",
            ),
            csv_row(
                incident_id="SYN-STAFF",
                category="STAFF",
                location_id="FLA-01",
            ),
            csv_row(
                incident_id="SYN-SUPPLY",
                category="SUPPLY",
                location_id="FLA-04",
            ),
        ]
        result, _ = self.run_seed(rows)

        self.assertEqual(result.valid_rows, 5)
        self.assertEqual(result.inserted, 5)
        with database.get_incidents_tables() as (incidents, _):
            stored = [dict(record) for record in incidents.all()]

        by_id = {
            record["incident_id"]: record
            for record in rows
        }
        actual = {
            source_id: next(
                record
                for record in stored
                if record["description"] == by_id[source_id]["description"]
                and record["branch"]
                == {
                    "SYN-EQUIPMENT": "medellin_centro",
                    "SYN-FOOD": "central",
                    "SYN-CUSTOMER": "medellin_laureles",
                    "SYN-STAFF": "miami_doral",
                    "SYN-SUPPLY": "orlando_international",
                }[source_id]
            )
            for source_id in by_id
        }
        self.assertEqual(actual["SYN-EQUIPMENT"]["category"], "equipment_failure")
        self.assertEqual(actual["SYN-FOOD"]["category"], "customer_complaint")
        self.assertEqual(actual["SYN-FOOD"]["status"], "resolved")
        self.assertEqual(actual["SYN-FOOD"]["branch"], "central")
        self.assertEqual(actual["SYN-CUSTOMER"]["category"], "customer_complaint")
        self.assertEqual(actual["SYN-CUSTOMER"]["status"], "discarded")
        self.assertEqual(actual["SYN-STAFF"]["category"], "staff_issue")
        self.assertEqual(actual["SYN-SUPPLY"]["category"], "supply_issue")
        self.assertTrue(all(record["origin"] == "customer" for record in actual.values()))

    def test_title_description_utc_date_and_source_key_are_stored_correctly(self):
        description = "  " + ("x" * 130) + "  "
        self.run_seed(
            [
                csv_row(
                    incident_id="SYN-TITLE",
                    description=description,
                )
            ]
        )

        with database.get_incidents_tables() as (incidents, seed_keys):
            stored = incidents.all()[0]
            keys = seed_keys.all()

        self.assertEqual(stored["title"], description[:120].strip())
        self.assertEqual(stored["description"], description)
        self.assertEqual(stored["created_at"], "2026-10-28T00:00:00+00:00")
        self.assertTrue(stored["updated_at"].endswith("+00:00"))
        self.assertEqual(stored["origin"], "customer")
        self.assertNotIn("incident_id", stored)
        self.assertNotIn("source_key", stored)
        self.assertEqual(keys[0]["source_key"], "incident_id:SYN-TITLE")
        self.assertEqual(keys[0]["incident_document_id"], stored.doc_id)

    def test_second_run_skips_duplicate_without_creating_another_document(self):
        rows = [csv_row(incident_id="SYN-IDEMPOTENT")]
        first, _ = self.run_seed(rows)
        second, _ = self.run_seed(rows)

        self.assertEqual(first.inserted, 1)
        self.assertEqual(second.inserted, 0)
        self.assertEqual(second.duplicates, 1)
        with database.get_incidents_tables() as (incidents, seed_keys):
            self.assertEqual(len(incidents.all()), 1)
            self.assertEqual(len(seed_keys.all()), 1)

    def test_missing_source_id_uses_title_and_created_at_fallback(self):
        rows = [csv_row(incident_id="")]
        first, _ = self.run_seed(rows)
        second, _ = self.run_seed(rows)

        self.assertEqual(first.inserted, 1)
        self.assertEqual(second.duplicates, 1)
        with database.get_incidents_tables() as (incidents, seed_keys):
            stored = incidents.all()[0]
            source_key = seed_keys.all()[0]["source_key"]
        self.assertTrue(source_key.startswith("title_created_at:"))
        self.assertNotIn(source_key, stored.values())

    def test_invalid_rows_are_reported_without_printing_description(self):
        sensitive_description = "SYNTHETIC_DESCRIPTION_SHOULD_NOT_APPEAR"
        rows = [
            csv_row(
                incident_id="SYN-INVALID-VALIDATION",
                location_id="INVALID",
                description=sensitive_description,
            ),
            csv_row(
                incident_id="SYN-INVALID-STATUS",
                status="UNMAPPED",
            ),
            csv_row(
                incident_id="SYN-INVALID-DATE",
                date="not-a-date",
            ),
            csv_row(
                incident_id="SYN-EMPTY-TITLE",
                description=(" " * 120) + "valid",
            ),
        ]
        result, output = self.run_seed(rows)

        self.assertEqual(result.rows_read, 4)
        self.assertEqual(result.valid_rows, 0)
        self.assertEqual(result.discarded, 4)
        self.assertEqual(result.discarded_by_reason["missing_or_invalid_location_id"], 1)
        self.assertEqual(result.discarded_by_reason["unmapped_status"], 1)
        self.assertEqual(result.discarded_by_reason["invalid_date"], 1)
        self.assertEqual(result.discarded_by_reason["empty_title"], 1)
        self.assertIn("incident_id=\"SYN-INVALID-STATUS\"", output)
        self.assertIn("estado sin mapa", output)
        self.assertIn("fecha no parseable", output)
        self.assertIn("título vacío", output)
        self.assertNotIn(sensitive_description, output)
        with database.get_incidents_tables() as (incidents, _):
            self.assertEqual(incidents.all(), [])

    def test_reported_summary_totals_match_seeded_records(self):
        rows = [
            csv_row(
                incident_id="SYN-SUMMARY-1",
                status="OPEN",
                category="SUPPLY",
            ),
            csv_row(
                incident_id="SYN-SUMMARY-2",
                status="CLOSED",
                category="FOOD_QUALITY",
                satisfaction_score="5",
                location_id="COL-10",
            ),
        ]
        result, _ = self.run_seed(rows)
        self.assertEqual(result.inserted, 2)

        main.app.dependency_overrides[get_current_user] = lambda: UserResponse(
            id=1,
            email="seed-summary-tests@example.com",
            is_active=True,
            role=UserRole.user,
            created_at="2026-01-01T00:00:00+00:00",
        )
        self.addCleanup(main.app.dependency_overrides.clear)
        with TestClient(main.app) as client:
            response = client.get("/api/incidents/summary")

        self.assertEqual(response.status_code, 200)
        summary = response.json()
        self.assertEqual(summary["total"], result.inserted)
        self.assertEqual(summary["by_status"]["open"], 1)
        self.assertEqual(summary["by_status"]["resolved"], 1)
        self.assertEqual(summary["by_category"]["supply_issue"], 1)
        self.assertEqual(summary["by_category"]["customer_complaint"], 1)

    def test_missing_csv_returns_clear_error_without_stack_trace(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            exit_code = seed_incidents.main(
                [str(self.directory / "does-not-exist.csv")]
            )
        self.assertEqual(exit_code, 1)
        self.assertIn("No se encontró el archivo CSV.", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
