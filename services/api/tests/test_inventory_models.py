"""Inventory ORM constraints and Pydantic schema tests using SQLite."""

import unittest
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from services.api.inventory.models import Ingredient, IngredientEntry, IngredientExit
from services.api.inventory.schemas import EntryCreate, ExitCreate, IngredientCreate


def create_sqlite_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    return engine


class InventoryModelTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_sqlite_engine()

    def tearDown(self):
        self.engine.dispose()

    def create_ingredient(self):
        ingredient = Ingredient(
            name="Falda de ternera",
            sku="BRS-BEEF-001",
            unit="kg",
            category="meat",
            country="CO",
        )
        with Session(self.engine) as session:
            session.add(ingredient)
            session.commit()
            session.refresh(ingredient)
        return ingredient

    def assert_database_rejects(self, record):
        with Session(self.engine) as session:
            session.add(record)
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_create_all_registers_three_tables_without_stock_column(self):
        inspector = inspect(self.engine)
        self.assertEqual(
            set(inspector.get_table_names()),
            {"ingredient", "ingredient_entry", "ingredient_exit"},
        )
        for table_name in inspector.get_table_names():
            with self.subTest(table=table_name):
                self.assertNotIn(
                    "current_stock",
                    {column["name"] for column in inspector.get_columns(table_name)},
                )

    def test_duplicate_sku_is_rejected_by_database(self):
        self.create_ingredient()
        self.assert_database_rejects(
            Ingredient(
                name="Otra falda",
                sku="BRS-BEEF-001",
                unit="kg",
                category="meat",
                country="CO",
            )
        )

    def test_entry_and_exit_foreign_keys_reject_missing_ingredient(self):
        self.assert_database_rejects(
            IngredientEntry(
                ingredient_id=999,
                quantity=1,
                supplier_name="Proveedor",
                location_id=1,
                user_uuid="1",
            )
        )
        self.assert_database_rejects(
            IngredientExit(
                ingredient_id=999,
                quantity=1,
                reason="waste",
                location_id=1,
                user_uuid="1",
            )
        )

    def test_database_checks_quantity_location_reason_and_ingredient_enums(self):
        ingredient = self.create_ingredient()
        invalid_entries = [
            {"quantity": 0},
            {"quantity": -1},
            {"location_id": 0},
            {"location_id": 15},
        ]
        for changes in invalid_entries:
            with self.subTest(entry=changes):
                self.assert_database_rejects(
                    IngredientEntry(
                        ingredient_id=ingredient.id,
                        quantity=changes.get("quantity", 1),
                        supplier_name="Proveedor",
                        location_id=changes.get("location_id", 1),
                        user_uuid="1",
                    )
                )

        invalid_exits = [
            {"quantity": 0},
            {"quantity": -1},
            {"location_id": 0},
            {"location_id": 15},
            {"reason": "invalid"},
        ]
        for changes in invalid_exits:
            with self.subTest(exit=changes):
                self.assert_database_rejects(
                    IngredientExit(
                        ingredient_id=ingredient.id,
                        quantity=changes.get("quantity", 1),
                        reason=changes.get("reason", "waste"),
                        location_id=changes.get("location_id", 1),
                        user_uuid="1",
                    )
                )

        for field, invalid_value in (
            ("unit", "gallon"),
            ("category", "invalid"),
            ("country", "CA"),
        ):
            with self.subTest(field=field):
                values = {
                    "name": "Ingrediente inválido",
                    "sku": f"INVALID-{field}",
                    "unit": "kg",
                    "category": "meat",
                    "country": "CO",
                }
                values[field] = invalid_value
                self.assert_database_rejects(Ingredient(**values))

    def test_schemas_reject_invalid_ingredient_enums_and_client_stock(self):
        valid = {
            "name": "Falda de ternera",
            "sku": "BRS-BEEF-001",
            "unit": "kg",
            "category": "meat",
            "country": "CO",
        }
        with self.assertRaises(ValidationError):
            IngredientCreate(**valid, current_stock=10)

        for field, invalid_value in (
            ("unit", "gallon"),
            ("category", "invalid"),
            ("country", "CA"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    IngredientCreate(**(valid | {field: invalid_value}))

    def test_movement_schemas_reject_nonpositive_or_nonfinite_quantities(self):
        invalid_quantities = (0, -1, float("nan"), float("inf"), float("-inf"))
        for quantity in invalid_quantities:
            with self.subTest(entry_quantity=quantity):
                with self.assertRaises(ValidationError):
                    EntryCreate(
                        ingredient_id=1,
                        quantity=quantity,
                        supplier_name="Proveedor",
                        location_id=1,
                    )
            with self.subTest(exit_quantity=quantity):
                with self.assertRaises(ValidationError):
                    ExitCreate(
                        ingredient_id=1,
                        quantity=quantity,
                        reason="waste",
                        location_id=1,
                    )

    def test_movement_schemas_reject_server_owned_fields(self):
        with self.assertRaises(ValidationError):
            EntryCreate(
                ingredient_id=1,
                quantity=1,
                supplier_name="Proveedor",
                location_id=1,
                user_uuid="1",
            )
        with self.assertRaises(ValidationError):
            ExitCreate(
                ingredient_id=1,
                quantity=1,
                reason="waste",
                location_id=1,
                created_at=datetime.now(timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()