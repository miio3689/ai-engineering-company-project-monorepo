"""TinyDB services for authentication users and their profiles."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import secrets
from threading import RLock
from typing import Iterator

from passlib.hash import bcrypt
from tinydb import TinyDB
from tinydb.table import Table

from .models import (
    ProfileCreate,
    ProfileResponse,
    ProfileUpdate,
    User,
    UserCreate,
    UserResponse,
    UserUpdate,
)

AUTH_DATABASE_PATH = Path(__file__).resolve().with_name("auth.json")
PASSWORD_RESET_EXPIRE_MINUTES = int(
    os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30")
)
if not 15 <= PASSWORD_RESET_EXPIRE_MINUTES <= 60:
    raise ValueError("PASSWORD_RESET_EXPIRE_MINUTES must be between 15 and 60")
_database_lock = RLock()


class InvalidResetTokenError(ValueError):
    """Raised when a password reset token is invalid, expired, or used."""


class IncorrectCurrentPasswordError(ValueError):
    """Raised when a user's current password cannot be verified."""


@contextmanager
def _get_auth_tables() -> Iterator[tuple[Table, Table]]:
    with TinyDB(AUTH_DATABASE_PATH) as database:
        yield database.table("users"), database.table("profiles")


@contextmanager
def _get_password_reset_tables() -> Iterator[tuple[Table, Table]]:
    with TinyDB(AUTH_DATABASE_PATH) as database:
        yield database.table("users"), database.table("password_reset_tokens")


@contextmanager
def _get_user_deletion_tables() -> Iterator[tuple[Table, Table, Table]]:
    with TinyDB(AUTH_DATABASE_PATH) as database:
        yield (
            database.table("users"),
            database.table("profiles"),
            database.table("password_reset_tokens"),
        )


def _find_user_by_email(table: Table, email: str) -> dict | None:
    normalized_email = email.casefold()
    return next(
        (
            record
            for record in table.all()
            if record["email"].casefold() == normalized_email
        ),
        None,
    )


def _find_profile_by_user_id(table: Table, user_id: int) -> dict | None:
    return table.get(lambda record: record["user_id"] == user_id)


def _user_response(record: dict, user_id: int | None = None) -> UserResponse:
    response_record = {
        key: value for key, value in record.items() if key != "hashed_password"
    }
    return UserResponse(
        id=record.doc_id if user_id is None else user_id,
        **response_record,
    )


def _profile_response(record: dict, profile_id: int | None = None) -> ProfileResponse:
    return ProfileResponse(
        id=record.doc_id if profile_id is None else profile_id,
        **record,
    )


def _obtener_usuario_con_hash_por_email(email: str) -> User | None:
    """Internal lookup for a future login flow; never returned by public services."""
    with _database_lock, _get_auth_tables() as (users, _):
        record = _find_user_by_email(users, email)
        if record is None:
            return None
        return User(id=record.doc_id, **record)


def autenticar_usuario(email: str, password: str) -> UserResponse | None:
    user = _obtener_usuario_con_hash_por_email(email)
    if user is None or not user.is_active:
        return None
    if not bcrypt.verify(password, user.hashed_password):
        return None
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        role=user.role,
        created_at=user.created_at,
    )


def create_reset_token(email: str) -> str | None:
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe()
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)

    with _database_lock, _get_password_reset_tables() as (users, reset_tokens):
        user = _find_user_by_email(users, email)
        if user is None:
            return None

        previous_valid_tokens = [
            record.doc_id
            for record in reset_tokens.all()
            if record["user_id"] == user.doc_id
            and record["used_at"] is None
            and datetime.fromisoformat(record["expires_at"]) > now
        ]
        if previous_valid_tokens:
            reset_tokens.update(
                {"used_at": now.isoformat()}, doc_ids=previous_valid_tokens
            )

        reset_tokens.insert(
            {
                "token_hash": token_hash,
                "user_id": user.doc_id,
                "user_created_at": user["created_at"],
                "expires_at": expires_at.isoformat(),
                "used_at": None,
            }
        )
    return token


def reset_password(token: str, new_password: str) -> None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    with _database_lock, _get_password_reset_tables() as (users, reset_tokens):
        reset_record = next(
            (
                record
                for record in reset_tokens.all()
                if secrets.compare_digest(record["token_hash"], token_hash)
            ),
            None,
        )
        if (
            reset_record is None
            or reset_record["used_at"] is not None
            or datetime.fromisoformat(reset_record["expires_at"]) <= now
        ):
            raise InvalidResetTokenError("El token de restablecimiento no es válido.")

        user_id = reset_record["user_id"]
        user = users.get(doc_id=user_id)
        if (
            user is None
            or not reset_record.get("user_created_at")
            or not user.get("created_at")
            or reset_record["user_created_at"] != user["created_at"]
        ):
            raise InvalidResetTokenError("El token de restablecimiento no es válido.")

        users.update({"hashed_password": bcrypt.hash(new_password)}, doc_ids=[user_id])
        reset_tokens.update({"used_at": now.isoformat()}, doc_ids=[reset_record.doc_id])


def change_password(user_id: int, current_password: str, new_password: str) -> None:
    with _database_lock, _get_auth_tables() as (users, _):
        user = users.get(doc_id=user_id)
        if user is None or not bcrypt.verify(current_password, user["hashed_password"]):
            raise IncorrectCurrentPasswordError("La contraseña actual es incorrecta.")

        users.update(
            {"hashed_password": bcrypt.hash(new_password)}, doc_ids=[user_id]
        )


def crear_usuario(data: UserCreate) -> UserResponse:
    with _database_lock, _get_auth_tables() as (users, _):
        if _find_user_by_email(users, data.email) is not None:
            raise ValueError(f"Ya existe un usuario con el email {data.email}.")

        record = {
            "email": data.email,
            "hashed_password": bcrypt.hash(data.password),
            "is_active": True,
            "role": data.role.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        user_id = users.insert(record)
        return _user_response(record, user_id)


def obtener_usuario_por_id(user_id: int) -> UserResponse | None:
    with _database_lock, _get_auth_tables() as (users, _):
        record = users.get(doc_id=user_id)
        return None if record is None else _user_response(record)


def listar_usuarios() -> list[UserResponse]:
    with _database_lock, _get_auth_tables() as (users, _):
        return [_user_response(record) for record in users.all()]


def obtener_usuario_por_email(email: str) -> UserResponse | None:
    with _database_lock, _get_auth_tables() as (users, _):
        record = _find_user_by_email(users, email)
        return None if record is None else _user_response(record)


def actualizar_usuario(user_id: int, data: UserUpdate) -> UserResponse:
    changes = data.model_dump(mode="json", exclude_unset=True)
    if not changes:
        raise ValueError("Debe especificar al menos un campo para actualizar.")
    if any(value is None for value in changes.values()):
        raise ValueError("email y role no pueden ser null.")

    with _database_lock, _get_auth_tables() as (users, _):
        record = users.get(doc_id=user_id)
        if record is None:
            raise ValueError(f"No existe un usuario con id {user_id}.")
        if "email" in changes:
            existing = _find_user_by_email(users, changes["email"])
            if existing is not None and existing.doc_id != user_id:
                raise ValueError(
                    f"Ya existe un usuario con el email {changes['email']}."
                )
        users.update(changes, doc_ids=[user_id])
        return _user_response(dict(record) | changes, user_id)


def eliminar_usuario(user_id: int) -> bool:
    with _database_lock, _get_user_deletion_tables() as (
        users,
        profiles,
        reset_tokens,
    ):
        record = users.get(doc_id=user_id)
        profiles.remove(lambda profile: profile["user_id"] == user_id)
        reset_tokens.remove(lambda token: token["user_id"] == user_id)
        if record is None:
            return False
        users.remove(doc_ids=[user_id])
        return True


def crear_perfil(user_id: int, data: ProfileCreate) -> ProfileResponse:
    with _database_lock, _get_auth_tables() as (users, profiles):
        if users.get(doc_id=user_id) is None:
            raise ValueError(f"No existe un usuario con id {user_id}.")
        if _find_profile_by_user_id(profiles, user_id) is not None:
            raise ValueError(f"El usuario {user_id} ya tiene un perfil.")

        record = data.model_dump(mode="json") | {"user_id": user_id}
        profile_id = profiles.insert(record)
        return ProfileResponse(id=profile_id, **record)


def obtener_perfil_por_user_id(user_id: int) -> ProfileResponse | None:
    with _database_lock, _get_auth_tables() as (_, profiles):
        record = _find_profile_by_user_id(profiles, user_id)
        return None if record is None else _profile_response(record)


def obtener_o_crear_perfil(user_id: int) -> ProfileResponse:
    with _database_lock:
        profile = obtener_perfil_por_user_id(user_id)
        if profile is not None:
            return profile
        user = obtener_usuario_por_id(user_id)
        if user is None:
            raise ValueError(f"No existe un usuario con id {user_id}.")
        return crear_perfil(
            user_id, ProfileCreate(name=user.email.partition("@")[0])
        )


def actualizar_perfil(user_id: int, data: ProfileUpdate) -> ProfileResponse:
    changes = data.model_dump(mode="json", exclude_unset=True)
    if not changes:
        raise ValueError("Debe especificar al menos un campo para actualizar.")
    if "name" in changes and changes["name"] is None:
        raise ValueError("name no puede ser null.")

    with _database_lock:
        profile = obtener_o_crear_perfil(user_id)
        with _get_auth_tables() as (_, profiles):
            profiles.update(changes, doc_ids=[profile.id])
        return ProfileResponse.model_validate(profile.model_dump() | changes)