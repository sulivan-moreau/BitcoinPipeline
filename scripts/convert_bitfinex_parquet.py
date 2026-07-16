"""Script de conversion one-shot : CSV Bitfinex vers Parquet (préparation big data).

Contrairement aux collecteurs de src/extract/, ce script n'est pas destiné a
être appelé en boucle par le pipeline principal : il transforme une fois
l'archive Bitfinex OHLC minute (data/raw/kaggle/btcusd.csv) en fichier
Parquet, afin de simuler un entrepôt big data exploitable par PySpark
(brique C2 : extraction depuis un système big data).
"""

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.logger import get_logger

CSV_PATH = Path("data/raw/kaggle/btcusd.csv")
PARQUET_PATH = Path("data/raw/bigdata/bitfinex_btcusd.parquet")

logger = get_logger("convert_bitfinex_parquet")


def convert(logger) -> None:
    """Convertit le CSV Bitfinex en Parquet, en filtrant les lignes incomplètes.

    Ce script ne peut rien faire sans le fichier source : contrairement aux
    collecteurs qui doivent survivre à l'absence d'une source, son absence
    est ici fatale (sys.exit(1)).
    """
    if not CSV_PATH.exists():
        logger.error(f"[CONVERT] Fichier introuvable : {CSV_PATH}")
        sys.exit(1)

    PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(CSV_PATH)
    total_rows = len(df)

    df = df.dropna(subset=["close"])
    logger.info(f"[CONVERT] {total_rows} lignes lues, {len(df)} conservées après nettoyage")

    try:
        import pyarrow  # noqa: F401
    except ImportError:
        logger.error("[CONVERT] pyarrow n'est pas installé — installez-le via `uv add pyarrow`")
        sys.exit(1)

    df.to_parquet(PARQUET_PATH, index=False, engine="pyarrow")

    size_mb = PARQUET_PATH.stat().st_size / (1024 * 1024)
    logger.info(f"[CONVERT] Fichier Parquet généré ({size_mb:.2f} MB) : {PARQUET_PATH}")


def run() -> None:
    """Point d'entrée du script : convertit le CSV Bitfinex en Parquet en mesurant la durée."""
    start = time.perf_counter()

    convert(logger)

    duration = time.perf_counter() - start
    logger.info(f"[CONVERT] Terminé en {duration:.2f}s")


if __name__ == "__main__":
    run()
