"""User registration and protected user management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from .. import services_auth
from ..auth_security import get_current_user
from ..models import (
    ProfileCreate,
    UserRegistration,
    UserResponse,
    UserRole,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(data: UserRegistration) -> UserResponse:
    try:
        user = services_auth.crear_usuario(data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if data.name is not None:
        try:
            services_auth.crear_perfil(
                user.id,
                ProfileCreate(name=data.name, phone=data.phone, address=data.address),
            )
        except Exception:
            services_auth.eliminar_usuario(user.id)
            raise
    return user


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


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    if current_user.role != UserRole.admin and current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="No autorizado para modificar este usuario.",
        )
    if not data.model_fields_set:
        raise HTTPException(status_code=422, detail="Debe indicar email o role.")
    if services_auth.obtener_usuario_por_id(user_id) is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    try:
        return services_auth.actualizar_usuario(user_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    _: UserResponse = Depends(get_current_user),
) -> None:
    if not services_auth.eliminar_usuario(user_id):
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")