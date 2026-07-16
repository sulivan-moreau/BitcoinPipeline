"""Service de lecture des relevés de prix Bitcoin depuis la table bitcoin_prices."""

from sqlalchemy import text

from src.utils.db import get_engine


def _row_to_dict(row) -> dict:
    """Convertit une ligne SQLAlchemy en dict JSON-sérialisable.

    Les colonnes timestamp/collected_at sont des TIMESTAMPTZ Postgres,
    renvoyées comme des objets datetime par SQLAlchemy : on les convertit
    en chaînes ISO 8601 pour correspondre au schéma PriceItem (champs str).
    """
    data = dict(row)
    for field in ("timestamp", "collected_at"):
        value = data.get(field)
        if hasattr(value, "isoformat"):
            data[field] = value.isoformat()
    return data


def get_latest_prices() -> list[dict]:
    """Retourne les 20 relevés de prix les plus récents, toutes sources confondues."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM bitcoin_prices ORDER BY collected_at DESC LIMIT 20")
        ).mappings().all()

    return [_row_to_dict(row) for row in rows]


def get_prices_by_source(source: str) -> list[dict]:
    """Retourne les 20 relevés de prix les plus récents pour une source donnée."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM bitcoin_prices WHERE source = :source ORDER BY collected_at DESC LIMIT 20"),
            {"source": source},
        ).mappings().all()

    return [_row_to_dict(row) for row in rows]
