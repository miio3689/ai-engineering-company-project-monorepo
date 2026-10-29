"""Login and current-user endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from .. import services_auth
from ..auth_security import create_access_token, get_current_user
from ..models import AuthMeResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


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
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
    }


@router.get("/me", response_model=AuthMeResponse)
def read_current_user(
    current_user: UserResponse = Depends(get_current_user),
) -> AuthMeResponse:
    return AuthMeResponse(
        email=current_user.email,
        role=current_user.role,
        profile=services_auth.obtener_perfil_por_user_id(current_user.id),
    )