"""Integration tests for the mounted supplier router and incident API."""

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api import database, seed, services_auth
from services.api.app import main
from services.api.routes import suppliers


class SupplierEndpointsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path_patch = patch.object(
            database, "DATABASE_PATH", Path(self.temporary.name) / "suppliers.json"
        )
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.auth_path_patch = patch.object(
            services_auth,
            "AUTH_DATABASE_PATH",
            Path(self.temporary.name) / "auth.json",
        )
        self.auth_path_patch.start()
        self.addCleanup(self.auth_path_patch.stop)
        with redirect_stdout(io.StringIO()):
            seed.main()
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.client.headers.update(self._authenticated_headers())
        self.payload = dict(seed.SUPPLIERS_SEED[0], name="Supplier endpoint test")

    def _authenticated_headers(self):
        email = "supplier-tests@example.com"
        password = "supplier-tests-password"
        registration = self.client.post(
            "/users", json={"email": email, "password": password}
        )
        self.assertEqual(registration.status_code, 201)
        login = self.client.post(
            "/auth/login",
            data={"username": email, "password": password},
        )
        self.assertEqual(login.status_code, 200)
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_create_detail_delete(self):
        response = self.client.post("/suppliers", json=self.payload)
        self.assertEqual(response.status_code, 201)
        created = response.json()
        self.assertIsInstance(created["id"], int)
        self.assertTrue(created["updated_at"])
        self.assertEqual(
            {key: created[key] for key in self.payload}, self.payload
        )
        url = f"/suppliers/{created['id']}"
        self.assertEqual(self.client.get(url).json(), created)
        self.assertEqual(len(self.client.get("/suppliers").json()), 16)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(len(self.client.get("/suppliers").json()), 15)

    def test_filters(self):
        for params, names in [
            ({}, [row["name"] for row in seed.SUPPLIERS_SEED]),
            (
                {"country": "USA"},
                [row["name"] for row in seed.SUPPLIERS_SEED if row["country"] == "USA"],
            ),
            (
                {"category": "carne"},
                [row["name"] for row in seed.SUPPLIERS_SEED if "carne" in row["categories"]],
            ),
            ({"country": "USA", "category": "carne"}, ["Miami Meat Distributors LLC"]),
            ({"country": "usa"}, []),
            ({"category": "unknown"}, []),
        ]:
            with self.subTest(params=params):
                response = self.client.get("/suppliers", params=params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row["name"] for row in response.json()], names)

    def test_invalid_create_never_opens_database(self):
        for changes in [
            {"currency": "USD"},
            {"country": "USA", "currency": "COP"},
            {"status": "deleted"},
            {"rate_per_unit": 0},
            {"rate_per_unit": -1},
            {"categories": []},
            {"categories": ["carne", "unknown"]},
            {"id": 123},
            {"updated_at": "2026-01-01T00:00:00Z"},
        ]:
            with self.subTest(changes=changes):
                with patch.object(suppliers, "get_suppliers_table") as open_table:
                    response = self.client.post("/suppliers", json=self.payload | changes)
                    self.assertEqual(response.status_code, 422)
                    open_table.assert_not_called()

    def test_rate_updates_only_rate_and_timestamp(self):
        before = self.client.get("/suppliers/1").json()
        response = self.client.patch("/suppliers/1/rate", json={"rate_per_unit": 29000})
        self.assertEqual(response.status_code, 200)
        after = response.json()
        self.assertEqual(after["rate_per_unit"], 29000)
        self.assertGreater(after["updated_at"], before["updated_at"])
        for field in before.keys() - {"rate_per_unit", "updated_at"}:
            self.assertEqual(after[field], before[field])
        self.assertEqual(self.client.get("/suppliers/1").json(), after)

    def test_status_updates_only_status(self):
        before = self.client.get("/suppliers/1").json()
        for status in ("suspended", "active"):
            response = self.client.patch("/suppliers/1/status", json={"status": status})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), before | {"status": status})
            self.assertEqual(self.client.get("/suppliers/1").json(), response.json())

    def test_invalid_patch_never_opens_database(self):
        for path, payload in [
            ("rate", {"rate_per_unit": 0}),
            ("rate", {"rate_per_unit": -1}),
            ("rate", {}),
            ("rate", {"rate_per_unit": 1, "status": "suspended"}),
            ("rate", {"rate_per_unit": 1, "updated_at": "2026-01-01T00:00:00Z"}),
            ("status", {"status": "deleted"}),
            ("status", {}),
            ("status", {"status": "active", "rate_per_unit": 1}),
            ("status", {"status": "active", "updated_at": "2026-01-01T00:00:00Z"}),
        ]:
            with self.subTest(path=path, payload=payload):
                with patch.object(suppliers, "get_suppliers_table") as open_table:
                    response = self.client.patch(f"/suppliers/1/{path}", json=payload)
                    self.assertEqual(response.status_code, 422)
                    open_table.assert_not_called()

    def test_missing_ids(self):
        for method, url, kwargs in [
            ("get", "/suppliers/999999", {}),
            ("patch", "/suppliers/999999/rate", {"json": {"rate_per_unit": 1}}),
            ("patch", "/suppliers/999999/status", {"json": {"status": "active"}}),
            ("delete", "/suppliers/999999", {}),
        ]:
            with self.subTest(method=method, url=url):
                response = self.client.request(method, url, **kwargs)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"detail": "Proveedor no encontrado."})

    def test_incident_endpoints_remain_functional(self):
        with patch.object(main, "_latest_metrics", None):
            self.assertEqual(
                self.client.get("/api/incidents/results/export").status_code, 404
            )
            content = (
                "incident_id,date,location_id,category,description,status,"
                "customer_id,satisfaction_score,reporter_id\n"
                "INC-TEST,2026-10-28,COL-01,SUPPLY,Missing delivery,OPEN,,,EMP-1\n"
            )
            response = self.client.post(
                "/api/incidents/analyze",
                files={"file": ("incidents.csv", content, "text/csv")},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["valid_records"], 1)
            response = self.client.get("/api/incidents/results/export")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.text.startswith("metric,value,percentage"))


if __name__ == "__main__":
    unittest.main()
