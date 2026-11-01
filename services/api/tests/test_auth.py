"""AUTH-01 regressions using temporary storage and real signed login tokens."""

import io
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from jose import jwt
from tinydb import TinyDB

from services.api import promote_admin, services_auth
from services.api.app import main
from services.api.auth_security import JWT_ALGORITHM, JWT_SECRET_KEY
from services.api.models import ProfileCreate, UserCreate, UserRole


class AuthEndpointsTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database_path = Path(temporary.name) / "auth.json"
        database_patch = patch.object(
            services_auth, "AUTH_DATABASE_PATH", self.database_path
        )
        database_patch.start()
        self.addCleanup(database_patch.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.password = "auth-tests-password"

    def register(self, email="alice@example.com", **fields):
        response = self.client.post(
            "/users", json={"email": email, "password": self.password} | fields
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def headers(self, email):
        response = self.client.post(
            "/auth/login", data={"username": email, "password": self.password}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["token_type"], "bearer")
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def admin(self):
        return services_auth.crear_usuario(
            UserCreate(
                email="admin@example.com",
                password=self.password,
                role=UserRole.admin,
            )
        )

    def test_public_registration_rejects_every_role_and_assigns_user(self):
        schema = self.client.get("/openapi.json").json()
        registration_schema = schema["components"]["schemas"]["UserRegistration"]
        self.assertNotIn("role", registration_schema["properties"])
        self.assertFalse(registration_schema["additionalProperties"])
        for role in ("admin", "manager", "user", None, "unknown"):
            with self.subTest(role=role):
                response = self.client.post(
                    "/users",
                    json={
                        "email": "alice@example.com",
                        "password": self.password,
                        "role": role,
                    },
                )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"][0]["loc"], ["body", "role"])
                self.assertEqual(services_auth.listar_usuarios(), [])
        user = self.register()
        self.assertEqual(user["role"], "user")
        self.assertNotIn("hashed_password", user)
        response = self.client.get("/auth/me", headers=self.headers(user["email"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "user")
        self.assertEqual(response.json()["profile"]["name"], "alice")
        duplicate = self.client.post(
            "/users", json={"email": "ALICE@example.com", "password": self.password}
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(len(services_auth.listar_usuarios()), 1)

    def test_non_admin_cannot_submit_role_even_unchanged_or_invalid(self):
        for actor_role in (UserRole.user, UserRole.manager):
            actor = services_auth.crear_usuario(
                UserCreate(
                    email=f"{actor_role.value}@example.com",
                    password=self.password,
                    role=actor_role,
                )
            )
            headers = self.headers(actor.email)
            for role in ("admin", "manager", "user", None, "unknown", 7):
                with self.subTest(actor_role=actor_role, role=role):
                    with patch.object(services_auth, "actualizar_usuario") as update:
                        response = self.client.put(
                            f"/users/{actor.id}",
                            headers=headers,
                            json={"role": role, "email": "changed@example.com"},
                        )
                        self.assertEqual(response.status_code, 403)
                        update.assert_not_called()
                    self.assertEqual(
                        services_auth.obtener_usuario_por_id(actor.id).role, actor_role
                    )
                    self.assertEqual(
                        services_auth.obtener_usuario_por_id(actor.id).email, actor.email
                    )
            response = self.client.put(
                f"/users/{actor.id}",
                headers=headers,
                json={"email": f"updated-{actor_role.value}@example.com"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["role"], actor_role.value)
            self.assertEqual(
                response.json()["email"], f"updated-{actor_role.value}@example.com"
            )

    def test_non_admin_cannot_update_other_existing_or_missing_user(self):
        actor = self.register()
        other = self.register("other@example.com")
        headers = self.headers(actor["email"])
        for target_id in (other["id"], 999999):
            with self.subTest(target_id=target_id):
                response = self.client.put(
                    f"/users/{target_id}",
                    headers=headers,
                    json={"email": "changed@example.com"},
                )
                self.assertEqual(response.status_code, 403)
        self.assertEqual(
            services_auth.obtener_usuario_por_id(other["id"]).email, other["email"]
        )

    def test_admin_can_update_email_and_role_of_any_user(self):
        admin = self.admin()
        other = self.register()
        headers = self.headers(admin.email)
        for target_id, email, role in (
            (other["id"], "updated@example.com", "manager"),
            (admin.id, "updated-admin@example.com", "admin"),
        ):
            with self.subTest(target_id=target_id):
                response = self.client.put(
                    f"/users/{target_id}",
                    headers=headers,
                    json={"email": email, "role": role},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["email"], email)
                self.assertEqual(response.json()["role"], role)
                self.assertEqual(
                    services_auth.obtener_usuario_por_id(target_id).email, email
                )
        self.assertEqual(
            self.client.put(
                "/users/999999", headers=headers, json={"role": "admin"}
            ).status_code,
            404,
        )

    def test_invalid_user_updates_keep_validation_and_conflict_errors(self):
        schema = self.client.get("/openapi.json").json()
        update_schema = schema["paths"]["/users/{user_id}"]["put"]["requestBody"][
            "content"
        ]["application/json"]["schema"]
        self.assertEqual(update_schema["$ref"], "#/components/schemas/UserUpdate")
        actor = self.register()
        self.register("other@example.com")
        headers = self.headers(actor["email"])
        for payload, status_code in (
            ({}, 422),
            ({"email": "invalid"}, 422),
            ({"email": None}, 409),
            ({"email": "OTHER@example.com"}, 409),
            ({"email": "valid@example.com", "password": "replacement"}, 422),
        ):
            with self.subTest(payload=payload):
                response = self.client.put(
                    f"/users/{actor['id']}", headers=headers, json=payload
                )
                self.assertEqual(response.status_code, status_code)
                self.assertEqual(
                    services_auth.obtener_usuario_por_id(actor["id"]).email,
                    actor["email"],
                )
        self.assertEqual(
            self.client.put(f"/users/{actor['id']}", headers=headers).status_code,
            422,
        )
        for body in ('{"email":', "not json"):
            response = self.client.put(
                f"/users/{actor['id']}",
                headers=headers | {"Content-Type": "application/json"},
                content=body,
            )
            self.assertEqual(response.status_code, 422)
        admin = self.admin()
        response = self.client.put(
            f"/users/{actor['id']}",
            headers=self.headers(admin.email),
            json={"role": "unknown"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["body", "role"])

    def test_delete_other_user_is_forbidden_before_existence_check(self):
        actor = self.register()
        other = self.register("other@example.com")
        headers = self.headers(actor["email"])
        for target_id in (other["id"], 999999):
            with self.subTest(target_id=target_id):
                with patch.object(services_auth, "eliminar_usuario") as delete:
                    response = self.client.delete(
                        f"/users/{target_id}", headers=headers
                    )
                    self.assertEqual(response.status_code, 403)
                    delete.assert_not_called()
        self.assertIsNotNone(services_auth.obtener_usuario_por_id(other["id"]))
        self.assertIsNotNone(services_auth.obtener_perfil_por_user_id(other["id"]))

    def test_self_delete_removes_user_profile_and_invalidates_token(self):
        actor = self.register()
        headers = self.headers(actor["email"])
        response = self.client.delete(f"/users/{actor['id']}", headers=headers)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertIsNone(services_auth.obtener_usuario_por_id(actor["id"]))
        self.assertIsNone(services_auth.obtener_perfil_por_user_id(actor["id"]))
        self.assertEqual(self.client.get("/auth/me", headers=headers).status_code, 401)

    def test_jwt_is_invalidated_when_tinydb_reuses_a_deleted_user_id(self):
        user_a = self.register("user-a@example.com")
        token_a_headers = self.headers(user_a["email"])
        deleted = self.client.delete(
            f"/users/{user_a['id']}", headers=token_a_headers
        )
        self.assertEqual(deleted.status_code, 204)

        user_b = self.register("user-b@example.com")
        self.assertEqual(user_b["id"], user_a["id"])
        self.assertEqual(
            self.client.get("/auth/me", headers=token_a_headers).status_code, 401
        )
        token_b_headers = self.headers(user_b["email"])
        response = self.client.get("/auth/me", headers=token_b_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], user_b["email"])

        token_without_account_claim = jwt.encode(
            {
                "user_uuid": user_b["id"],
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )
        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token_without_account_claim}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_can_delete_other_user_and_get_404_for_missing_user(self):
        admin = self.admin()
        other = self.register()
        headers = self.headers(admin.email)
        response = self.client.delete(f"/users/{other['id']}", headers=headers)
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(services_auth.obtener_usuario_por_id(other["id"]))
        self.assertIsNone(services_auth.obtener_perfil_por_user_id(other["id"]))
        self.assertEqual(
            self.client.delete(f"/users/{other['id']}", headers=headers).status_code,
            404,
        )

    def test_registration_always_creates_profile_with_default_or_given_name(self):
        for index, fields in enumerate(
            (
                {},
                {"name": None},
                {"name": ""},
                {"name": " \t "},
                {"phone": "123", "address": "Main street"},
                {"name": "Alice", "phone": "123", "address": "Main street"},
            )
        ):
            with self.subTest(fields=fields):
                email = f"person{index}@example.com"
                user = self.register(email, **fields)
                profile = services_auth.obtener_perfil_por_user_id(user["id"])
                self.assertIsNotNone(profile)
                self.assertEqual(profile.user_id, user["id"])
                self.assertEqual(
                    profile.name, "Alice" if fields.get("name") == "Alice" else f"person{index}"
                )
                self.assertEqual(profile.phone, fields.get("phone"))
                self.assertEqual(profile.address, fields.get("address"))

    def test_get_profile_repairs_legacy_account_idempotently(self):
        legacy = services_auth.crear_usuario(
            UserCreate(email="legacy@example.com", password=self.password)
        )
        self.assertIsNone(services_auth.obtener_perfil_por_user_id(legacy.id))
        headers = self.headers(legacy.email)
        first = self.client.get("/profiles/me", headers=headers)
        self.assertEqual(first.status_code, 200)
        expected = first.json()
        self.assertEqual(expected["name"], "legacy")
        self.assertEqual(expected["user_id"], legacy.id)
        self.assertIsNone(expected["phone"])
        self.assertIsNone(expected["address"])
        second = self.client.get("/profiles/me", headers=headers)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), expected)
        with TinyDB(self.database_path) as database:
            self.assertEqual(len(database.table("profiles")), 1)

    def test_put_profile_repairs_legacy_account_and_preserves_changes(self):
        legacy = services_auth.crear_usuario(
            UserCreate(email="legacy@example.com", password=self.password)
        )
        headers = self.headers(legacy.email)
        response = self.client.put(
            "/profiles/me", headers=headers, json={"phone": "123"}
        )
        self.assertEqual(response.status_code, 200)
        expected = response.json()
        self.assertEqual(expected["name"], "legacy")
        self.assertEqual(expected["phone"], "123")
        response = self.client.put(
            "/profiles/me", headers=headers, json={"name": "Saved name", "address": "Saved address"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], expected["id"])
        self.assertEqual(response.json()["phone"], "123")
        saved = response.json()
        self.assertEqual(self.client.get("/profiles/me", headers=headers).json(), saved)
        self.assertEqual(self.client.get("/auth/me", headers=headers).json()["profile"], saved)
        with TinyDB(self.database_path) as database:
            self.assertEqual(len(database.table("profiles")), 1)

    def test_profile_repair_is_idempotent_across_concurrent_threads(self):
        legacy = services_auth.crear_usuario(
            UserCreate(email="legacy@example.com", password=self.password)
        )
        with ThreadPoolExecutor(max_workers=4) as executor:
            profiles = list(
                executor.map(services_auth.obtener_o_crear_perfil, [legacy.id] * 8)
            )
        self.assertTrue(all(profile == profiles[0] for profile in profiles))
        with TinyDB(self.database_path) as database:
            self.assertEqual(len(database.table("profiles")), 1)

    def test_invalid_profile_updates_do_not_create_or_change_profiles(self):
        legacy = services_auth.crear_usuario(
            UserCreate(email="legacy@example.com", password=self.password)
        )
        headers = self.headers(legacy.email)
        for payload in ({}, {"name": None}, {"user_id": 999}, {"role": "admin"}):
            with self.subTest(payload=payload):
                response = self.client.put("/profiles/me", headers=headers, json=payload)
                self.assertEqual(response.status_code, 422)
                self.assertIsNone(services_auth.obtener_perfil_por_user_id(legacy.id))
        original = services_auth.crear_perfil(
            legacy.id, ProfileCreate(name="Existing name", phone="123")
        )
        self.assertEqual(
            self.client.get("/profiles/me", headers=headers).json(),
            original.model_dump(mode="json"),
        )
        response = self.client.put(
            "/profiles/me", headers=headers, json={"phone": None, "address": None}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Existing name")
        self.assertIsNone(response.json()["phone"])

    def test_protected_endpoints_reject_anonymous_requests(self):
        for method, url, payload in (
            ("get", "/users", None),
            ("get", "/users/1", None),
            ("put", "/users/1", {"email": "new@example.com"}),
            ("delete", "/users/1", None),
            ("get", "/profiles/me", None),
            ("put", "/profiles/me", {"name": "New name"}),
        ):
            with self.subTest(method=method, url=url):
                response = self.client.request(method, url, json=payload)
                self.assertEqual(response.status_code, 401)
        self.assertEqual(services_auth.listar_usuarios(), [])

    def test_terminal_promotion_is_idempotent_and_preserves_user_and_profile(self):
        user = self.register()
        before = services_auth.obtener_usuario_por_id(user["id"])
        profile = services_auth.obtener_perfil_por_user_id(user["id"])
        for _ in range(2):
            output = io.StringIO()
            with patch.object(sys, "argv", ["promote_admin", "ALICE@example.com"]):
                with redirect_stdout(output):
                    promote_admin.main()
            self.assertIn("promovido a admin", output.getvalue())
            after = services_auth.obtener_usuario_por_id(user["id"])
            self.assertEqual(after.role, UserRole.admin)
            self.assertEqual(
                after.model_dump(exclude={"role"}), before.model_dump(exclude={"role"})
            )
            self.assertEqual(
                services_auth.obtener_perfil_por_user_id(user["id"]), profile
            )
            self.assertIsNotNone(
                services_auth.autenticar_usuario(user["email"], self.password)
            )

    def test_terminal_promotion_rejects_missing_or_invalid_email(self):
        for email in ("missing@example.com", "invalid"):
            with self.subTest(email=email):
                error = io.StringIO()
                with patch.object(sys, "argv", ["promote_admin", email]):
                    with redirect_stderr(error):
                        with self.assertRaises(SystemExit) as raised:
                            promote_admin.main()
                self.assertEqual(raised.exception.code, 2)
                self.assertTrue(error.getvalue())
                self.assertEqual(services_auth.listar_usuarios(), [])


class JwtStartupTests(unittest.TestCase):
    def startup(self, secret):
        environment = os.environ.copy()
        environment.pop("JWT_SECRET_KEY", None)
        if secret is not None:
            environment["JWT_SECRET_KEY"] = secret
        return subprocess.run(
            [sys.executable, "-c", "import services.api.app.main"],
            cwd=Path(__file__).resolve().parents[3],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_startup_rejects_missing_empty_and_short_jwt_secret(self):
        for secret in (None, "", " " * 32, "x" * 31, " " + "x" * 31 + " "):
            with self.subTest(secret=secret):
                result = self.startup(secret)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "JWT_SECRET_KEY is required and must contain at least 32 characters",
                    result.stderr,
                )

    def test_startup_accepts_jwt_secret_at_minimum_length_and_above(self):
        for length in (32, 64):
            with self.subTest(length=length):
                result = self.startup("x" * length)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
