"""Tests for optional inventory database setup and request sessions."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlmodel import Session, create_engine, select

from services.api.app import main
from services.api.inventory import database
from services.api.inventory.database import get_db


class InventoryDatabaseTests(unittest.TestCase):
    def test_app_starts_without_database_url_and_dependency_returns_503(self):
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            with TestClient(main.app) as main_client:
                self.assertEqual(main_client.get("/openapi.json").status_code, 200)

            probe_app = FastAPI()

            @probe_app.get("/probe")
            def probe(session: Session = Depends(get_db)):
                return {"available": True}

            with TestClient(probe_app) as client:
                response = client.get("/probe")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Servicio de inventario no disponible."},
        )

    def test_dependency_override_yields_a_usable_sqlite_session(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
        )
        probe_app = FastAPI()

        def override_get_db():
            with Session(engine) as session:
                yield session

        @probe_app.get("/probe")
        def probe(session: Session = Depends(get_db)):
            return {"value": session.exec(select(1)).one()}

        probe_app.dependency_overrides[get_db] = override_get_db
        try:
            with TestClient(probe_app) as client:
                response = client.get("/probe")
        finally:
            engine.dispose()

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"value": 1})

    def test_init_inventory_db_adds_unit_cost_column_idempotently(self):
        with TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "inventory.sqlite"
            engine = create_engine(f"sqlite:///{database_path}")
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE ingredient_entry (id INTEGER PRIMARY KEY)"
                )
            engine.dispose()

            with (
                patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{database_path}"}),
                patch.object(database, "_engine", None),
            ):
                database.init_inventory_db()
                database.init_inventory_db()
                migrated_engine = database.get_engine()
                columns = {
                    column["name"]
                    for column in inspect(migrated_engine).get_columns("ingredient_entry")
                }
                migrated_engine.dispose()

            self.assertIn("unit_cost", columns)


if __name__ == "__main__":
    unittest.main()