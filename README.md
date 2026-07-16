# BitcoinPipeline

Pipeline de collecte, agrégation et mise à disposition du prix du Bitcoin
depuis 5 sources hétérogènes, réalisé dans le cadre du bloc de compétences
E1 (C1-C5) du diplôme Développeur en Intelligence Artificielle (Simplon).

## Sources de données

Le projet compare le prix du Bitcoin sur plusieurs exchanges, chacun
collecté par une méthode d'extraction différente :

| Source | Méthode | Exchange / origine |
|---|---|---|
| API REST | requests | CoinGecko (référence agrégée) |
| Scraping | requests + BeautifulSoup | Kraken (via page marchés CoinLore) |
| Fichier | pandas | Coinbase (dataset Kaggle) |
| Base de données | SQLAlchemy / PostgreSQL | Bitstamp (dataset Kaggle, échantillon de 10 000 lignes) |
| Big data | PySpark | Bitfinex (archive Parquet, ~4.5M lignes) |

## Prérequis

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (gestionnaire de paquets)
- Docker Desktop (PostgreSQL)
- Java 17 (requis par PySpark) — `brew install openjdk@17` sur macOS

## Installation

```bash
git clone https://github.com/sulivan-moreau/BitcoinPipeline.git
cd BitcoinPipeline
cp .env.example .env
# Éditer .env : renseigner ADMIN_PASSWORD au minimum
uv sync
```

## Lancer la base de données

```bash
docker compose up -d postgres_warehouse
```

## Préparer les données sources

Télécharger et placer dans `data/raw/kaggle/` :
- `BTC-Hourly.csv` (dataset [prasoonkottarathil/btcinusd](https://www.kaggle.com/datasets/prasoonkottarathil/btcinusd), fichier Coinbase)
- `btcusd_1-min_data.csv` (dataset [mczielinski/bitcoin-historical-data](https://www.kaggle.com/datasets/mczielinski/bitcoin-historical-data), fichier Bitstamp)
- `btcusd.csv` (dataset [tencars/392-crypto-currency-pairs-at-minute-resolution](https://www.kaggle.com/datasets/tencars/392-crypto-currency-pairs-at-minute-resolution), fichier Bitfinex)

Puis lancer les scripts de préparation (one-shot) :

```bash
uv run python scripts/seed_bitstamp.py
uv run python scripts/convert_bitfinex_parquet.py
```

## Lancer le pipeline complet

```bash
uv run python -m src.persist
```

Ceci exécute successivement : les 5 collectors, la normalisation/agrégation,
puis l'insertion en base et l'export CSV final
(`data/processed/bitcoin_prices_final.csv`).

## Lancer un collector individuellement

```bash
uv run python -m src.extract.api_collector
uv run python -m src.extract.scraper_collector
uv run python -m src.extract.file_collector
uv run python -m src.extract.db_collector
uv run python -m src.extract.bigdata_collector
```

## Lancer l'API

```bash
uv run uvicorn src.api.main:app --reload --port 8000
```

Documentation interactive : http://localhost:8000/docs

Authentification :

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"VOTRE_MOT_DE_PASSE"}'
```

Puis utiliser le token retourné :

```bash
curl http://localhost:8000/prices \
  -H "Authorization: Bearer VOTRE_TOKEN"
```

## Structure du projet
BitcoinPipeline/
├── src/
│   ├── extract/       # Les 5 collecteurs (C1, C2)
│   ├── normalize.py   # Agrégation multi-sources (C3)
│   ├── persist.py     # Import en base + export CSV (C4)
│   └── api/            # API REST FastAPI + JWT (C5)
├── scripts/            # Scripts one-shot de préparation des données
├── sql/                # Schémas SQL
├── data/                # Données brutes et traitées (non versionnées)
└── docs/                # Documentation par compétence

## Documentation

- [docs/specs_techniques.md](docs/specs_techniques.md) — Cadrage du projet (C1)
- [docs/agregation.md](docs/agregation.md) — Algorithme d'agrégation (C3)
- [docs/merise_mcd.md](docs/merise_mcd.md) — Modélisation Merise (C4)
- [docs/rgpd_procedures.md](docs/rgpd_procedures.md) — Conformité RGPD (C4)
- [docs/openapi.md](docs/openapi.md) — Documentation API (C5)
