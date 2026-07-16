"""Service d'authentification : vérification des identifiants et compte admin par défaut."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.api.core.config import ADMIN_PASSWORD, ADMIN_USERNAME
from src.api.core.security import hash_password, verify_password
from src.utils.db import get_engine
from src.utils.logger import get_logger

logger = get_logger("auth_service")


def ensure_users_table() -> None:
    """Crée la table users si elle n'existe pas, conformément au MPD (docs/merise_mcd.md).

    Une erreur SQL est logguée mais ne provoque pas de sys.exit : c'est à
    l'appelant (ex. le lifespan de l'API) de décider comment réagir à cet
    échec.
    """
    ddl = text(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )

    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(ddl)
    except SQLAlchemyError as exc:
        logger.error(f"[AUTH] Échec de la création de la table users : {exc}")
        return

    logger.info("[AUTH] Table users prête")


def authenticate_user(username: str, password: str) -> dict | None:
    """Vérifie les identifiants fournis contre la table users.

    Retourne les informations du compte si le mot de passe correspond,
    sinon None (username inconnu ou mot de passe incorrect).
    """
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, username, hashed_password FROM users WHERE username = :username"),
            {"username": username},
        ).first()

    if row is None:
        return None

    if not verify_password(password, row.hashed_password):
        return None

    return {"id": row.id, "username": row.username}


def create_default_admin() -> None:
    """Crée le compte administrateur par défaut au démarrage, si configuré.

    Si ADMIN_PASSWORD est vide, aucun compte n'est créé (log un warning) :
    on ne veut pas créer un compte admin avec un mot de passe vide ou
    devinable par défaut. Le mot de passe est haché avant insertion, et
    l'insertion est idempotente (ON CONFLICT DO NOTHING) pour ne pas
    dupliquer le compte aux redémarrages successifs de l'API.
    """
    if not ADMIN_PASSWORD:
        logger.warning("[AUTH] ADMIN_PASSWORD est vide — aucun compte admin par défaut créé")
        return

    hashed = hash_password(ADMIN_PASSWORD)

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO users (username, hashed_password)
                VALUES (:username, :hashed_password)
                ON CONFLICT (username) DO NOTHING
                """
            ),
            {"username": ADMIN_USERNAME, "hashed_password": hashed},
        )

    logger.info(f"[AUTH] Compte admin par défaut vérifié/créé ({ADMIN_USERNAME})")
