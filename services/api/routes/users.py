"""User registration and protected user management endpoints."""

import logging
from json import JSONDecodeError

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .. import services_auth
from ..auth_security import get_current_user
from ..models import (
    ProfileCreate,
    RegistrationResponse,
    UserCreate,
    UserRegistration,
    UserResponse,
    UserRole,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)


@router.post("", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_user(data: UserRegistration) -> RegistrationResponse:
    profile = ProfileCreate(
        name=(data.name or "").strip() or data.email.partition("@")[0],
        phone=data.phone,
        address=data.address,
    )
    try:
        user = services_auth.crear_usuario(
            UserCreate(email=data.email, password=data.password, role=UserRole.user)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409, detail="Ya existe una cuenta con ese correo."
        ) from exc

    try:
        services_auth.crear_perfil(user.id, profile)
    except Exception as exc:
        try:
            services_auth.eliminar_usuario(user.id)
        except Exception as rollback_error:
            logger.error(
                "Falló la creación del perfil y su reversión (tipos: %s, %s).",
                type(exc).__name__,
                type(rollback_error).__name__,
            )
        else:
            logger.error(
                "Falló la creación del perfil (tipo: %s).",
                type(exc).__name__,
            )
        raise HTTPException(
            status_code=500, detail="Error interno del servidor."
        ) from None
    return RegistrationResponse(id=user.id)


@router.get("", response_model=list[UserResponse])
def list_users(
    _: UserResponse = Depends(get_current_user),
) -> list[UserResponse]:
    return services_auth.listar_usuarios()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    _: UserResponse = Depends(get_current_user),
) -> UserResponse:
    user = services_auth.obtener_usuario_por_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return user


async def authorize_user_update(
    user_id: int,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
) -> None:
    if current_user.role == UserRole.admin:
        return
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="No autorizado para modificar este usuario.",
        )
    try:
        data = await request.json()
    except JSONDecodeError as exc:
        raise HTTPException(
            status_code=422, detail="El cuerpo debe contener JSON válido."
        ) from exc
    # Check field presence before validation, including null or invalid role values.
    if isinstance(data, dict) and "role" in data:
        raise HTTPException(
            status_code=403,
            detail="No autorizado para modificar este usuario.",
        )


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    _: None = Depends(authorize_user_update),
) -> UserResponse:
    if not data.model_fields_set:
        raise HTTPException(status_code=422, detail="Debe indicar email o role.")
    if services_auth.obtener_usuario_por_id(user_id) is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    try:
        return services_auth.actualizar_usuario(user_id, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="No se pudo actualizar el usuario por un conflicto.",
        ) from exc


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: UserResponse = Depends(get_current_user),
) -> None:
    if current_user.role != UserRole.admin and current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="No autorizado para eliminar este usuario.",
        )
    if not services_auth.eliminar_usuario(user_id):
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")