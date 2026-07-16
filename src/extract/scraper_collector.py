"""Collecteur du prix Kraken du Bitcoin via la page exchanges CoinLore.

Ce module illustre la brique C1 d'extraction de données depuis une page web
publique (sans API) : récupération du HTML brut de la page exchanges
CoinLore (table des marchés servie côté serveur, sans rendu JS nécessaire),
sauvegarde pour traçabilité, puis extraction ciblée des lignes correspondant
a l'exchange Kraken dans cette table, avec priorité aux paires indexées sur
le dollar (USDT, puis USDC). Le résultat sert de point de comparaison face a
la référence agrégée obtenue via l'API CoinGecko.
"""

import re
from datetime import UTC, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from src.utils.logger import get_logger

SCRAPING_URL = "https://www.coinlore.com/coin/bitcoin/exchanges"
RAW_HTML_PATH = Path("data/raw/scraping/coinlore_exchanges.html")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Referer": "https://www.google.com/",
}

logger = get_logger("scraper_collector")


def fetch_html(logger) -> str | None:
    """Récupère le HTML de la page exchanges CoinLore et le sauvegarde pour traçabilité.

    Gère les erreurs sans jamais lever d'exception : timeout, erreur réseau
    ou statut HTTP différent de 200. Retourne None en cas d'échec.
    """
    try:
        response = requests.get(SCRAPING_URL, headers=HEADERS, timeout=15)
    except requests.Timeout:
        logger.warning("[SCRAPING] Timeout lors de la récupération de la page CoinLore")
        return None
    except requests.RequestException as exc:
        logger.warning(f"[SCRAPING] Erreur réseau lors de la récupération de la page CoinLore : {exc}")
        return None

    if response.status_code != 200:
        logger.warning(f"[SCRAPING] Statut HTTP inattendu sur CoinLore : {response.status_code}")
        return None

    RAW_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_HTML_PATH.write_text(response.text, encoding="utf-8")

    return response.text


PRICE_PATTERN = re.compile(r"\$[\d,]+(?:\.\d+)?")
USD_LIKE_PRIORITY = ("usdt", "usdc")


def _find_pairs_table(soup: BeautifulSoup):
    """Trouve la table des marchés (celle avec des colonnes Exchange et Price).

    Retourne un triplet (table, index colonne Pair, index colonne Price),
    ou (None, None, None) si aucune table ne correspond.
    """
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if "exchange" in headers and "price" in headers:
            pair_idx = headers.index("pair") if "pair" in headers else None
            price_idx = headers.index("price")
            return table, pair_idx, price_idx
    return None, None, None


def _row_mentions_kraken(row) -> bool:
    """Vérifie si une ligne mentionne Kraken, dans son texte ou un alt d'image."""
    if "kraken" in row.get_text(" ", strip=True).lower():
        return True
    return any("kraken" in img.get("alt", "").lower() for img in row.find_all("img"))


def parse_price(html: str, logger) -> float | None:
    """Extrait le prix Kraken du BTC depuis la table des exchanges CoinLore.

    Localise la table principale des marchés (colonnes "Exchange" et
    "Price"), puis les lignes mentionnant Kraken (texte, lien ou attribut
    alt d'image). Parmi ces lignes, priorise une paire USDT puis USDC ; a
    défaut, prend la première ligne Kraken trouvée en loguant un
    avertissement. Retourne None si aucune ligne Kraken n'existe ou si le
    prix ne peut pas être extrait/converti.
    """
    soup = BeautifulSoup(html, "html.parser")

    table, pair_idx, price_idx = _find_pairs_table(soup)
    if table is None:
        logger.error("[SCRAPING] Aucune ligne Kraken trouvée dans la table CoinLore")
        return None

    rows = [row for row in table.find_all("tr") if row.find_parent("thead") is None]
    kraken_rows = [row for row in rows if _row_mentions_kraken(row)]

    if not kraken_rows:
        logger.error("[SCRAPING] Aucune ligne Kraken trouvée dans la table CoinLore")
        return None

    def pair_text_of(row) -> str:
        cells = row.find_all(["td", "th"])
        if pair_idx is not None and len(cells) > pair_idx:
            return cells[pair_idx].get_text(" ", strip=True)
        return ""

    selected_row = None
    for keyword in USD_LIKE_PRIORITY:
        for row in kraken_rows:
            if keyword in pair_text_of(row).lower():
                selected_row = row
                break
        if selected_row is not None:
            break

    if selected_row is None:
        selected_row = kraken_rows[0]
        pair = pair_text_of(selected_row) or "paire inconnue"
        logger.warning(f"[SCRAPING] Aucune paire USD/USDT/USDC pour Kraken — fallback sur {pair}")

    cells = selected_row.find_all(["td", "th"])
    price_text = None
    if len(cells) > price_idx:
        match = PRICE_PATTERN.search(cells[price_idx].get_text(" ", strip=True))
        if match:
            price_text = match.group(0)

    if not price_text:
        logger.error("[SCRAPING] Prix Kraken introuvable dans la ligne CoinLore correspondante")
        return None

    cleaned = price_text.replace("$", "").replace(",", "").replace(" ", "").strip()

    try:
        return float(cleaned)
    except ValueError:
        logger.error("[SCRAPING] Prix Kraken introuvable dans la ligne CoinLore correspondante")
        return None


def normalize_result(price: float) -> dict:
    """Transforme le prix scrapé sur Kraken dans le schéma commun du pipeline."""
    now = datetime.now(UTC).isoformat()
    return {
        "source": "scraping_kraken",
        "price_usd": price,
        "timestamp": now,
        "collected_at": now,
    }


def run() -> list[dict]:
    """Point d'entrée du collecteur : scrape et normalise le prix Kraken du BTC.

    Ne lève jamais d'exception et ne fait pas sys.exit : en cas d'échec a
    n'importe quelle étape, retourne une liste vide afin que le pipeline
    global puisse continuer avec les autres sources.
    """
    html = fetch_html(logger)

    if html is None:
        logger.error("[SCRAPING] Échec de la récupération de la page CoinLore")
        logger.info("[SCRAPING] Collecte terminée | 0 prix récupéré (échec)")
        return []

    price = parse_price(html, logger)

    if price is None:
        logger.error("[SCRAPING] Échec de l'extraction du prix Kraken depuis CoinLore")
        logger.info("[SCRAPING] Collecte terminée | 0 prix récupéré (échec)")
        return []

    result = normalize_result(price)
    logger.info("[SCRAPING] Collecte terminée | 1 prix récupéré (Kraken)")
    return [result]


if __name__ == "__main__":
    run()
