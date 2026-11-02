"""Tests for password reset and change services using isolated TinyDB storage."""

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from passlib.hash import bcrypt
from tinydb import TinyDB

from services.api import services_auth
from services.api.models import UserCreate


class PasswordServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database_path = Path(self.temporary.name) / "auth.json"
        self.database_patch = patch.object(
            services_auth, "AUTH_DATABASE_PATH", self.database_path
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        self.password = "original-password"
        user = services_auth.crear_usuario(
            UserCreate(email="reset-tests@example.com", password=self.password)
        )
        self.user_id = user.id

    def test_reset_changes_password_and_token_can_only_be_used_once(self):
        token = services_auth.create_reset_token("RESET-TESTS@example.com")
        self.assertIsNotNone(token)

        services_auth.reset_password(token, "new-password")
        user = services_auth._obtener_usuario_con_hash_por_email(
            "reset-tests@example.com"
        )
        self.assertTrue(bcrypt.verify("new-password", user.hashed_password))
        with self.assertRaises(services_auth.InvalidResetTokenError):
            services_auth.reset_password(token, "another-password")

    def test_expired_token_is_rejected(self):
        token = services_auth.create_reset_token("reset-tests@example.com")
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

        with self.assertRaises(services_auth.InvalidResetTokenError):
            services_auth.reset_password(token, "new-password")

    def test_missing_and_manipulated_tokens_are_rejected(self):
        valid_token = services_auth.create_reset_token("reset-tests@example.com")
        changed_character = "A" if valid_token[-1] != "A" else "B"
        manipulated_token = valid_token[:-1] + changed_character
        token_without_timestamp = services_auth.create_reset_token(
            "reset-tests@example.com"
        )
        with TinyDB(self.database_path) as database:
            tokens = database.table("password_reset_tokens")
            record = next(
                item
                for item in tokens.all()
                if item["token_hash"]
                == hashlib.sha256(token_without_timestamp.encode("utf-8")).hexdigest()
            )
            tokens.update(
                lambda item: item.pop("user_created_at", None),
                doc_ids=[record.doc_id],
            )

        token_with_mismatched_timestamp = services_auth.create_reset_token(
            "reset-tests@example.com"
        )
        with TinyDB(self.database_path) as database:
            tokens = database.table("password_reset_tokens")
            record = next(
                item
                for item in tokens.all()
                if item["token_hash"]
                == hashlib.sha256(
                    token_with_mismatched_timestamp.encode("utf-8")
                ).hexdigest()
            )
            tokens.update(
                {"user_created_at": "2000-01-01T00:00:00+00:00"},
                doc_ids=[record.doc_id],
            )

        for token in (
            "unknown-token",
            manipulated_token,
            token_without_timestamp,
            token_with_mismatched_timestamp,
        ):
            with self.subTest(token=token):
                with self.assertRaises(services_auth.InvalidResetTokenError):
                    services_auth.reset_password(token, "new-password")

    def test_only_token_hash_is_stored(self):
        token = services_auth.create_reset_token("reset-tests@example.com")
        with TinyDB(self.database_path) as database:
            record = database.table("password_reset_tokens").all()[0]
            contents = self.database_path.read_text(encoding="utf-8")

        self.assertNotIn(token, contents)
        self.assertEqual(
            record["token_hash"], hashlib.sha256(token.encode("utf-8")).hexdigest()
        )
        self.assertEqual(
            set(record),
            {"token_hash", "user_id", "user_created_at", "expires_at", "used_at"},
        )
        self.assertIsNone(record["used_at"])

    def test_new_token_invalidates_previous_token(self):
        first_token = services_auth.create_reset_token("reset-tests@example.com")
        second_token = services_auth.create_reset_token("reset-tests@example.com")

        with self.assertRaises(services_auth.InvalidResetTokenError):
            services_auth.reset_password(first_token, "new-password")
        services_auth.reset_password(second_token, "new-password")

    def test_change_password_checks_current_password(self):
        with self.assertRaises(services_auth.IncorrectCurrentPasswordError):
            services_auth.change_password(self.user_id, "incorrect", "new-password")
        user = services_auth._obtener_usuario_con_hash_por_email(
            "reset-tests@example.com"
        )
        self.assertTrue(bcrypt.verify(self.password, user.hashed_password))

        services_auth.change_password(self.user_id, self.password, "new-password")
        user = services_auth._obtener_usuario_con_hash_por_email(
            "reset-tests@example.com"
        )
        self.assertTrue(bcrypt.verify("new-password", user.hashed_password))

    def test_unknown_email_returns_none(self):
        self.assertIsNone(services_auth.create_reset_token("missing@example.com"))


if __name__ == "__main__":
    unittest.main()