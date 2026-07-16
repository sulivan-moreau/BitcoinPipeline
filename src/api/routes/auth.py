"""Route d'authentification : émission d'un token JWT contre des identifiants valides."""

from fastapi import APIRouter, HTTPException, status

from src.api.core.security import create_access_token
from src.api.schemas.auth import LoginRequest, TokenResponse
from src.api.services.auth_service import authenticate_user

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authentification et émission d'un token JWT",
    description=(
        "Vérifie les identifiants fournis (username/password) contre le compte "
        "administrateur enregistré en base. En cas de succès, retourne un token "
        "JWT Bearer à fournir dans l'en-tête `Authorization: Bearer <token>` "
        "pour accéder aux routes protégées de l'API."
    ),
    responses={401: {"description": "Identifiants incorrects"}},
)
def login(payload: LoginRequest) -> TokenResponse:
    user = authenticate_user(payload.username, payload.password)

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants incorrects")

    access_token = create_access_token({"sub": user["username"]})
    return TokenResponse(access_token=access_token)
