"""Authenticated current-user profile endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from .. import services_auth
from ..auth_security import get_current_user
from ..models import ProfileResponse, ProfileUpdate, UserResponse

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    current_user: UserResponse = Depends(get_current_user),
) -> ProfileResponse:
    return services_auth.obtener_o_crear_perfil(current_user.id)


@router.put("/me", response_model=ProfileResponse)
def update_my_profile(
    data: ProfileUpdate,
    current_user: UserResponse = Depends(get_current_user),
) -> ProfileResponse:
    try:
        return services_auth.actualizar_perfil(current_user.id, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Los datos del perfil no son válidos."
        ) from exc