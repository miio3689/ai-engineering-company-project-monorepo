"""Password endpoints tested with temporary auth storage and mocked email."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import dotenv
from fastapi.testclient import TestClient
from tinydb import TinyDB

from services.api import email_service, services_auth
from services.api.models import UserCreate
from services.api.routes.auth import FORGOT_PASSWORD_MESSAGE

with patch.object(dotenv, "load_dotenv"):
    from services.api.app import main


class PasswordRouteTests(unittest.TestCase):
    email = "password-routes@example.com"
    original_password = "original-password"

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database_path = Path(self.temporary.name) / "auth.json"
        self.database_patch = patch.object(
            services_auth, "AUTH_DATABASE_PATH", self.database_path
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        user = services_auth.crear_usuario(
            UserCreate(email=self.email, password=self.original_password)
        )
        self.user_id = user.id
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def _login(self, password: str):
        return self.client.post(
            "/auth/login",
            data={"username": self.email, "password": password},
        )

    def test_forgot_password_is_generic_and_schedules_email_for_existing_user(self):
        with (
            patch.dict(
                os.environ, {"FRONTEND_BASE_URL": "https://frontend.example"}
            ),
            patch.object(email_service, "send_password_reset_email") as send_email,
        ):
            existing = self.client.post(
                "/auth/forgot-password", json={"email": self.email}
            )
            self.assertEqual(existing.status_code, 200)
            send_email.assert_called_once()
            sent_email, reset_url = send_email.call_args.args
            self.assertEqual(sent_email, self.email)
            self.assertTrue(
                reset_url.startswith("https://frontend.example/reset-password?")
            )
            token = parse_qs(urlparse(reset_url).query)["token"][0]
            self.assertTrue(token)

            missing = self.client.post(
                "/auth/forgot-password", json={"email": "missing@example.com"}
            )

        self.assertEqual(existing.json(), missing.json())
        self.assertEqual(
            existing.json(),
            {
                "message": (
                    "Si existe una cuenta con ese correo, recibirás instrucciones "
                    "para restablecer tu contraseña."
                )
            },
        )
        self.assertEqual(send_email.call_count, 1)

    def test_forgot_password_email_failure_does_not_change_response(self):
        with patch.object(
            email_service,
            "send_password_reset_email",
            side_effect=RuntimeError("delivery failed"),
        ):
            response = self.client.post(
                "/auth/forgot-password", json={"email": self.email}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "message": (
                    "Si existe una cuenta con ese correo, recibirás instrucciones "
                    "para restablecer tu contraseña."
                )
            },
        )

    def test_resend_failure_keeps_generic_response_and_logs_no_email_or_details(self):
        with (
            patch.dict(os.environ, {"RESEND_API_KEY": "test-key"}),
            patch.object(
                email_service.resend.Emails,
                "send",
                side_effect=email_service.resend.exceptions.ResendError(
                    "500",
                    "application_error",
                    "private provider response",
                    "",
                ),
            ),
            self.assertLogs("services.api.routes.auth", level="ERROR") as captured,
        ):
            response = self.client.post(
                "/auth/forgot-password", json={"email": self.email}
            )

        log_output = "\n".join(captured.output)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": FORGOT_PASSWORD_MESSAGE})
        self.assertNotIn(self.email, response.text + log_output)
        self.assertNotIn("private provider response", response.text + log_output)
        self.assertNotIn("reset-password?", response.text + log_output)
        self.assertIn("EmailDeliveryError", log_output)

    def test_missing_email_configuration_raises_controlled_error(self):
        with patch.dict(os.environ, {"RESEND_API_KEY": ""}):
            with self.assertRaises(email_service.EmailConfigurationError) as raised:
                email_service.send_password_reset_email(
                    self.email, "https://frontend.example/reset-password"
                )

        self.assertEqual(
            str(raised.exception),
            "El servicio de correo no está configurado.",
        )
        self.assertNotIn("RESEND_API_KEY", str(raised.exception))

    def test_reset_email_has_mobile_html_and_plain_text_content(self):
        reset_url = "https://frontend.example/reset-password?token=sample-token"
        with (
            patch.dict(os.environ, {"RESEND_API_KEY": "test-key"}),
            patch.object(email_service.resend.Emails, "send") as resend_send,
        ):
            email_service.send_password_reset_email(self.email, reset_url)

        message = resend_send.call_args.args[0]
        self.assertEqual(message["to"], [self.email])
        self.assertNotIn("test-key", str(message))
        self.assertIn(reset_url, message["html"])
        self.assertIn(reset_url, message["text"])
        self.assertIn("caduca en 30 minutos", message["html"])
        self.assertIn("caduca en 30 minutos", message["text"])
        self.assertIn("max-width:560px", message["html"])

    def test_reset_password_changes_login_and_rejects_reuse(self):
        token = services_auth.create_reset_token(self.email)
        response = self.client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "new-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._login(self.original_password).status_code, 401)
        self.assertEqual(self._login("new-password").status_code, 200)

        second_use = self.client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "another-password"},
        )
        self.assertEqual(second_use.status_code, 400)

    def test_reset_password_rejects_expired_and_invented_tokens(self):
        expired_token = services_auth.create_reset_token(self.email)
        with TinyDB(self.database_path) as database:
            tokens = database.table("password_reset_tokens")
            record = tokens.all()[0]
            tokens.update(
                {
                    "expires_at": (
                        datetime.now(timezone.utc) - timedelta(minutes=1)
                    ).isoformat()
                },
                doc_ids=[record.doc_id],
            )

        for token in (expired_token, "invented-token"):
            with self.subTest(token=token):
                response = self.client.post(
                    "/auth/reset-password",
                    json={"token": token, "new_password": "new-password"},
                )
                self.assertEqual(response.status_code, 400)

    def test_deleted_users_reset_token_cannot_target_reused_user_id(self):
        token = services_auth.create_reset_token(self.email)
        self.assertTrue(services_auth.eliminar_usuario(self.user_id))

        replacement_email = "replacement-password-routes@example.com"
        replacement_password = "replacement-password"
        replacement = services_auth.crear_usuario(
            UserCreate(email=replacement_email, password=replacement_password)
        )
        self.assertEqual(replacement.id, self.user_id)

        response = self.client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "attacker-password"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsNotNone(
            services_auth.autenticar_usuario(replacement_email, replacement_password)
        )
        self.assertIsNone(
            services_auth.autenticar_usuario(replacement_email, "attacker-password")
        )

    def test_change_password_requires_session_and_verifies_current_password(self):
        payload = {
            "current_password": self.original_password,
            "new_password": "new-password",
        }
        unauthorized = self.client.post("/auth/change-password", json=payload)
        self.assertEqual(unauthorized.status_code, 401)

        login = self._login(self.original_password)
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        incorrect = self.client.post(
            "/auth/change-password",
            json=payload | {"current_password": "incorrect-password"},
            headers=headers,
        )
        self.assertEqual(incorrect.status_code, 400)

        changed = self.client.post(
            "/auth/change-password", json=payload, headers=headers
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self._login("new-password").status_code, 200)


if __name__ == "__main__":
    unittest.main()