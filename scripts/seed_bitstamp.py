"""Script de seed one-shot : peuple une table Postgres avec un historique Bitstamp.

Contrairement aux collecteurs de src/extract/, ce script n'est pas destiné a
être appelé en boucle par le pipeline principal : il charge une fois un
échantillon du dataset Kaggle Bitstamp (data/raw/kaggle/btcusd_1-min_data.csv)
dans une table dédiée, pour disposer d'un historique exploitable en base
(brique C2 : extraction depuis une base de données).
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

CSV_PATH = Path("data/raw/kaggle/btcusd_1-min_data.csv")

logger = get_logger("seed_bitstamp")


def ensure_table(engine: Engine, logger) -> None:
    """Crée la table historical_prices_bitstamp si elle n'existe pas encore."""
    ddl = text(
        """
        CREATE TABLE IF NOT EXISTS historical_prices_bitstamp (
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
    logger.info("[SEED] Table historical_prices_bitstamp prête")


def table_already_seeded(engine: Engine) -> bool:
    """Vérifie si la table contient déjà des lignes."""
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM historical_prices_bitstamp")).scalar()
    return count > 0


def load_and_clean_csv(logger) -> pd.DataFrame | None:
    """Charge le CSV Bitstamp et ne garde qu'un échantillon récent et propre.

    Supprime les minutes sans transaction (Close NaN) et ne conserve que les
    10 000 lignes les plus récentes, un échantillon suffisant pour la
    démonstration C2 sans charger des millions de lignes en base.
    """
    if not CSV_PATH.exists():
        logger.error(f"[SEED] Fichier introuvable : {CSV_PATH}")
        return None

    df = pd.read_csv(CSV_PATH)
    df = df.dropna(subset=["Close"])
    df = df.sort_values("Timestamp", ascending=False).head(10_000)

    logger.info(f"[SEED] {len(df)} lignes retenues après nettoyage")
    return df


def seed(engine: Engine, df: pd.DataFrame, logger) -> None:
    """Insère les lignes nettoyées en base, en ignorant les doublons (ts_unix).

    Utilise ON CONFLICT DO NOTHING sur ts_unix pour permettre de relancer le
    script sans créer de doublons. Le nombre de lignes effectivement
    insérées est déduit d'un comptage avant/après l'insertion.
    """
    insert_stmt = text(
        """
        INSERT INTO historical_prices_bitstamp (ts_unix, open, high, low, close, volume)
        VALUES (:ts_unix, :open, :high, :low, :close, :volume)
        ON CONFLICT (ts_unix) DO NOTHING
        """
    )

    rows = [
        {
            "ts_unix": int(row.Timestamp),
            "open": float(row.Open),
            "high": float(row.High),
            "low": float(row.Low),
            "close": float(row.Close),
            "volume": float(row.Volume),
        }
        for row in df.itertuples()
    ]

    try:
        with engine.begin() as conn:
            before = conn.execute(text("SELECT COUNT(*) FROM historical_prices_bitstamp")).scalar()
            conn.execute(insert_stmt, rows)
            after = conn.execute(text("SELECT COUNT(*) FROM historical_prices_bitstamp")).scalar()
    except SQLAlchemyError as exc:
        logger.error(f"[SEED] Erreur lors de l'insertion en base : {exc}")
        return

    logger.info(f"[SEED] {after - before} lignes effectivement insérées dans historical_prices_bitstamp")


def run() -> None:
    """Point d'entrée du seed : peuple historical_prices_bitstamp en une fois.

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
        logger.error("[SEED] Échec du chargement du CSV Bitstamp, seed annulé")
        return

    seed(engine, df, logger)

    duration = time.perf_counter() - start
    logger.info(f"[SEED] Terminé en {duration:.2f}s")


if __name__ == "__main__":
    run()
