"""Collecteur du prix du Bitcoin depuis un fichier CSV local (Coinbase).

Ce module illustre la brique C1 d'extraction de données depuis un fichier :
lecture d'un historique horaire Coinbase au format CryptoDataDownload
(dataset Kaggle), puis extraction et normalisation du prix le plus récent
dans le schéma commun du pipeline.
"""

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from src.utils.logger import get_logger

CSV_PATH = Path("data/raw/kaggle/BTC-Hourly.csv")

logger = get_logger("file_collector")


def load_csv(logger) -> pd.DataFrame | None:
    """Charge le CSV Coinbase en gérant l'éventuel commentaire CryptoDataDownload.

    Vérifie l'existence du fichier, détecte si la première ligne est un
    commentaire (au lieu de l'en-tête "unix,date,..."), et gère les erreurs
    de lecture (fichier vide ou illisible) sans lever d'exception.
    """
    if not CSV_PATH.exists():
        logger.error(f"[FILE] Fichier introuvable : {CSV_PATH}")
        return None

    try:
        with open(CSV_PATH, encoding="utf-8") as f:
            first_line = f.readline()
    except OSError as exc:
        logger.error(f"[FILE] Impossible de lire le fichier : {exc}")
        return None

    skiprows = 0 if "unix" in first_line.lower() else 1

    try:
        df = pd.read_csv(CSV_PATH, skiprows=skiprows)
    except pd.errors.EmptyDataError:
        logger.error("[FILE] Fichier CSV vide")
        return None
    except pd.errors.ParserError as exc:
        logger.error(f"[FILE] Erreur de parsing du CSV : {exc}")
        return None

    logger.info(f"[FILE] {len(df)} lignes chargées depuis BTC-Hourly.csv")
    return df


def get_latest_price(df: pd.DataFrame, logger) -> dict | None:
    """Extrait le prix de clôture le plus récent (colonne "unix" décroissante).

    Ignore les lignes dont la colonne "close" est NaN et cherche la ligne
    valide suivante, jusqu'à un nombre raisonnable d'essais. Retourne None
    si aucune ligne valide n'est trouvée.
    """
    sorted_df = df.sort_values("unix", ascending=False)

    max_attempts = min(len(sorted_df), 10)
    for i in range(max_attempts):
        row = sorted_df.iloc[i]
        close = row["close"]

        if pd.isna(close):
            logger.warning(f"[FILE] Valeur 'close' invalide (NaN) a la ligne unix={row['unix']}, ligne suivante")
            continue

        return {"price_usd": float(close), "unix_timestamp": int(row["unix"])}

    logger.error("[FILE] Aucune ligne valide trouvée dans le CSV")
    return None


def normalize_result(raw: dict) -> dict:
    """Transforme le prix Coinbase extrait dans le schéma commun du pipeline."""
    return {
        "source": "file_coinbase",
        "price_usd": raw["price_usd"],
        "timestamp": datetime.fromtimestamp(raw["unix_timestamp"], tz=UTC).isoformat(),
        "collected_at": datetime.now(UTC).isoformat(),
    }


def run() -> list[dict]:
    """Point d'entrée du collecteur : lit et normalise le prix Coinbase le plus récent.

    Ne lève jamais d'exception et ne fait pas sys.exit : en cas d'échec a
    n'importe quelle étape, retourne une liste vide afin que le pipeline
    global puisse continuer avec les autres sources.
    """
    df = load_csv(logger)

    if df is None:
        logger.error("[FILE] Échec du chargement du CSV Coinbase")
        logger.info("[FILE] Collecte terminée | 0 prix récupéré (échec)")
        return []

    raw = get_latest_price(df, logger)

    if raw is None:
        logger.error("[FILE] Échec de l'extraction du prix le plus récent")
        logger.info("[FILE] Collecte terminée | 0 prix récupéré (échec)")
        return []

    result = normalize_result(raw)
    logger.info("[FILE] Collecte terminée | 1 prix récupéré (Coinbase)")
    return [result]


if __name__ == "__main__":
    run()
