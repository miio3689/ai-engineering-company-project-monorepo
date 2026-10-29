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
    profile = services_auth.obtener_perfil_por_user_id(current_user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado.")
    return profile


@router.put("/me", response_model=ProfileResponse)
def update_my_profile(
    data: ProfileUpdate,
    current_user: UserResponse = Depends(get_current_user),
) -> ProfileResponse:
    try:
        return services_auth.actualizar_perfil(current_user.id, data)
    except ValueError as exc:
        status_code = 404 if "no tiene un perfil" in str(exc) else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc