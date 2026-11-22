"""Inventory API tests using isolated SQLite and TinyDB stores."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from services.api import services_auth
from services.api.app import main
from services.api.routes.inventory import (
    INVENTORY_CACHE_TTL_SECONDS,
    inventory_cache,
)
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
        inventory_cache.clear()
        self.addCleanup(inventory_cache.clear)
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

    def test_all_seven_inventory_endpoints_require_authentication(self):
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
            (
                "PUT",
                "/inventory/products/1/stock",
                {"location_id": 1, "quantity": 5},
            ),
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
                    *(
                        ("unit_cost", "price_variance")
                        if order["type"] == "inbound"
                        else ()
                    ),
                },
            )
            self.assertEqual(order["name"], PRODUCT["name"])
            self.assertEqual(order["sku"], PRODUCT["sku"])

    def test_second_products_and_orders_reads_skip_database_queries(self):
        self._seed_ingredients_and_movements(1)
        products_first = self._count_select_queries("/inventory/products")
        orders_first = self._count_select_queries("/inventory/orders")
        products_second = self._count_select_queries("/inventory/products")
        orders_second = self._count_select_queries("/inventory/orders")

        self.assertEqual(products_first, 3)
        self.assertEqual(orders_first, 2)
        self.assertEqual(products_second, 0)
        self.assertEqual(orders_second, 0)

    def test_inventory_read_errors_return_503_and_are_not_cached(self):
        original_exec = Session.exec

        for path in ("/inventory/products", "/inventory/orders"):
            with self.subTest(path=path):
                inventory_cache.clear()
                execution_count = 0

                def fail_first_exec(session, *args, **kwargs):
                    nonlocal execution_count
                    execution_count += 1
                    if execution_count == 1:
                        raise SQLAlchemyError("temporary database failure")
                    return original_exec(session, *args, **kwargs)

                with patch.object(Session, "exec", new=fail_first_exec):
                    failed = self.client.get(path, headers=self.headers)
                    self.assertEqual(failed.status_code, 503, failed.text)
                    self.assertEqual(execution_count, 1)

                    recovered = self.client.get(path, headers=self.headers)
                    self.assertEqual(recovered.status_code, 200, recovered.text)
                    self.assertGreater(execution_count, 1)

    def test_product_create_invalidates_warm_products_cache(self):
        initial = self.client.get("/inventory/products", headers=self.headers)
        self.assertEqual(initial.json(), [])

        created = self.create_product()

        listed = self.client.get("/inventory/products", headers=self.headers)
        self.assertEqual([item["id"] for item in listed.json()], [created["id"]])

    def test_inbound_invalidates_product_and_order_caches(self):
        product = self.create_product()
        self.client.get("/inventory/products", headers=self.headers)
        self.assertEqual(
            self.client.get("/inventory/orders", headers=self.headers).json(),
            [],
        )

        inbound = self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 7,
                "supplier_name": "Proveedor",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(inbound.status_code, 201, inbound.text)
        listed_product = self.client.get(
            "/inventory/products",
            headers=self.headers,
        ).json()[0]
        listed_orders = self.client.get(
            "/inventory/orders",
            headers=self.headers,
        ).json()
        self.assertEqual(listed_product["current_stock"], 7)
        self.assertEqual([order["id"] for order in listed_orders], [inbound.json()["id"]])

    def test_outbound_invalidates_product_and_order_caches(self):
        product = self.create_product()
        self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 7,
                "supplier_name": "Proveedor",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.client.get("/inventory/products", headers=self.headers)
        self.client.get("/inventory/orders", headers=self.headers)

        outbound = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 2,
                "reason": "waste",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(outbound.status_code, 201, outbound.text)
        listed_product = self.client.get(
            "/inventory/products",
            headers=self.headers,
        ).json()[0]
        listed_orders = self.client.get(
            "/inventory/orders",
            headers=self.headers,
        ).json()
        self.assertEqual(listed_product["current_stock"], 5)
        self.assertEqual(
            {(order["type"], order["id"]) for order in listed_orders},
            {("inbound", 1), ("outbound", outbound.json()["id"])},
        )

    def test_expired_products_cache_reloads_external_database_changes(self):
        clock = [0.0]
        with patch.object(inventory_cache, "_clock", lambda: clock[0]):
            first = self.client.get("/inventory/products", headers=self.headers)
            self.assertEqual(first.json(), [])
            with Session(self.engine) as session:
                session.add(Ingredient(**PRODUCT))
                session.commit()

            before_expiration = self.client.get(
                "/inventory/products",
                headers=self.headers,
            )
            self.assertEqual(before_expiration.json(), [])
            clock[0] += INVENTORY_CACHE_TTL_SECONDS + 0.1
            after_expiration = self.client.get(
                "/inventory/products",
                headers=self.headers,
            )
            self.assertEqual(len(after_expiration.json()), 1)

    def test_unauthenticated_read_is_rejected_when_cache_is_warm(self):
        self.assertEqual(
            self.client.get(
                "/inventory/products",
                headers=self.headers,
            ).status_code,
            200,
        )
        response = self.client.get("/inventory/products")
        self.assertEqual(response.status_code, 401)

    def test_outbound_validation_uses_database_not_stale_products_cache(self):
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
        cached_products = self.client.get(
            "/inventory/products",
            headers=self.headers,
        ).json()
        self.assertEqual(cached_products[0]["current_stock"], 5)

        with Session(self.engine) as session:
            session.add(
                IngredientExit(
                    ingredient_id=product["id"],
                    quantity=3,
                    reason="waste",
                    location_id=1,
                    user_uuid=str(self.user_id),
                )
            )
            session.commit()
        self.assertEqual(
            self.client.get(
                "/inventory/products",
                headers=self.headers,
            ).json()[0]["current_stock"],
            5,
        )

        response = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 3,
                "reason": "waste",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_queries_for_products_and_orders_do_not_grow_with_ingredients(self):
        self._seed_ingredients_and_movements(1)
        inventory_cache.clear()
        product_queries_one = self._count_select_queries("/inventory/products")
        order_queries_one = self._count_select_queries("/inventory/orders")

        self._seed_ingredients_and_movements(3, start_index=1)
        inventory_cache.clear()
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

    def test_inbound_unit_cost_is_optional_persisted_and_returned_in_order_list(self):
        product = self.create_product()
        with_cost = self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 4,
                "supplier_name": "Proveedor con costo",
                "unit_cost": 12.5,
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(with_cost.status_code, 201, with_cost.text)
        self.assertEqual(with_cost.json()["unit_cost"], 12.5)
        self.assertIsNone(with_cost.json()["price_variance"])
        with Session(self.engine) as session:
            stored = session.exec(select(IngredientEntry)).one()
            self.assertEqual(stored.unit_cost, 12.5)

        without_cost = self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 2,
                "supplier_name": "Proveedor sin costo",
                "location_id": 2,
            },
            headers=self.headers,
        )
        self.assertEqual(without_cost.status_code, 201, without_cost.text)
        self.assertIsNone(without_cost.json()["unit_cost"])
        self.assertIsNone(without_cost.json()["price_variance"])

        invalid_costs = (0, -1, float("nan"))
        for cost in invalid_costs:
            with self.subTest(unit_cost=cost):
                payload = {
                    "ingredient_id": product["id"],
                    "quantity": 1,
                    "supplier_name": "Proveedor inválido",
                    "unit_cost": "NaN" if isinstance(cost, float) and cost != cost else cost,
                    "location_id": 1,
                }
                response = self.client.post(
                    "/inventory/orders/inbound",
                    json=payload,
                    headers=self.headers,
                )
                self.assertEqual(response.status_code, 422, response.text)

        orders = self.client.get("/inventory/orders", headers=self.headers)
        self.assertEqual(orders.status_code, 200, orders.text)
        inbound_by_supplier = {
            order["supplier_name"]: order
            for order in orders.json()
            if order["type"] == "inbound"
        }
        self.assertEqual(inbound_by_supplier["Proveedor con costo"]["unit_cost"], 12.5)
        self.assertIsNone(inbound_by_supplier["Proveedor sin costo"]["unit_cost"])

    def test_price_variance_uses_five_recent_costs_for_same_ingredient_and_supplier(self):
        def add_history(product_id, supplier, cost, day):
            from datetime import datetime, timedelta, timezone

            with Session(self.engine) as session:
                session.add(
                    IngredientEntry(
                        ingredient_id=product_id,
                        quantity=1,
                        supplier_name=supplier,
                        unit_cost=cost,
                        location_id=1,
                        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
                        + timedelta(days=day),
                        user_uuid=str(self.user_id),
                    )
                )
                session.commit()

        def inbound(product_id, supplier, cost):
            return self.client.post(
                "/inventory/orders/inbound",
                json={
                    "ingredient_id": product_id,
                    "quantity": 1,
                    "supplier_name": supplier,
                    "unit_cost": cost,
                    "location_id": 1,
                },
                headers=self.headers,
            )

        product = self.create_product()
        for day in range(3):
            add_history(product["id"], "Proveedor A", 100, day)
        increase = inbound(product["id"], "Proveedor A", 130)
        self.assertEqual(increase.status_code, 201, increase.text)
        self.assertEqual(
            increase.json()["price_variance"],
            {
                "baseline_unit_cost": 100.0,
                "variance_pct": 30.0,
                "threshold_pct": 10.0,
            },
        )

        in_range_product = self.create_product(
            PRODUCT | {"sku": "BRS-TEST-IN-RANGE"},
        )
        for day in range(3):
            add_history(in_range_product["id"], "Proveedor B", 100, day)
        in_range = inbound(in_range_product["id"], "Proveedor B", 105)
        self.assertEqual(in_range.status_code, 201, in_range.text)
        self.assertIsNone(in_range.json()["price_variance"])

        no_history_product = self.create_product(
            PRODUCT | {"sku": "BRS-TEST-NO-HISTORY"},
        )
        first = inbound(no_history_product["id"], "Proveedor C", 100)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertIsNone(first.json()["price_variance"])
        other_supplier = inbound(no_history_product["id"], "Proveedor D", 130)
        self.assertEqual(other_supplier.status_code, 201, other_supplier.text)
        self.assertIsNone(other_supplier.json()["price_variance"])

        recent_product = self.create_product(
            PRODUCT | {"sku": "BRS-TEST-RECENT"},
        )
        add_history(recent_product["id"], "Proveedor E", 1000, 0)
        for day in range(1, 6):
            add_history(recent_product["id"], "Proveedor E", 100, day)
        recent = inbound(recent_product["id"], "Proveedor E", 100)
        self.assertEqual(recent.status_code, 201, recent.text)
        self.assertIsNone(recent.json()["price_variance"])

        decrease_product = self.create_product(
            PRODUCT | {"sku": "BRS-TEST-DECREASE"},
        )
        for day in range(3):
            add_history(decrease_product["id"], "Proveedor F", 100, day)
        decrease = inbound(decrease_product["id"], "Proveedor F", 80)
        self.assertEqual(decrease.status_code, 201, decrease.text)
        self.assertEqual(decrease.json()["price_variance"]["variance_pct"], -20.0)

        no_cost_product = self.create_product(
            PRODUCT | {"sku": "BRS-TEST-NULL-COST"},
        )
        add_history(no_cost_product["id"], "Proveedor G", None, 0)
        ignored_null = inbound(no_cost_product["id"], "Proveedor G", 130)
        self.assertEqual(ignored_null.status_code, 201, ignored_null.text)
        self.assertIsNone(ignored_null.json()["price_variance"])

    def test_direct_stock_edit_is_rejected_without_changing_stock(self):
        product = self.create_product()
        inbound = self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 10,
                "supplier_name": "Proveedor",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(inbound.status_code, 201, inbound.text)
        before = self.client.get(
            "/inventory/products",
            headers=self.headers,
        ).json()[0]["current_stock"]

        rejected = self.client.put(
            f"/inventory/products/{product['id']}/stock",
            json={"location_id": 1, "quantity": 50},
            headers=self.headers,
        )
        self.assertEqual(rejected.status_code, 403, rejected.text)
        self.assertEqual(
            rejected.json(),
            {
                "detail": (
                    "El stock no se modifica directamente: "
                    "registra una orden de entrada o de salida."
                )
            },
        )
        after = self.client.get(
            "/inventory/products",
            headers=self.headers,
        ).json()[0]["current_stock"]
        self.assertEqual(after, before)

        unauthenticated = self.client.put(
            f"/inventory/products/{product['id']}/stock",
            json={"location_id": 1, "quantity": 50},
        )
        missing = self.client.put(
            "/inventory/products/999999/stock",
            json={"location_id": 1, "quantity": 50},
            headers=self.headers,
        )
        self.assertEqual(unauthenticated.status_code, 401, unauthenticated.text)
        self.assertEqual(missing.status_code, 404, missing.text)

        invalid_payloads = (
            {"location_id": 0, "quantity": 1},
            {"location_id": 15, "quantity": 1},
            {"location_id": 1, "quantity": -1},
            {"location_id": 1, "quantity": 1, "extra": True},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                invalid = self.client.put(
                    f"/inventory/products/{product['id']}/stock",
                    json=payload,
                    headers=self.headers,
                )
                self.assertEqual(invalid.status_code, 422, invalid.text)

    def test_direct_stock_edit_route_documents_403_in_openapi(self):
        openapi = self.client.get("/openapi.json").json()
        operation = openapi["paths"]["/inventory/products/{ingredient_id}/stock"]["put"]
        self.assertIn("403", operation["responses"])
        self.assertEqual(
            operation["responses"]["403"]["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/StockEditRejection",
        )

    def test_waste_reference_cost_is_mean_of_five_most_recent_product_entries(self):
        from datetime import datetime, timedelta, timezone

        product = self.create_product()
        with Session(self.engine) as session:
            for day, cost in enumerate((10, 20, 30, 40, 50, 60)):
                session.add(
                    IngredientEntry(
                        ingredient_id=product["id"],
                        quantity=10,
                        supplier_name="Proveedor",
                        unit_cost=cost,
                        location_id=1,
                        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
                        + timedelta(days=day),
                        user_uuid=str(self.user_id),
                    )
                )
            session.commit()

        response = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 1,
                "reason": "waste",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["reference_unit_cost"], 40.0)

        orders = self.client.get("/inventory/orders", headers=self.headers)
        self.assertEqual(orders.status_code, 200, orders.text)

    def test_consumption_reference_cost_is_null(self):
        product = self.create_product()
        inbound = self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 4,
                "supplier_name": "Proveedor",
                "unit_cost": 12,
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(inbound.status_code, 201, inbound.text)
        response = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 1,
                "reason": "consumption",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertIsNone(response.json()["reference_unit_cost"])

    def test_waste_without_cost_history_returns_null(self):
        product = self.create_product()
        inbound = self.client.post(
            "/inventory/orders/inbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 4,
                "supplier_name": "Proveedor sin costo",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(inbound.status_code, 201, inbound.text)
        response = self.client.post(
            "/inventory/orders/outbound",
            json={
                "ingredient_id": product["id"],
                "quantity": 1,
                "reason": "waste",
                "location_id": 1,
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertIsNone(response.json()["reference_unit_cost"])

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