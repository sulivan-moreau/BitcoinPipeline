"""Script d'import du jeu de données final en base de données (C4).

Ce module persiste le résultat de l'agrégation multi-sources
(src/normalize.py) dans la table Postgres bitcoin_prices, conforme au MPD
documenté dans docs/merise_mcd.md, et exporte le même résultat en CSV final
dans data/processed/.
"""

import csv
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.normalize import run as normalize_run
from src.utils.db import get_engine
from src.utils.logger import get_logger

CSV_OUTPUT_PATH = Path("data/processed/bitcoin_prices_final.csv")

logger = get_logger("persist")


def ensure_table(engine, logger) -> None:
    """Crée la table bitcoin_prices si elle n'existe pas, conformément au MPD (docs/merise_mcd.md)."""
    ddl = text(
        """
        CREATE TABLE IF NOT EXISTS bitcoin_prices (
            id SERIAL PRIMARY KEY,
            source VARCHAR(50) NOT NULL,
            price_usd NUMERIC(12, 2) NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL,
            collected_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    with engine.begin() as conn:
        conn.execute(ddl)
    logger.info("[PERSIST] Table bitcoin_prices prête")


def insert_prices(engine, entries: list[dict], logger) -> int:
    """Insère chaque entrée dans bitcoin_prices, un nouveau relevé par exécution.

    Contrairement au seed Bitstamp (échantillon figé chargé une fois, avec
    contrainte UNIQUE), aucune contrainte d'unicité n'est appliquée ici :
    chaque exécution du pipeline ajoute un nouveau relevé de prix, pour
    constituer un historique des collectes dans le temps. Les erreurs SQL
    sont gérées par entrée individuellement, afin qu'un échec isolé
    n'empêche pas l'insertion des autres.
    """
    insert_stmt = text(
        """
        INSERT INTO bitcoin_prices (source, price_usd, timestamp, collected_at)
        VALUES (:source, :price_usd, :timestamp, :collected_at)
        """
    )

    inserted = 0
    for entry in entries:
        try:
            with engine.begin() as conn:
                conn.execute(insert_stmt, entry)
            inserted += 1
        except SQLAlchemyError as exc:
            logger.error(f"[PERSIST] Échec de l'insertion pour la source {entry.get('source')} : {exc}")

    logger.info(f"[PERSIST] {inserted} lignes insérées dans bitcoin_prices")
    return inserted


def export_csv(entries: list[dict], logger) -> None:
    """Exporte les entrées nettoyées en CSV final (colonnes source, price_usd, timestamp, collected_at)."""
    CSV_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["source", "price_usd", "timestamp", "collected_at"]
    with open(CSV_OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            writer.writerow({field: entry[field] for field in fieldnames})

    logger.info(f"[PERSIST] {len(entries)} lignes écrites dans {CSV_OUTPUT_PATH}")


def run() -> None:
    """Point d'entrée : normalise, persiste en base et exporte le résultat final en CSV.

    Un jeu de données vide (agrégation infructueuse) ou une base
    inaccessible sont tous deux fatals (sys.exit(1)) : persister un jeu de
    données vide n'a pas de sens, et ce script ne peut rien faire sans base.
    """
    start = datetime.now(UTC)

    entries = normalize_run()

    if not entries:
        logger.error(
            "[PERSIST] Aucune donnée à persister — le pipeline d'agrégation n'a produit aucun résultat exploitable"
        )
        sys.exit(1)

    engine = get_engine()

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error(f"[PERSIST] Impossible de se connecter à la base de données : {exc}")
        sys.exit(1)

    ensure_table(engine, logger)
    insert_prices(engine, entries, logger)
    export_csv(entries, logger)

    duration = (datetime.now(UTC) - start).total_seconds()
    logger.info(f"[PERSIST] Terminé en {duration:.2f}s")


if __name__ == "__main__":
    run()
