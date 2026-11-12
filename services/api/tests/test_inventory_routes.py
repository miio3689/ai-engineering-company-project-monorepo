"""Inventory API tests using isolated SQLite and TinyDB stores."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from services.api import services_auth
from services.api.app import main
from services.api.inventory.database import get_db
from services.api.inventory.models import Ingredient, IngredientEntry, IngredientExit


PRODUCT = {
    "name": "Falda de ternera",
    "sku": "BRS-BEEF-001",
    "unit": "kg",
    "category": "meat",
    "country": "CO",
}


class InventoryRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database_url_patch = patch.dict(os.environ, {"DATABASE_URL": ""})
        self.database_url_patch.start()
        self.addCleanup(self.database_url_patch.stop)
        self.auth_path_patch = patch.object(
            services_auth,
            "AUTH_DATABASE_PATH",
            Path(self.temporary.name) / "auth.json",
        )
        self.auth_path_patch.start()
        self.addCleanup(self.auth_path_patch.stop)

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

        def override_get_db():
            with Session(self.engine) as session:
                yield session

        self.get_db_override = override_get_db
        self.previous_get_db_override = main.app.dependency_overrides.get(get_db)
        main.app.dependency_overrides[get_db] = override_get_db
        self.addCleanup(self._restore_get_db_override)

        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        registration = self.client.post(
            "/users",
            json={
                "email": "inventory-tests@example.com",
                "password": "inventory-test-password",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.text)
        self.user_id = registration.json()["id"]
        login = self.client.post(
            "/auth/login",
            data={
                "username": "inventory-tests@example.com",
                "password": "inventory-test-password",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def tearDown(self):
        self.engine.dispose()

    def _restore_get_db_override(self):
        if self.previous_get_db_override is None:
            main.app.dependency_overrides.pop(get_db, None)
        else:
            main.app.dependency_overrides[get_db] = self.previous_get_db_override

    def create_product(self, payload=None):
        response = self.client.post(
            "/inventory/products",
            json=PRODUCT if payload is None else payload,
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_all_six_inventory_endpoints_require_authentication(self):
        requests = (
            ("GET", "/inventory/products", None),
            ("POST", "/inventory/products", PRODUCT),
            ("GET", "/inventory/products/1", None),
            (
                "POST",
                "/inventory/orders/inbound",
                {
                    "ingredient_id": 1,
                    "quantity": 1,
                    "supplier_name": "Proveedor",
                    "location_id": 1,
                },
            ),
            (
                "POST",
                "/inventory/orders/outbound",
                {
                    "ingredient_id": 1,
                    "quantity": 1,
                    "reason": "waste",
                    "location_id": 1,
                },
            ),
            ("GET", "/inventory/orders", None),
        )
        for method, url, payload in requests:
            with self.subTest(method=method, url=url):
                response = self.client.request(method, url, json=payload)
                self.assertEqual(response.status_code, 401, response.text)

    def test_product_create_duplicate_sku_and_missing_detail(self):
        created = self.create_product()
        self.assertEqual(
            set(created),
            {
                "id",
                "name",
                "sku",
                "unit",
                "category",
                "country",
                "current_stock",
                "stock_by_location",
            },
        )
        self.assertEqual(created["current_stock"], 0)
        self.assertEqual(created["stock_by_location"], [])
        self.assertEqual(
            self.client.post(
                "/inventory/products",
                json=PRODUCT,
                headers=self.headers,
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.get("/inventory/products/999", headers=self.headers).status_code,
            404,
        )

    def test_stock_reflects_entries_minus_exits_in_product_list_and_detail(self):
        product = self.create_product()
        inbound = self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 12.5,
                "supplier_name": "Carnes del Valle S.A.",
                "location_id": 4,
            },
            headers=self.headers,
        )
        self.assertEqual(inbound.status_code, 201, inbound.text)
        outbound = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 2.25,
                "reason": "consumption",
                "location_id": 4,
            },
            headers=self.headers,
        )
        self.assertEqual(outbound.status_code, 201, outbound.text)

        listed = self.client.get("/inventory/products", headers=self.headers)
        detail = self.client.get(
            f"/inventory/products/{product['id']}",
            headers=self.headers,
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(listed.json()[0]["current_stock"], 10.25)
        self.assertEqual(detail.json()["current_stock"], 10.25)
        self.assertEqual(
            listed.json()[0]["stock_by_location"],
            [{"location_id": 4, "quantity": 10.25}],
        )
        self.assertEqual(
            detail.json()["stock_by_location"],
            [{"location_id": 4, "quantity": 10.25}],
        )

    def test_stock_by_location_sums_entries_and_exits_across_locations(self):
        product = self.create_product()
        for location_id, quantity in ((2, 7), (1, 10)):
            response = self.client.post(
                "/inventory/orders/inbound",
                json={
                    "ingredient_id": product["id"],
                    "quantity": quantity,
                    "supplier_name": "Proveedor",
                    "location_id": location_id,
                },
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 201, response.text)
        outbound = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 2,
                "reason": "consumption",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(outbound.status_code, 201, outbound.text)

        detail = self.client.get(
            f"/inventory/products/{product['id']}",
            headers=self.headers,
        ).json()
        self.assertEqual(
            detail["stock_by_location"],
            [
                {"location_id": 1, "quantity": 8.0},
                {"location_id": 2, "quantity": 7.0},
            ],
        )
        self.assertEqual(detail["current_stock"], 15.0)
        self.assertAlmostEqual(
            sum(row["quantity"] for row in detail["stock_by_location"]),
            detail["current_stock"],
            places=3,
        )

    def test_stock_by_location_is_empty_without_movements(self):
        product = self.create_product()
        response = self.client.get(
            f"/inventory/products/{product['id']}",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["current_stock"], 0)
        self.assertEqual(response.json()["stock_by_location"], [])

    def test_product_list_includes_stock_by_location_for_multiple_ingredients(self):
        first = self.create_product()
        second = self.create_product(
            PRODUCT | {"name": "Costilla de cerdo", "sku": "BRS-PORK-002"}
        )
        for ingredient_id, location_id, quantity in (
            (first["id"], 1, 3),
            (second["id"], 2, 5),
        ):
            response = self.client.post(
                "/inventory/orders/inbound",
                json={
                    "ingredient_id": ingredient_id,
                    "quantity": quantity,
                    "supplier_name": "Proveedor",
                    "location_id": location_id,
                },
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 201, response.text)

        response = self.client.get("/inventory/products", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        products = {item["id"]: item for item in response.json()}
        self.assertEqual(
            products[first["id"]]["stock_by_location"],
            [{"location_id": 1, "quantity": 3.0}],
        )
        self.assertEqual(
            products[second["id"]]["stock_by_location"],
            [{"location_id": 2, "quantity": 5.0}],
        )

    def test_insufficient_stock_returns_exact_message_without_insert(self):
        product = self.create_product()
        self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 5,
                "supplier_name": "Proveedor",
                "location_id": 1,
            },
            headers=self.headers,
        )
        response = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 5.001,
                "reason": "waste",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Insufficient stock for ingredient 'Falda de ternera' "
            "at location 1. Available: 5.000, requested: 5.001.",
        )
        with Session(self.engine) as session:
            self.assertEqual(len(session.exec(select(IngredientExit)).all()), 0)

    def test_submill_stock_rounding_cannot_create_negative_net_stock(self):
        product = self.create_product()
        self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 0.0002,
                "supplier_name": "Proveedor",
                "location_id": 1,
            },
            headers=self.headers,
        )
        response = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 0.0004,
                "reason": "waste",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Insufficient stock for ingredient 'Falda de ternera' "
            "at location 1. Available: 0.000, requested: 0.000.",
        )
        with Session(self.engine) as session:
            self.assertEqual(len(session.exec(select(IngredientExit)).all()), 0)

    def test_outbound_equal_to_available_stock_is_allowed(self):
        product = self.create_product()
        self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 8,
                "supplier_name": "Proveedor",
                "location_id": 1,
            },
            headers=self.headers,
        )
        response = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 8,
                "reason": "consumption",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        detail = self.client.get(
            f"/inventory/products/{product['id']}",
            headers=self.headers,
        )
        self.assertEqual(detail.json()["current_stock"], 0)
        self.assertEqual(
            detail.json()["stock_by_location"],
            [{"location_id": 1, "quantity": 0.0}],
        )

    def test_outbound_without_stock_at_requested_location_is_rejected(self):
        product = self.create_product()
        self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 10,
                "supplier_name": "Proveedor",
                "location_id": 1,
            },
            headers=self.headers,
        )
        response = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 5,
                "reason": "consumption",
                "location_id": 5,
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Insufficient stock for ingredient 'Falda de ternera' at location 5. "
            "Available: 0.000, requested: 5.000.",
        )

    def test_outbound_within_local_stock_is_allowed(self):
        product = self.create_product()
        for location_id, quantity in ((1, 10), (2, 8)):
            self.client.post(
                "/inventory/orders/inbound",
                json={
                    "ingredient_id": product["id"],
                    "quantity": quantity,
                    "supplier_name": "Proveedor",
                    "location_id": location_id,
                },
                headers=self.headers,
            )
        response = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 9,
                "reason": "consumption",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)

    def test_outbound_over_local_stock_is_rejected_even_below_global_total(self):
        product = self.create_product()
        for location_id, quantity in ((1, 5), (2, 10)):
            self.client.post(
                "/inventory/orders/inbound",
                json={
                    "ingredient_id": product["id"],
                    "quantity": quantity,
                    "supplier_name": "Proveedor",
                    "location_id": location_id,
                },
                headers=self.headers,
            )
        response = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 6,
                "reason": "waste",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Insufficient stock for ingredient 'Falda de ternera' at location 1. "
            "Available: 5.000, requested: 6.000.",
        )

    def test_outbound_exact_local_stock_leaves_zero_at_that_location(self):
        product = self.create_product()
        for location_id, quantity in ((1, 4), (2, 10)):
            self.client.post(
                "/inventory/orders/inbound",
                json={
                    "ingredient_id": product["id"],
                    "quantity": quantity,
                    "supplier_name": "Proveedor",
                    "location_id": location_id,
                },
                headers=self.headers,
            )
        response = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 4,
                "reason": "waste",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        detail = self.client.get(
            f"/inventory/products/{product['id']}",
            headers=self.headers,
        ).json()
        self.assertEqual(detail["current_stock"], 10)
        self.assertEqual(
            detail["stock_by_location"],
            [
                {"location_id": 1, "quantity": 0.0},
                {"location_id": 2, "quantity": 10.0},
            ],
        )

    def test_invalid_reason_quantity_and_locations_return_422(self):
        product = self.create_product()
        invalid_requests = (
            (
                "/inventory/orders/outbound",
                {
                    "ingredient_id": product["id"],
                    "quantity": 1,
                    "reason": "invalid",
                    "location_id": 1,
                },
            ),
            (
                "/inventory/orders/inbound",
                {
                    "ingredient_id": product["id"],
                    "quantity": 0,
                    "supplier_name": "Proveedor",
                    "location_id": 1,
                },
            ),
            (
                "/inventory/orders/outbound",
                {
                    "ingredient_id": product["id"],
                    "quantity": -1,
                    "reason": "waste",
                    "location_id": 1,
                },
            ),
        )
        for url, payload in invalid_requests:
            with self.subTest(url=url, payload=payload):
                response = self.client.post(url, json=payload, headers=self.headers)
                self.assertEqual(response.status_code, 422, response.text)

        for location_id in (0, 15):
            with self.subTest(location_id=location_id):
                response = self.client.post(
                    "/inventory/orders/inbound",
                    json={
                        "ingredient_id": product["id"],
                        "quantity": 1,
                        "supplier_name": "Proveedor",
                        "location_id": location_id,
                    },
                    headers=self.headers,
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_missing_ingredient_is_404_for_inbound_and_outbound(self):
        inbound = self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": 999,
                "quantity": 1,
                "supplier_name": "Proveedor",
                "location_id": 1,
            },
            headers=self.headers,
        )
        outbound = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": 999,
                "quantity": 1,
                "reason": "waste",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(inbound.status_code, 404, inbound.text)
        self.assertEqual(outbound.status_code, 404, outbound.text)

    def test_client_cannot_set_stock_or_movement_identity(self):
        self.assertEqual(
            self.client.post(
                "/inventory/products",
                json=PRODUCT | {"current_stock": 999},
                headers=self.headers,
            ).status_code,
            422,
        )
        product = self.create_product()
        response = self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 2,
                "supplier_name": "Proveedor",
                "location_id": 2,
                "user_uuid": "999",
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 422)
        created = self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 2,
                "supplier_name": "Proveedor",
                "location_id": 2,
            },
            headers=self.headers,
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["user_uuid"], str(self.user_id))
        with Session(self.engine) as session:
            stored_entry = session.exec(select(IngredientEntry)).one()
            self.assertEqual(stored_entry.user_uuid, str(self.user_id))

    def test_orders_include_both_movement_types_and_joined_ingredient_data(self):
        product = self.create_product()
        self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 4,
                "supplier_name": "Proveedor",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 1,
                "reason": "waste",
                "location_id": 1,
            },
            headers=self.headers,
        )
        response = self.client.get("/inventory/orders", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        orders = response.json()
        self.assertEqual({order["type"] for order in orders}, {"inbound", "outbound"})
        self.assertEqual(orders[0]["type"], "outbound")
        for order in orders:
            self.assertEqual(
                set(order),
                {
                    "id",
                    "type",
                    "ingredient_id",
                    "name",
                    "sku",
                    "quantity",
                    "location_id",
                    "created_at",
                    "user_uuid",
                    "reason" if order["type"] == "outbound" else "supplier_name",
                },
            )
            self.assertEqual(order["name"], PRODUCT["name"])
            self.assertEqual(order["sku"], PRODUCT["sku"])

    def test_queries_for_products_and_orders_do_not_grow_with_ingredients(self):
        self._seed_ingredients_and_movements(1)
        product_queries_one = self._count_select_queries("/inventory/products")
        order_queries_one = self._count_select_queries("/inventory/orders")

        self._seed_ingredients_and_movements(3, start_index=1)
        product_queries_many = self._count_select_queries("/inventory/products")
        order_queries_many = self._count_select_queries("/inventory/orders")

        self.assertEqual(product_queries_one, product_queries_many)
        self.assertEqual(order_queries_one, order_queries_many)
        self.assertEqual(product_queries_many, 3)
        self.assertEqual(order_queries_many, 2)

    def test_authenticated_inventory_without_database_url_returns_503(self):
        self._restore_get_db_override()
        response = self.client.get("/inventory/products", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Servicio de inventario no disponible."},
        )

    def _seed_ingredients_and_movements(self, count, start_index=0):
        with Session(self.engine) as session:
            for index in range(start_index, start_index + count):
                ingredient = Ingredient(
                    name=f"Ingrediente {index}",
                    sku=f"BRS-TEST-{index:03d}",
                    unit="kg",
                    category="meat",
                    country="CO",
                )
                session.add(ingredient)
                session.flush()
                session.add(
                    IngredientEntry(
                        ingredient_id=ingredient.id,
                        quantity=10,
                        supplier_name="Proveedor",
                        location_id=1,
                        user_uuid=str(self.user_id),
                    )
                )
                session.add(
                    IngredientExit(
                        ingredient_id=ingredient.id,
                        quantity=1,
                        reason="waste",
                        location_id=1,
                        user_uuid=str(self.user_id),
                    )
                )
            session.commit()

    def _count_select_queries(self, path):
        statements = []

        def count_query(_connection, _cursor, statement, _parameters, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", count_query)
        try:
            response = self.client.get(path, headers=self.headers)
        finally:
            event.remove(self.engine, "before_cursor_execute", count_query)
        self.assertEqual(response.status_code, 200, response.text)
        return len(statements)


if __name__ == "__main__":
    unittest.main()