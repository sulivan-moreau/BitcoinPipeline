"""Agrégation SQL de deux sources via JOIN (C3 : agrégation multi-sources).

Complément à src/normalize.py (qui agrège les 5 sources normalisées en
Python) : ce module démontre l'agrégation d'au moins deux sources
directement en SQL, via une jointure entre deux tables Postgres alimentées
par des sources différentes — Bitstamp (base de données, C2) et Coinbase
(fichier, C1) — plutôt qu'en mémoire côté application.

Prérequis : scripts/seed_coinbase.py puis scripts/seed_bitstamp_join_sample.py
doivent avoir été exécutés (dans cet ordre) pour peupler coinbase_prices et
bitstamp_prices_2022_sample.
"""

from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

from src.utils.db import get_engine
from src.utils.logger import get_logger

logger = get_logger("aggregate_sql")


def join_bitstamp_coinbase(engine, logger) -> list[dict]:
    """Requête documentée : jointure SQL entre Bitstamp et Coinbase (C3).

    Contexte métier : comparer, heure par heure, le prix de clôture Bitstamp
    (moyenne des relevés minute) et le prix de clôture Coinbase, pour la
    même fenêtre temporelle (les deux échantillons sont recalés sur la
    période de l'historique Coinbase par scripts/seed_bitstamp_join_sample.py).

    Deux CTE (WITH) préparent chaque source séparément :
    - bitstamp_hourly : agrège Bitstamp (minute) en moyenne horaire, car
      Coinbase n'a qu'un relevé par heure — sans cette agrégation, le JOIN
      produirait plusieurs lignes Bitstamp pour une seule ligne Coinbase.
    - coinbase_hourly : normalise juste le format du timestamp pour matcher
      la même granularité.
    Le JOIN final relie les deux CTE sur l'heure commune (hour_bucket) et
    calcule l'écart de prix entre les deux exchanges.
    """
    query = text(
        """
        WITH bitstamp_hourly AS (
            SELECT
                date_trunc('hour', to_timestamp(ts_unix)) AS hour_bucket,
                AVG(close) AS bitstamp_avg_close
            FROM bitstamp_prices_2022_sample
            GROUP BY date_trunc('hour', to_timestamp(ts_unix))
        ),
        coinbase_hourly AS (
            SELECT
                date_trunc('hour', to_timestamp(ts_unix)) AS hour_bucket,
                close AS coinbase_close
            FROM coinbase_prices
        )
        SELECT
            b.hour_bucket,
            ROUND(b.bitstamp_avg_close, 2) AS bitstamp_avg_close,
            c.coinbase_close,
            ROUND(b.bitstamp_avg_close - c.coinbase_close, 2) AS price_diff_usd
        FROM bitstamp_hourly b
        JOIN coinbase_hourly c ON b.hour_bucket = c.hour_bucket
        ORDER BY b.hour_bucket DESC
        LIMIT 20
        """
    )

    try:
        with engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
    except SQLAlchemyError as exc:
        logger.error(f"[AGGREGATE_SQL] Erreur SQL lors de la jointure Bitstamp/Coinbase : {exc}")
        return []

    result = []
    for row in rows:
        entry = dict(row)
        if isinstance(entry["hour_bucket"], datetime):
            entry["hour_bucket"] = entry["hour_bucket"].isoformat()
        result.append(entry)

    return result


def run() -> list[dict]:
    """Point d'entrée : exécute la jointure SQL Bitstamp/Coinbase et logue le résultat.

    Ne lève jamais d'exception : en cas d'échec de connexion ou de tables
    absentes, retourne une liste vide plutôt que de bloquer.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except (ValueError, SQLAlchemyError) as exc:
        logger.error(f"[AGGREGATE_SQL] Impossible de se connecter à la base de données : {exc}")
        return []

    rows = join_bitstamp_coinbase(engine, logger)

    if not rows:
        logger.info("[AGGREGATE_SQL] Jointure Bitstamp/Coinbase | 0 ligne (tables absentes ou vides ?)")
        return []

    logger.info(f"[AGGREGATE_SQL] Jointure Bitstamp/Coinbase | {len(rows)} heures comparées")
    for row in rows[:5]:
        logger.info(
            f"[AGGREGATE_SQL] {row['hour_bucket']} | Bitstamp={row['bitstamp_avg_close']}$ | "
            f"Coinbase={row['coinbase_close']}$ | écart={row['price_diff_usd']}$"
        )

    return rows


if __name__ == "__main__":
    run()
