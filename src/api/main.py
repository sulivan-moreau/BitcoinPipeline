"""API REST BitcoinPipeline (C5) : expose le jeu de données agrégé, protégée par JWT.

Cette API expose le résultat du pipeline de collecte multi-sources (API
CoinGecko, scraping Kraken, fichier Coinbase, base de données Bitstamp, big
data Bitfinex via PySpark), persisté dans la table bitcoin_prices. L'accès
en lecture aux relevés de prix nécessite un token JWT obtenu via
POST /auth/login.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.auth import router as auth_router
from src.api.routes.prices import router as prices_router
from src.api.services.auth_service import create_default_admin, ensure_users_table
from src.utils.logger import get_logger

logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prépare la table users et crée le compte administrateur par défaut au démarrage.

    Un échec ici (ex. base de données pas encore disponible) ne doit pas
    empêcher l'API de démarrer : l'erreur est seulement loguée en warning.
    """
    try:
        ensure_users_table()
        create_default_admin()
    except Exception as exc:
        logger.warning(f"[API] Échec de la création du compte admin par défaut : {exc}")
    yield


app = FastAPI(
    title="BitcoinPipeline API",
    description=(
        "API REST exposant le prix du Bitcoin collecté depuis 5 sources "
        "hétérogènes : API CoinGecko, scraping (page CoinLore, exchange "
        "Kraken), fichier historique Coinbase, base de données Bitstamp et "
        "archive big data Bitfinex traitée via PySpark. L'accès en lecture "
        "aux relevés de prix est protégé par authentification JWT."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(prices_router, prefix="/prices", tags=["prices"])


@app.get("/health", summary="Vérification de disponibilité de l'API")
def health() -> dict:
    """Endpoint non protégé pour vérifier que l'API répond."""
    return {"status": "ok", "service": "BitcoinPipeline API"}
