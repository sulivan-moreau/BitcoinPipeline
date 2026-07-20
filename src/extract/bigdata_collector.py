"""Collecteur du prix du Bitcoin depuis l'archive big data Bitfinex (PySpark).

Ce module illustre la brique C2 d'extraction de données depuis un système
big data : lecture de l'archive Parquet Bitfinex (~4,5M lignes de ticks OHLC
minute, préparée par scripts/convert_bitfinex_parquet.py) via PySpark en
local[*], calcul de statistiques descriptives et extraction du prix le plus
récent, normalisé dans le schéma commun du pipeline.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.functions import col, desc

from src.utils.logger import get_logger
from src.utils.results import save_last_result

PARQUET_PATH = Path("data/raw/bigdata/bitfinex_btcusd.parquet")

logger = get_logger("bigdata_collector")


def init_spark(logger) -> SparkSession | None:
    """Initialise une SparkSession locale pour lire l'archive Bitfinex.

    Utilise local[*] pour paralléliser sur tous les cœurs disponibles, avec
    une mémoire driver de 2g (suffisante pour ~4,5M lignes, inutile de monter
    à 8g pour ce volume). Le niveau de log Spark est réduit à ERROR pour ne
    pas polluer les logs applicatifs avec le bruit interne de Spark.
    """
    try:
        spark = (
            SparkSession.builder.appName("BitcoinPipeline-Bitfinex")
            .master("local[*]")
            .config("spark.driver.memory", "2g")
            .getOrCreate()
        )
        spark.sparkContext.setLogLevel("ERROR")
    except Exception as exc:
        logger.error(f"[SPARK] Échec de l'initialisation de la SparkSession : {exc}")
        return None

    logger.info("[SPARK] SparkSession initialisée (local[*])")
    return spark


def load_data(spark: SparkSession, logger) -> DataFrame | None:
    """Charge l'archive Parquet Bitfinex et filtre les lignes exploitables.

    Ne garde que les lignes où "close" n'est pas null : les ticks sans
    transaction n'ont pas de valeur de clôture exploitable pour le pipeline.
    """
    if not PARQUET_PATH.exists():
        logger.error("[SPARK] Fichier Parquet introuvable — lancez scripts/convert_bitfinex_parquet.py")
        return None

    df = spark.read.parquet(str(PARQUET_PATH))
    df = df.filter(col("close").isNotNull())

    logger.info(f"[SPARK] {df.count()} lignes chargées depuis l'archive Bitfinex")
    return df


def get_latest_price(df: DataFrame, logger) -> dict | None:
    """Requête documentée : dernier prix Bitfinex connu.

    Équivalent SQL : ORDER BY time DESC LIMIT 1. orderBy(desc) + first() est
    acceptable ici car Spark optimise ce pattern en un seul partitionnement,
    contrairement à un collect() complet suivi d'un tri en mémoire Python.
    """
    latest_row = df.orderBy(desc("time")).first()

    if latest_row is None:
        logger.error("[SPARK] Aucune ligne disponible dans l'archive Bitfinex")
        return None

    return {"price_usd": float(latest_row["close"]), "unix_timestamp": int(latest_row["time"])}


def get_stats(df: DataFrame, logger) -> None:
    """Requête documentée : statistiques descriptives sur le prix de clôture Bitfinex.

    Calcule count/moyenne/min/max via une agrégation Spark distribuée.
    Purement informatif — le résultat est loggé mais n'entre pas dans celui
    retourné par run() ; une erreur ici ne doit pas bloquer le collecteur.
    """
    try:
        stats_row = df.agg(
            F.count("close").alias("count"),
            F.avg("close").alias("avg_close"),
            F.min("close").alias("min_close"),
            F.max("close").alias("max_close"),
        ).first()

        logger.info(
            f"[SPARK] Stats Bitfinex | {stats_row['count']} lignes | "
            f"moyenne={stats_row['avg_close']} | min={stats_row['min_close']} | max={stats_row['max_close']}"
        )
    except Exception as exc:
        logger.warning(f"[SPARK] Erreur lors du calcul des statistiques : {exc}")


def normalize_result(raw: dict) -> dict:
    """Transforme le prix Bitfinex extrait dans le schéma commun du pipeline.

    Le timestamp Bitfinex ("time") peut être en secondes ou en millisecondes
    selon la source ; on détecte le format via l'ordre de grandeur de la
    valeur (un timestamp en secondes tient sur 10 chiffres jusqu'en 2286,
    un timestamp en millisecondes en compte 13).
    """
    unix_timestamp = raw["unix_timestamp"]
    if unix_timestamp > 10**12:
        unix_timestamp //= 1000

    return {
        "source": "bigdata_bitfinex",
        "price_usd": raw["price_usd"],
        "timestamp": datetime.fromtimestamp(unix_timestamp, tz=UTC).isoformat(),
        "collected_at": datetime.now(UTC).isoformat(),
    }


def run() -> list[dict]:
    """Point d'entrée du collecteur : lit l'archive Bitfinex via Spark et normalise le dernier prix.

    Ne lève jamais d'exception et ne fait pas sys.exit : en cas d'échec à
    n'importe quelle étape, retourne une liste vide afin que le pipeline
    global puisse continuer avec les autres sources. La SparkSession est
    systématiquement arrêtée (bloc finally), même en cas d'erreur.
    """
    spark = init_spark(logger)
    if spark is None:
        logger.info("[SPARK] Collecte terminée | 0 prix récupéré (échec)")
        return []

    try:
        df = load_data(spark, logger)
        if df is None:
            logger.info("[SPARK] Collecte terminée | 0 prix récupéré (échec)")
            return []

        get_stats(df, logger)

        raw = get_latest_price(df, logger)
        if raw is None:
            logger.info("[SPARK] Collecte terminée | 0 prix récupéré (échec)")
            return []

        result = normalize_result(raw)
        save_last_result(result["source"], [result])
        logger.info("[SPARK] Collecte terminée | 1 prix récupéré (Bitfinex)")
        return [result]
    finally:
        spark.stop()


if __name__ == "__main__":
    run()
