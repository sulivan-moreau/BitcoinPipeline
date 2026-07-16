"""Sécurité de l'API : hachage des mots de passe (argon2) et gestion des JWT."""

from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import text

from src.api.core.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY
from src.utils.db import get_engine

_password_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """Hache un mot de passe en clair avec argon2."""
    return _password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Vérifie un mot de passe en clair contre son hash argon2, sans lever d'exception."""
    try:
        _password_hasher.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def create_access_token(data: dict) -> str:
    """Crée un JWT signé à partir de data, avec expiration JWT_EXPIRE_MINUTES après maintenant."""
    payload = data.copy()
    payload["exp"] = datetime.now(UTC) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> dict:
    """Décode le JWT Bearer et vérifie que l'utilisateur existe toujours en base.

    Lève une HTTPException 401 si le token est invalide ou expiré, ou si le
    username qu'il contient ne correspond plus à un compte existant dans la
    table users (ex. compte supprimé après émission du token).
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise unauthorized

    username = payload.get("sub")
    if username is None:
        raise unauthorized

    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, username FROM users WHERE username = :username"),
            {"username": username},
        ).first()

    if row is None:
        raise unauthorized

    return {"id": row.id, "username": row.username}
