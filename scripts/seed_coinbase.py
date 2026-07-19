"""Script de seed one-shot : peuple une table Postgres avec l'historique Coinbase.

Contrairement aux collecteurs de src/extract/, ce script n'est pas destiné a
être appelé en boucle par le pipeline principal : il charge une fois
l'historique horaire Coinbase (data/raw/kaggle/BTC-Hourly.csv) dans une table
dédiée, pour permettre une agrégation SQL multi-sources (JOIN avec Bitstamp,
voir scripts/seed_bitstamp_join_sample.py et src/aggregate_sql.py — brique C3).
"""

import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv()

from src.utils.db import get_engine
from src.utils.logger import get_logger

CSV_PATH = Path("data/raw/kaggle/BTC-Hourly.csv")

logger = get_logger("seed_coinbase")


def ensure_table(engine: Engine, logger) -> None:
    """Crée la table coinbase_prices si elle n'existe pas encore."""
    ddl = text(
        """
        CREATE TABLE IF NOT EXISTS coinbase_prices (
            id SERIAL PRIMARY KEY,
            ts_unix BIGINT NOT NULL,
            open NUMERIC,
            high NUMERIC,
            low NUMERIC,
            close NUMERIC,
            volume NUMERIC,
            UNIQUE(ts_unix)
        )
        """
    )
    with engine.begin() as conn:
        conn.execute(ddl)
    logger.info("[SEED] Table coinbase_prices prête")


def table_already_seeded(engine: Engine) -> bool:
    """Vérifie si la table contient déjà des lignes."""
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM coinbase_prices")).scalar()
    return count > 0


def load_and_clean_csv(logger) -> pd.DataFrame | None:
    """Charge le CSV Coinbase en gérant l'éventuel commentaire CryptoDataDownload.

    Contrairement au seed Bitstamp (données minute, ~7,6M lignes, échantillon
    de 10 000 lignes nécessaire), l'historique horaire Coinbase ne compte que
    ~33 000 lignes : il est chargé intégralement, sans échantillonnage.
    """
    if not CSV_PATH.exists():
        logger.error(f"[SEED] Fichier introuvable : {CSV_PATH}")
        return None

    with open(CSV_PATH, encoding="utf-8") as f:
        first_line = f.readline()

    skiprows = 0 if "unix" in first_line.lower() else 1

    df = pd.read_csv(CSV_PATH, skiprows=skiprows)
    df = df.rename(columns={"Volume USD": "volume_usd"})
    df = df.dropna(subset=["close"])

    logger.info(f"[SEED] {len(df)} lignes retenues après nettoyage")
    return df


def seed(engine: Engine, df: pd.DataFrame, logger) -> None:
    """Insère les lignes nettoyées en base, en ignorant les doublons (ts_unix).

    Utilise ON CONFLICT DO NOTHING sur ts_unix pour permettre de relancer le
    script sans créer de doublons. Le nombre de lignes effectivement
    insérées est déduit d'un comptage avant/après l'insertion. La colonne
    "Volume USD" du CSV est utilisée comme volume (plutôt que "Volume BTC"),
    pour rester comparable en dollars avec le reste du pipeline.
    """
    insert_stmt = text(
        """
        INSERT INTO coinbase_prices (ts_unix, open, high, low, close, volume)
        VALUES (:ts_unix, :open, :high, :low, :close, :volume)
        ON CONFLICT (ts_unix) DO NOTHING
        """
    )

    rows = [
        {
            "ts_unix": int(row.unix),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume_usd),
        }
        for row in df.itertuples()
    ]

    try:
        with engine.begin() as conn:
            before = conn.execute(text("SELECT COUNT(*) FROM coinbase_prices")).scalar()
            conn.execute(insert_stmt, rows)
            after = conn.execute(text("SELECT COUNT(*) FROM coinbase_prices")).scalar()
    except SQLAlchemyError as exc:
        logger.error(f"[SEED] Erreur lors de l'insertion en base : {exc}")
        return

    logger.info(f"[SEED] {after - before} lignes effectivement insérées dans coinbase_prices")


def run() -> None:
    """Point d'entrée du seed : peuple coinbase_prices en une fois.

    Un échec de connexion à la base est fatal (sys.exit(1)) : un seed ne
    peut pas continuer sans base de données, contrairement aux collecteurs
    du pipeline principal qui doivent survivre à l'échec d'une source.
    """
    start = time.perf_counter()

    engine = get_engine()

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error(f"[SEED] Impossible de se connecter à la base de données : {exc}")
        sys.exit(1)

    ensure_table(engine, logger)

    if table_already_seeded(engine):
        logger.info("[SEED] Table déjà peuplée, rien à faire (relance manuelle possible en vidant la table)")
        return

    df = load_and_clean_csv(logger)
    if df is None:
        logger.error("[SEED] Échec du chargement du CSV Coinbase, seed annulé")
        return

    seed(engine, df, logger)

    duration = time.perf_counter() - start
    logger.info(f"[SEED] Terminé en {duration:.2f}s")


if __name__ == "__main__":
    run()
