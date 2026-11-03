"""Synthetic integration tests for the authenticated incident API."""

import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api import database
from services.api.app import main
from services.api.auth_security import get_current_user
from services.api.models import UserResponse, UserRole
from services.api.routes import incidents


def incident_payload(**overrides):
    return {
        "title": "Synthetic incident",
        "description": "A synthetic incident description",
        "category": "supply_issue",
        "status": "open",
        "origin": "customer",
        "branch": "central",
    } | overrides


class IncidentEndpointsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        database_path = Path(self.temporary.name) / "incidents.json"
        self.database_patch = patch.object(
            database, "INCIDENTS_DATABASE_PATH", database_path
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)

        self.user_override = UserResponse(
            id=1,
            email="incidents-tests@example.com",
            is_active=True,
            role=UserRole.user,
            created_at="2026-01-01T00:00:00+00:00",
        )
        main.app.dependency_overrides[get_current_user] = lambda: self.user_override
        self.addCleanup(main.app.dependency_overrides.clear)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def create_incident(self, **overrides):
        response = self.client.post(
            "/api/incidents",
            json=incident_payload(**overrides),
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_generates_id_and_utc_timestamps(self):
        response = self.client.post(
            "/api/incidents",
            json=incident_payload(
                category="customer_complaint",
                origin="branch",
                branch="medellin_centro",
            ),
        )
        self.assertEqual(response.status_code, 201, response.text)
        record = response.json()
        self.assertIsInstance(record["id"], int)
        self.assertEqual(record["category"], "customer_complaint")
        self.assertEqual(record["origin"], "branch")
        self.assertEqual(record["branch"], "medellin_centro")
        self.assertTrue(
            record["created_at"].endswith("+00:00")
            or record["created_at"].endswith("Z")
        )
        self.assertEqual(record["created_at"], record["updated_at"])

    def test_missing_fields_return_400_with_field_specific_messages(self):
        response = self.client.post(
            "/api/incidents",
            json={
                "description": "Synthetic description",
                "category": "supply_issue",
                "status": "open",
                "origin": "customer",
                "branch": "central",
            },
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["detail"], "Datos no válidos.")
        self.assertIn(
            {"field": "title", "message": "El título es obligatorio."},
            payload["errors"],
        )

    def test_blank_text_and_disallowed_values_return_400(self):
        for request_payload, expected_field in (
            (incident_payload(title="   "), "title"),
            (incident_payload(category="not_a_category"), "category"),
            (incident_payload(status="not_a_status"), "status"),
            (incident_payload(origin="not_an_origin"), "origin"),
            (incident_payload(branch="not_a_branch"), "branch"),
        ):
            with self.subTest(field=expected_field):
                response = self.client.post(
                    "/api/incidents",
                    json=request_payload,
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["detail"], "Datos no válidos.")
                self.assertIn(
                    expected_field,
                    {error["field"] for error in response.json()["errors"]},
                )

    def test_list_filters_are_combinable_and_invalid_filters_return_400(self):
        target = self.create_incident(
            status="open",
            origin="customer",
            branch="central",
            category="supply_issue",
        )
        self.create_incident(
            status="in_progress",
            origin="branch",
            branch="medellin_centro",
            category="equipment_failure",
        )

        response = self.client.get(
            "/api/incidents",
            params={
                "status": "open",
                "origin": "customer",
                "branch": "central",
                "category": "supply_issue",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [target["id"]])

        invalid = self.client.get("/api/incidents", params={"status": "invalid"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["errors"][0]["field"], "status")

    def test_detail_returns_404_for_missing_incident(self):
        response = self.client.get("/api/incidents/999999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"detail": "No se encontró la incidencia."},
        )

    def test_status_transitions_and_final_states(self):
        created = self.create_incident()
        incident_id = created["id"]

        in_progress = self.client.patch(
            f"/api/incidents/{incident_id}/status",
            json={"status": "in_progress"},
        )
        self.assertEqual(in_progress.status_code, 200, in_progress.text)
        self.assertEqual(in_progress.json()["status"], "in_progress")
        self.assertNotEqual(
            in_progress.json()["updated_at"],
            created["updated_at"],
        )

        resolved = self.client.patch(
            f"/api/incidents/{incident_id}/status",
            json={"status": "resolved"},
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(resolved.json()["status"], "resolved")
        self.assertEqual(
            resolved.json()["description"],
            created["description"],
        )

        final_transition = self.client.patch(
            f"/api/incidents/{incident_id}/status",
            json={"status": "open"},
        )
        self.assertEqual(final_transition.status_code, 400)
        self.assertEqual(final_transition.json()["detail"], "Datos no válidos.")
        self.assertEqual(final_transition.json()["errors"][0]["field"], "status")

    def test_open_can_be_discarded_but_discarded_is_final(self):
        created = self.create_incident()
        discarded = self.client.patch(
            f"/api/incidents/{created['id']}/status",
            json={"status": "discarded"},
        )
        self.assertEqual(discarded.status_code, 200)
        self.assertEqual(discarded.json()["status"], "discarded")

        invalid = self.client.patch(
            f"/api/incidents/{created['id']}/status",
            json={"status": "in_progress"},
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["errors"][0]["field"], "status")

    def test_summary_returns_all_zero_values_for_empty_database(self):
        response = self.client.get("/api/incidents/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 0)
        for group in ("by_status", "by_category", "by_origin", "by_branch"):
            self.assertTrue(payload[group])
            self.assertEqual(set(payload[group].values()), {0})

    def test_summary_counts_each_allowed_group(self):
        self.create_incident(
            status="in_progress",
            origin="branch",
            branch="medellin_centro",
            category="equipment_failure",
        )
        self.create_incident(
            status="discarded",
            origin="internal",
            branch="central",
            category="other",
        )

        payload = self.client.get("/api/incidents/summary").json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["by_status"]["in_progress"], 1)
        self.assertEqual(payload["by_status"]["discarded"], 1)
        self.assertEqual(payload["by_category"]["equipment_failure"], 1)
        self.assertEqual(payload["by_category"]["other"], 1)
        self.assertEqual(payload["by_origin"]["branch"], 1)
        self.assertEqual(payload["by_origin"]["internal"], 1)
        self.assertEqual(payload["by_branch"]["medellin_centro"], 1)
        self.assertEqual(payload["by_branch"]["central"], 1)

    def test_all_incident_routes_require_authentication(self):
        override = main.app.dependency_overrides.pop(get_current_user)
        try:
            for method, path, kwargs in (
                ("get", "/api/incidents", {}),
                ("post", "/api/incidents", {"json": incident_payload()}),
                ("get", "/api/incidents/summary", {}),
                ("get", "/api/incidents/1", {}),
                (
                    "patch",
                    "/api/incidents/1/status",
                    {"json": {"status": "in_progress"}},
                ),
            ):
                with self.subTest(method=method, path=path):
                    response = self.client.request(method, path, **kwargs)
                    self.assertEqual(response.status_code, 401)
        finally:
            main.app.dependency_overrides[get_current_user] = override

    def test_unexpected_error_is_generic_and_does_not_expose_traceback(self):
        with self.assertLogs("services.api.routes.incidents", level="ERROR") as captured:
            with patch.object(
                incidents,
                "get_incidents_tables",
                side_effect=RuntimeError("test-only internal failure"),
            ):
                response = self.client.get("/api/incidents")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"detail": "Error interno del servicio."},
        )
        self.assertNotIn("Traceback", response.text)
        self.assertNotIn("test-only internal failure", response.text)
        self.assertIn("RuntimeError", "\n".join(captured.output))
        self.assertNotIn("test-only internal failure", "\n".join(captured.output))

    def test_unexpected_analysis_error_is_generic_and_does_not_log_details(self):
        csv_content = (
            "incident_id,date,location_id,category,description,status,"
            "customer_id,satisfaction_score,reporter_id\n"
            "SYN-002,2026-10-28,COL-01,SUPPLY,Synthetic supply issue,OPEN,,,SYN-EMP-2\n"
        )
        with (
            self.assertLogs("services.api.app.main", level="ERROR") as captured,
            patch.object(
                main,
                "calculate_metrics",
                side_effect=RuntimeError("internal calculation detail"),
            ),
        ):
            response = self.client.post(
                "/api/incidents/analyze",
                files={"file": ("synthetic.csv", csv_content, "text/csv")},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"detail": "Error interno al analizar el fichero."},
        )
        log_output = "\n".join(captured.output)
        self.assertIn("RuntimeError", log_output)
        self.assertNotIn("internal calculation detail", response.text + log_output)
        self.assertNotIn("Traceback", response.text + log_output)

    def test_analyze_bad_extension_keeps_detail_only_400_response(self):
        response = self.client.post(
            "/api/incidents/analyze",
            files={"file": ("synthetic.txt", b"not a CSV", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "El fichero debe tener extensión .csv."},
        )

    def test_auth_validation_still_returns_422(self):
        registration = self.client.post("/users", json={})
        login = self.client.post("/auth/login", data={})
        self.assertEqual(registration.status_code, 422)
        self.assertEqual(login.status_code, 422)

    def test_existing_analyze_and_export_routes_still_work(self):
        csv_content = (
            "incident_id,date,location_id,category,description,status,"
            "customer_id,satisfaction_score,reporter_id\n"
            "SYN-001,2026-10-28,COL-01,SUPPLY,Synthetic supply issue,OPEN,,,SYN-EMP-1\n"
        )
        with patch.object(main, "_latest_metrics", None):
            analyzed = self.client.post(
                "/api/incidents/analyze",
                files={
                    "file": (
                        "synthetic.csv",
                        io.BytesIO(csv_content.encode("utf-8")),
                        "text/csv",
                    )
                },
            )
            exported = self.client.get("/api/incidents/results/export")

        self.assertEqual(analyzed.status_code, 200, analyzed.text)
        self.assertEqual(analyzed.json()["valid_records"], 1)
        self.assertEqual(exported.status_code, 200)
        self.assertTrue(exported.text.startswith("metric,value,percentage"))


if __name__ == "__main__":
    unittest.main()
