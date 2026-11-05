"""Inventory seed tests using temporary TinyDB and in-memory SQLite."""

from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool
from tinydb import TinyDB

from services.api import services_auth
from services.api.app import main as api_main
from services.api.inventory.database import get_db
from services.api.inventory.models import Ingredient, IngredientEntry, IngredientExit
from services.api.seed_inventory import main, seed_inventory


class InventorySeedTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.auth_path = Path(self.temporary.name) / "auth.json"
        self.auth_path_patch = patch.object(
            services_auth,
            "AUTH_DATABASE_PATH",
            self.auth_path,
        )
        self.auth_path_patch.start()
        self.addCleanup(self.auth_path_patch.stop)
        self.database_url_patch = patch.dict(os.environ, {"DATABASE_URL": "sqlite://"})
        self.database_url_patch.start()
        self.addCleanup(self.database_url_patch.stop)

        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SQLModel.metadata.create_all(self.engine)
        self.session_factory = lambda: Session(self.engine)
        self.previous_get_db_override = api_main.app.dependency_overrides.get(get_db)
        api_main.app.dependency_overrides[get_db] = self.session_factory
        self.addCleanup(self._restore_get_db_override)

        self.client = TestClient(api_main.app)
        self.addCleanup(self.client.close)
        registration = self.client.post(
            "/users",
            json={
                "email": "inventory-seed-tests@example.com",
                "password": "inventory-seed-test-password",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.text)
        self.user_id = registration.json()["id"]
        login = self.client.post(
            "/auth/login",
            data={
                "username": "inventory-seed-tests@example.com",
                "password": "inventory-seed-test-password",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def tearDown(self):
        self.engine.dispose()

    def _restore_get_db_override(self):
        if self.previous_get_db_override is None:
            api_main.app.dependency_overrides.pop(get_db, None)
        else:
            api_main.app.dependency_overrides[get_db] = self.previous_get_db_override

    def _table_counts(self):
        with Session(self.engine) as session:
            return (
                len(session.exec(select(Ingredient)).all()),
                len(session.exec(select(IngredientEntry)).all()),
                len(session.exec(select(IngredientExit)).all()),
            )

    def test_seed_inserts_exact_records_stock_and_tinydb_user_uuid(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main(session_factory=self.session_factory)

        self.assertIn("Ingredientes insertados: 6", output.getvalue())
        self.assertIn("Entradas insertadas: 7", output.getvalue())
        self.assertIn("Salidas insertadas: 3", output.getvalue())
        self.assertEqual(self._table_counts(), (6, 7, 3))

        with Session(self.engine) as session:
            entry_users = {
                entry.user_uuid for entry in session.exec(select(IngredientEntry)).all()
            }
            exit_users = {
                exit_record.user_uuid
                for exit_record in session.exec(select(IngredientExit)).all()
            }
        self.assertEqual(entry_users, {str(self.user_id)})
        self.assertEqual(exit_users, {str(self.user_id)})

        response = self.client.get("/inventory/products", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            {product["sku"]: product["current_stock"] for product in response.json()},
            {
                "BRS-BEEF-001": 67.5,
                "BRS-PORK-001": 35.0,
                "BRS-SAUCE-001": 16.0,
                "BRS-SAUCE-002": 15.0,
                "BRS-PROD-001": 60.0,
                "BRS-PKG-001": 200.0,
            },
        )

    def test_second_run_does_not_duplicate_anything(self):
        seed_inventory(self.session_factory)
        output = io.StringIO()
        with redirect_stdout(output):
            main(session_factory=self.session_factory)

        self.assertIn("ya estaba sembrada", output.getvalue())
        self.assertEqual(self._table_counts(), (6, 7, 3))

    def test_no_active_users_aborts_before_opening_session_or_inserting(self):
        with TinyDB(self.auth_path) as database:
            database.table("users").update({"is_active": False})

        session_factory_called = False

        def tracking_session_factory():
            nonlocal session_factory_called
            session_factory_called = True
            return Session(self.engine)

        with self.assertRaisesRegex(
            RuntimeError,
            "No hay usuarios activos en TinyDB",
        ):
            seed_inventory(tracking_session_factory)

        self.assertFalse(session_factory_called)
        self.assertEqual(self._table_counts(), (0, 0, 0))

    def test_missing_database_url_exits_clearly_without_opening_session(self):
        session_factory_called = False

        def tracking_session_factory():
            nonlocal session_factory_called
            session_factory_called = True
            return Session(self.engine)

        output = io.StringIO()
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            with redirect_stderr(output):
                with self.assertRaises(SystemExit) as error:
                    main(session_factory=tracking_session_factory)

        self.assertEqual(error.exception.code, 1)
        self.assertIn("DATABASE_URL no está configurada", output.getvalue())
        self.assertNotIn("postgres", output.getvalue().lower())
        self.assertNotIn("password", output.getvalue().lower())
        self.assertFalse(session_factory_called)
        self.assertEqual(self._table_counts(), (0, 0, 0))

    def test_database_failure_does_not_expose_driver_details(self):
        def failing_session_factory():
            raise OperationalError(
                "SELECT 1",
                {},
                Exception("sensitive driver detail and connection string"),
            )

        output = io.StringIO()
        with redirect_stderr(output):
            with self.assertRaises(SystemExit) as error:
                main(session_factory=failing_session_factory)

        self.assertEqual(error.exception.code, 1)
        self.assertIn("no se pudo acceder a la base de datos", output.getvalue())
        self.assertNotIn("sensitive", output.getvalue())
        self.assertNotIn("connection string", output.getvalue())
        self.assertEqual(self._table_counts(), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()