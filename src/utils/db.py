"""Utilitaires de connexion a la base de donnees."""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import Connection


def get_engine() -> Engine:
    """Cree un Engine SQLAlchemy a partir de DATABASE_URL.

    Leve une ValueError si la variable d'environnement est absente.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("La variable d'environnement DATABASE_URL est absente.")

    return create_engine(database_url)


@contextmanager
def get_connection() -> Iterator[Connection]:
    """Fournit une connexion et libere proprement les ressources (connexion + engine)."""
    engine = get_engine()
    connection = engine.connect()
    try:
        yield connection
    finally:
        connection.close()
        engine.dispose()
