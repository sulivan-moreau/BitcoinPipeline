"""Script de seed one-shot : échantillon Bitstamp historique pour la jointure SQL C3.

Contrairement au seed principal (scripts/seed_bitstamp.py, qui charge les
10 000 minutes les PLUS RÉCENTES pour le collecteur BDD du pipeline, brique
C2), ce script charge un échantillon Bitstamp sur la MÊME période que
l'historique Coinbase (data/raw/kaggle/BTC-Hourly.csv, qui s'arrête au
2022-03-01), dans une table séparée (bitstamp_prices_2022_sample). Sans ce
recalage temporel, une jointure entre Bitstamp (données récentes) et
Coinbase (données figées à 2022) ne retournerait aucune ligne : les deux
échantillons ne se chevauchent pas dans le temps. Ce script prépare la
jointure documentée dans src/aggregate_sql.py (brique C3 : agrégation d'au
moins deux sources en SQL, via JOIN).
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

logger = get_logger("seed_bitstamp_join_sample")


def ensure_table(engine: Engine, logger) -> None:
    """Crée la table bitstamp_prices_2022_sample si elle n'existe pas encore."""
    ddl = text(
        """
        CREATE TABLE IF NOT EXISTS bitstamp_prices_2022_sample (
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
    logger.info("[SEED] Table bitstamp_prices_2022_sample prête")


def table_already_seeded(engine: Engine) -> bool:
    """Vérifie si la table contient déjà des lignes."""
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM bitstamp_prices_2022_sample")).scalar()
    return count > 0


def get_coinbase_cutoff(engine: Engine, logger) -> int | None:
    """Récupère le timestamp Unix le plus récent de coinbase_prices.

    Sert de borne supérieure pour l'échantillon Bitstamp, afin de garantir
    un chevauchement temporel entre les deux sources pour la jointure.
    """
    try:
        with engine.connect() as conn:
            cutoff = conn.execute(text("SELECT MAX(ts_unix) FROM coinbase_prices")).scalar()
    except SQLAlchemyError as exc:
        logger.error(f"[SEED] Impossible de lire coinbase_prices : {exc}")
        return None

    if cutoff is None:
        logger.error("[SEED] coinbase_prices est vide — lancez scripts/seed_coinbase.py d'abord")
        return None

    return int(cutoff)


def load_and_clean_csv(logger, cutoff: int) -> pd.DataFrame | None:
    """Charge le CSV Bitstamp et ne garde que les minutes antérieures au cutoff Coinbase.

    Supprime les minutes sans transaction (Close NaN), filtre sur
    Timestamp <= cutoff, puis ne conserve que les 10 000 lignes les plus
    récentes de cette fenêtre — un échantillon suffisant pour démontrer la
    jointure sans charger des millions de lignes en base.
    """
    if not CSV_PATH.exists():
        logger.error(f"[SEED] Fichier introuvable : {CSV_PATH}")
        return None

    df = pd.read_csv(CSV_PATH)
    df = df.dropna(subset=["Close"])
    df = df[df["Timestamp"] <= cutoff]
    df = df.sort_values("Timestamp", ascending=False).head(10_000)

    logger.info(f"[SEED] {len(df)} lignes retenues après nettoyage (cutoff Unix={cutoff})")
    return df


def seed(engine: Engine, df: pd.DataFrame, logger) -> None:
    """Insère les lignes nettoyées en base, en ignorant les doublons (ts_unix)."""
    insert_stmt = text(
        """
        INSERT INTO bitstamp_prices_2022_sample (ts_unix, open, high, low, close, volume)
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
            before = conn.execute(text("SELECT COUNT(*) FROM bitstamp_prices_2022_sample")).scalar()
            conn.execute(insert_stmt, rows)
            after = conn.execute(text("SELECT COUNT(*) FROM bitstamp_prices_2022_sample")).scalar()
    except SQLAlchemyError as exc:
        logger.error(f"[SEED] Erreur lors de l'insertion en base : {exc}")
        return

    logger.info(f"[SEED] {after - before} lignes effectivement insérées dans bitstamp_prices_2022_sample")


def run() -> None:
    """Point d'entrée du seed : peuple bitstamp_prices_2022_sample en une fois.

    Nécessite que coinbase_prices soit déjà peuplée (scripts/seed_coinbase.py)
    pour déterminer la fenêtre temporelle cible. Un échec de connexion à la
    base est fatal (sys.exit(1)).
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

    cutoff = get_coinbase_cutoff(engine, logger)
    if cutoff is None:
        return

    df = load_and_clean_csv(logger, cutoff)
    if df is None:
        logger.error("[SEED] Échec du chargement du CSV Bitstamp, seed annulé")
        return

    seed(engine, df, logger)

    duration = time.perf_counter() - start
    logger.info(f"[SEED] Terminé en {duration:.2f}s")


if __name__ == "__main__":
    run()
