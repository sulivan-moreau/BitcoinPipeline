"""Routes de consultation des relevés de prix Bitcoin, protégées par JWT."""

from fastapi import APIRouter, Depends

from src.api.core.security import get_current_user
from src.api.schemas.prices import PriceItem
from src.api.services.prices_service import get_latest_prices, get_prices_by_source

router = APIRouter()


@router.get(
    "",
    response_model=list[PriceItem],
    summary="Derniers relevés de prix, toutes sources confondues",
    description=(
        "Retourne les 20 relevés de prix Bitcoin les plus récents, toutes "
        "sources confondues (api_coingecko, scraping_kraken, file_coinbase, "
        "db_bitstamp, bigdata_bitfinex). Nécessite un token JWT valide."
    ),
    responses={401: {"description": "Token JWT manquant, invalide ou expiré"}},
)
def read_latest_prices(current_user: dict = Depends(get_current_user)) -> list[PriceItem]:
    return get_latest_prices()


@router.get(
    "/{source}",
    response_model=list[PriceItem],
    summary="Derniers relevés de prix pour une source donnée",
    description=(
        "Retourne les 20 relevés de prix Bitcoin les plus récents pour une "
        "source précise (ex. api_coingecko, scraping_kraken, file_coinbase, "
        "db_bitstamp, bigdata_bitfinex). Nécessite un token JWT valide."
    ),
    responses={401: {"description": "Token JWT manquant, invalide ou expiré"}},
)
def read_prices_by_source(source: str, current_user: dict = Depends(get_current_user)) -> list[PriceItem]:
    return get_prices_by_source(source)
