"""JWT configuration and authenticated-user dependency."""

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from . import services_auth
from .models import UserResponse

# These defaults are for local development only; production must set both env vars.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or (
    "dev-only-secret-change-before-deploying"
)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES") or "30")
if ACCESS_TOKEN_EXPIRE_MINUTES < 1:
    raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(user_uuid: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"user_uuid": user_uuid, "exp": expires_at}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserResponse:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar el token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_uuid = int(payload["user_uuid"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise unauthorized from exc

    user = services_auth.obtener_usuario_por_id(user_uuid)
    if user is None or not user.is_active:
        raise unauthorized
    return user