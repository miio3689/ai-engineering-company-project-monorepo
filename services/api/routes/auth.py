"""Login and current-user endpoints."""

import logging
import os
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from .. import email_service, services_auth
from ..auth_security import create_access_token, get_current_user
from ..models import (
    AuthMeResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
FORGOT_PASSWORD_MESSAGE = (
    "Si existe una cuenta con ese correo, recibirás instrucciones para "
    "restablecer tu contraseña."
)


def _create_and_send_reset_email(to_email: str) -> None:
    try:
        token = services_auth.create_reset_token(to_email)
    except Exception as exc:
        logger.error(
            "No se pudo generar el restablecimiento (tipo: %s).",
            type(exc).__name__,
        )
        return

    if token is None:
        return

    try:
        frontend_base_url = os.getenv(
            "FRONTEND_BASE_URL", "http://localhost:3000"
        ).rstrip("/")
        reset_url = (
            f"{frontend_base_url}/reset-password?{urlencode({'token': token})}"
        )
    except (TypeError, ValueError) as exc:
        logger.error(
            "No se pudo preparar el restablecimiento (tipo: %s).",
            type(exc).__name__,
        )
        return

    try:
        email_service.send_password_reset_email(to_email, reset_url)
    except email_service.EmailConfigurationError as exc:
        logger.error(
            "El envío de restablecimiento no está configurado (tipo: %s).",
            type(exc).__name__,
        )
    except email_service.EmailDeliveryError as exc:
        logger.error(
            "Falló la entrega del restablecimiento (tipo: %s).",
            type(exc).__name__,
        )
    except Exception as exc:
        logger.error(
            "Falló el proceso de envío del restablecimiento (tipo: %s).",
            type(exc).__name__,
        )


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict[str, str]:
    user = services_auth.autenticar_usuario(form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
    }


@router.post("/forgot-password")
def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    background_tasks.add_task(_create_and_send_reset_email, data.email)
    return {"message": FORGOT_PASSWORD_MESSAGE}


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest) -> dict[str, str]:
    try:
        services_auth.reset_password(data.token, data.new_password)
    except services_auth.InvalidResetTokenError as exc:
        raise HTTPException(
            status_code=400,
            detail="El token de restablecimiento no es válido.",
        ) from exc
    return {"message": "Contraseña restablecida correctamente."}


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: UserResponse = Depends(get_current_user),
) -> dict[str, str]:
    try:
        services_auth.change_password(
            current_user.id, data.current_password, data.new_password
        )
    except services_auth.IncorrectCurrentPasswordError as exc:
        raise HTTPException(
            status_code=400,
            detail="La contraseña actual es incorrecta.",
        ) from exc
    return {"message": "Contraseña actualizada correctamente."}


@router.get("/me", response_model=AuthMeResponse)
def read_current_user(
    current_user: UserResponse = Depends(get_current_user),
) -> AuthMeResponse:
    return AuthMeResponse(
        email=current_user.email,
        role=current_user.role,
        profile=services_auth.obtener_perfil_por_user_id(current_user.id),
    )