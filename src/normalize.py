"""Script d'agrégation multi-sources du prix du Bitcoin (C3).

Ce module fusionne les résultats des 5 collectors du pipeline (API
CoinGecko, scraping Kraken, fichier Coinbase, base de données Bitstamp, big
data Bitfinex) en un jeu de données unique : collecte tolérante aux pannes,
suppression des entrées corrompues, puis homogénéisation des formats
(prix arrondi, timestamps ISO 8601 UTC stricts).
"""

from datetime import UTC, datetime

from src.extract import (
    api_collector,
    bigdata_collector,
    db_collector,
    file_collector,
    scraper_collector,
)
from src.utils.logger import get_logger

logger = get_logger("normalize")

REQUIRED_KEYS = {"source", "price_usd", "timestamp", "collected_at"}
MIN_PRICE_USD = 1
MAX_PRICE_USD = 1_000_000


def collect_all(logger) -> list[dict]:
    """Appelle les 5 collectors et concatène leurs résultats.

    Chaque appel est isolé : un collector qui lève une exception imprévue
    (au-delà de son propre run(), déjà tolérant et retournant [] en cas
    d'échec géré) ne doit jamais interrompre la collecte des autres sources.
    """
    collectors = [
        ("api_collector", api_collector),
        ("scraper_collector", scraper_collector),
        ("file_collector", file_collector),
        ("db_collector", db_collector),
        ("bigdata_collector", bigdata_collector),
    ]

    results: list[dict] = []
    for name, collector in collectors:
        try:
            results.extend(collector.run())
        except Exception as exc:
            logger.error(f"[NORMALIZE] Échec inattendu du collector {name} : {exc}")

    logger.info(f"[NORMALIZE] {len(results)} résultats bruts collectés sur 5 sources")
    return results


def is_valid_entry(entry: dict, logger) -> bool:
    """Détecte les entrées corrompues avant homogénéisation.

    Trois familles de contrôles, chacune correspondant à une classe de bug
    en amont qu'on veut intercepter ici plutôt que polluer le jeu de
    données final :
    - clés manquantes : un collector qui retourne un schéma incomplet ;
    - price_usd hors de [1, 1_000_000] USD : filtre les valeurs aberrantes
      de parsing (prix à 0, ou à plusieurs milliards suite à une erreur de
      nettoyage de chaîne comme dans le bug de concaténation déjà rencontré
      côté scraping) ;
    - timestamp/collected_at non parsables en ISO 8601 : un format de date
      invalide rendrait l'entrée inexploitable en aval.
    """
    source = entry.get("source", "inconnue")

    missing = REQUIRED_KEYS - entry.keys()
    if missing:
        logger.warning(f"[NORMALIZE] Entrée rejetée (source={source}) : clés manquantes {sorted(missing)}")
        return False

    price = entry["price_usd"]
    if not isinstance(price, (int, float)) or isinstance(price, bool):
        logger.warning(f"[NORMALIZE] Entrée rejetée (source={source}) : price_usd n'est pas un nombre ({price!r})")
        return False
    if not (MIN_PRICE_USD <= price <= MAX_PRICE_USD):
        logger.warning(f"[NORMALIZE] Entrée rejetée (source={source}) : price_usd hors bornes ({price})")
        return False

    for field in ("timestamp", "collected_at"):
        value = entry[field]
        try:
            datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            logger.warning(f"[NORMALIZE] Entrée rejetée (source={source}) : {field} invalide ({value!r})")
            return False

    return True


def _to_strict_iso_z(value: str) -> str:
    """Convertit une date ISO 8601 quelconque (offset +00:00, avec/sans µs) en UTC suffixé "Z"."""
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def homogenize(entry: dict) -> dict:
    """Homogénéise une entrée valide vers un format de sortie strict et stable.

    Deux normalisations : le prix est arrondi à 2 décimales (les sources
    n'ont pas toutes la même précision, ex. l'API contre le scraping) et les
    timestamps sont réécrits en UTC explicite avec suffixe "Z" plutôt que
    "+00:00", pour garantir un format identique quelle que soit la source
    d'origine (avec ou sans microsecondes). Ne mute jamais l'entrée reçue.
    """
    return {
        **entry,
        "price_usd": round(float(entry["price_usd"]), 2),
        "timestamp": _to_strict_iso_z(entry["timestamp"]),
        "collected_at": _to_strict_iso_z(entry["collected_at"]),
    }


def merge_and_clean(raw_results: list[dict], logger) -> list[dict]:
    """Filtre les entrées corrompues, homogénéise le reste et trie par source.

    Le tri alphabétique par source garantit une sortie stable d'une
    exécution à l'autre, indépendamment de l'ordre (non déterministe côté
    réseau) dans lequel les collectors ont répondu.
    """
    valid_entries = [entry for entry in raw_results if is_valid_entry(entry, logger)]
    cleaned = [homogenize(entry) for entry in valid_entries]
    cleaned.sort(key=lambda entry: entry["source"])

    n_total = len(raw_results)
    n_valides = len(cleaned)
    n_rejetees = n_total - n_valides
    logger.info(f"[NORMALIZE] {n_valides}/{n_total} entrées retenues après nettoyage ({n_rejetees} rejetées)")

    return cleaned


def run() -> list[dict]:
    """Point d'entrée de l'agrégation : collecte les 5 sources et retourne le jeu de données fusionné."""
    raw_results = collect_all(logger)
    final_results = merge_and_clean(raw_results, logger)

    for entry in final_results:
        logger.info(f"[NORMALIZE] Résultat final : {entry['source']}={entry['price_usd']}$")

    return final_results


if __name__ == "__main__":
    run()
