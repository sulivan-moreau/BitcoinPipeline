"""Collecteur du prix du Bitcoin depuis la base de données Bitstamp.

Ce module illustre la brique C2 d'extraction de données depuis une base de
données : requêtes SQL documentées sur la table historical_prices_bitstamp
(Postgres, peuplée au préalable par scripts/seed_bitstamp.py), extraction du
dernier prix connu et normalisation dans le schéma commun du pipeline.
"""

from datetime import UTC, datetime

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

from src.utils.db import get_engine
from src.utils.logger import get_logger

logger = get_logger("db_collector")


def get_latest_price(engine, logger) -> dict | None:
    """Requête documentée : dernier prix Bitstamp connu.

    Contexte métier : la table historical_prices_bitstamp contient un
    échantillon horodaté (ts_unix) de l'historique Bitstamp. On veut ici le
    prix de clôture le plus récent, pour l'intégrer au pipeline au même
    titre que les autres sources.
    """
    # Récupère l'enregistrement le plus récent de la table (tri décroissant
    # sur le timestamp Unix, LIMIT 1 pour ne remonter qu'une ligne)
    query = text(
        """
        SELECT ts_unix, close
        FROM historical_prices_bitstamp
        ORDER BY ts_unix DESC
        LIMIT 1
        """
    )

    try:
        with engine.connect() as conn:
            row = conn.execute(query).first()
    except SQLAlchemyError as exc:
        logger.error(f"[DB] Erreur SQL lors de la récupération du dernier prix : {exc}")
        return None

    if row is None:
        logger.error("[DB] Table historical_prices_bitstamp vide — lancez scripts/seed_bitstamp.py")
        return None

    return {"price_usd": float(row.close), "unix_timestamp": int(row.ts_unix)}


def get_price_stats(engine, logger) -> dict:
    """Requête documentée : statistiques descriptives de l'échantillon Bitstamp.

    Contexte métier : donne une vision rapide de la santé des données
    chargées (nombre de lignes, moyenne/min/max du prix de clôture). Purement
    informatif — le résultat est loggé mais n'entre pas dans celui de run().
    """
    # Statistiques descriptives sur l'échantillon Bitstamp chargé, utile
    # pour vérifier la cohérence des données collectées
    query = text(
        """
        SELECT COUNT(*) AS total_rows, AVG(close) AS avg_close,
               MIN(close) AS min_close, MAX(close) AS max_close
        FROM historical_prices_bitstamp
        """
    )

    try:
        with engine.connect() as conn:
            row = conn.execute(query).first()
    except SQLAlchemyError as exc:
        logger.warning(f"[DB] Erreur SQL lors du calcul des statistiques : {exc}")
        return {}

    stats = {
        "total_rows": row.total_rows,
        "avg_close": row.avg_close,
        "min_close": row.min_close,
        "max_close": row.max_close,
    }
    logger.info(
        f"[DB] Stats Bitstamp | {stats['total_rows']} lignes | "
        f"moyenne={stats['avg_close']} | min={stats['min_close']} | max={stats['max_close']}"
    )
    return stats


def normalize_result(raw: dict) -> dict:
    """Transforme le prix Bitstamp extrait dans le schéma commun du pipeline."""
    return {
        "source": "db_bitstamp",
        "price_usd": raw["price_usd"],
        "timestamp": datetime.fromtimestamp(raw["unix_timestamp"], tz=UTC).isoformat(),
        "collected_at": datetime.now(UTC).isoformat(),
    }


def run() -> list[dict]:
    """Point d'entrée du collecteur : lit et normalise le dernier prix Bitstamp en base.

    Ne lève jamais d'exception et ne fait pas sys.exit : en cas d'échec de
    connexion ou d'absence de données, retourne une liste vide afin que le
    pipeline global puisse continuer avec les autres sources.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except (ValueError, SQLAlchemyError) as exc:
        logger.error(f"[DB] Impossible de se connecter à la base de données : {exc}")
        logger.info("[DB] Collecte terminée | 0 prix récupéré (échec)")
        return []

    get_price_stats(engine, logger)

    raw = get_latest_price(engine, logger)

    if raw is None:
        logger.info("[DB] Collecte terminée | 0 prix récupéré (échec)")
        return []

    result = normalize_result(raw)
    logger.info("[DB] Collecte terminée | 1 prix récupéré (Bitstamp)")
    return [result]


if __name__ == "__main__":
    run()
