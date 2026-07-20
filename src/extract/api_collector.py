"""Collecteur du prix du Bitcoin depuis l'API publique CoinGecko.

Ce module illustre la brique C1 d'extraction de données depuis un service
web REST : appel HTTP GET vers un endpoint public, gestion des erreurs
(timeout, rate limit, autres erreurs réseau) et normalisation du résultat
dans le schéma commun du pipeline.
"""

import os
import time
from datetime import UTC, datetime

import requests

from src.utils.logger import get_logger
from src.utils.results import save_last_result

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
# Optionnelle : aucune clé n'est requise pour cet endpoint public, mais la
# variable est prête si CoinGecko venait a exiger une clé a l'avenir.
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")

logger = get_logger("api_collector")


def fetch_price(logger) -> dict | None:
    """Interroge l'API CoinGecko pour recuperer le prix actuel du BTC en USD.

    Gere les erreurs sans jamais lever d'exception : timeout, rate limit
    (429, avec une seule tentative de retry apres 2s) et toute autre erreur
    reseau. Retourne None en cas d'echec.
    """
    params = {"ids": "bitcoin", "vs_currencies": "usd"}

    try:
        response = requests.get(COINGECKO_URL, params=params, timeout=10)
    except requests.Timeout:
        logger.warning("[API] Timeout lors de l'appel a CoinGecko")
        return None
    except requests.RequestException as exc:
        logger.warning(f"[API] Erreur reseau lors de l'appel a CoinGecko : {exc}")
        return None

    if response.status_code == 429:
        logger.warning("[API] Rate limit atteint (429), nouvelle tentative dans 2s")
        time.sleep(2)
        try:
            response = requests.get(COINGECKO_URL, params=params, timeout=10)
        except requests.Timeout:
            logger.warning("[API] Timeout lors du retry apres rate limit")
            return None
        except requests.RequestException as exc:
            logger.warning(f"[API] Erreur reseau lors du retry apres rate limit : {exc}")
            return None

        if response.status_code == 429:
            logger.warning("[API] Rate limit toujours atteint apres retry, abandon")
            return None

    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning(f"[API] Reponse invalide de CoinGecko : {exc}")
        return None

    data = response.json()
    price_usd = data["bitcoin"]["usd"]

    return {"price_usd": float(price_usd), "raw_timestamp": None}


def normalize_result(raw: dict) -> dict:
    """Transforme le resultat brut de CoinGecko dans le schema commun du pipeline."""
    now = datetime.now(UTC).isoformat()
    return {
        "source": "api_coingecko",
        "price_usd": raw["price_usd"],
        "timestamp": now,
        "collected_at": now,
    }


def run() -> list[dict]:
    """Point d'entree du collecteur : recupere et normalise le prix du BTC.

    Ne leve jamais d'exception et ne fait pas sys.exit : en cas d'echec,
    retourne une liste vide afin que le pipeline global puisse continuer
    avec les autres sources.
    """
    raw = fetch_price(logger)

    if raw is None:
        logger.error("[API] Echec de la recuperation du prix depuis CoinGecko")
        logger.info("[API] Collecte terminée | 0 prix récupéré (échec)")
        return []

    result = normalize_result(raw)
    save_last_result(result["source"], [result])
    logger.info("[API] Collecte terminée | 1 prix récupéré")
    return [result]


if __name__ == "__main__":
    run()
