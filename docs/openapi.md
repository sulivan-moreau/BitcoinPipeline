# BitcoinPipeline — Documentation API REST (C5)

## Vue d'ensemble

L'API expose le jeu de données de prix Bitcoin collecté depuis 5 sources
(CoinGecko, Kraken via scraping, Coinbase via fichier, Bitstamp via BDD,
Bitfinex via big data/PySpark). Spec OpenAPI complète exportée dans
`docs/openapi.json`, générée automatiquement par FastAPI et consultable
de façon interactive sur `/docs` (Swagger UI) et `/redoc`.

## Authentification

Toutes les routes `/prices/*` nécessitent un token JWT (Bearer), obtenu via
`POST /auth/login`. Le token expire après 30 minutes (configurable via
`JWT_EXPIRE_MINUTES`).

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"VOTRE_MOT_DE_PASSE"}'
```

Réponse :
```json
{"access_token": "eyJ...", "token_type": "bearer"}
```

Utilisation du token sur les routes protégées :
```bash
curl http://localhost:8000/prices \
  -H "Authorization: Bearer eyJ..."
```

## Points de terminaison

| Méthode | Route | Protégée | Description |
|---|---|---|---|
| POST | /auth/login | Non | Authentification, retourne un JWT |
| GET | /prices | Oui (JWT) | 20 relevés de prix les plus récents, toutes sources confondues |
| GET | /prices/{source} | Oui (JWT) | 20 relevés les plus récents pour une source donnée (api_coingecko, scraping_kraken, file_coinbase, db_bitstamp, bigdata_bitfinex) |
| GET | /health | Non | Vérification de disponibilité |

## Codes de réponse

| Code | Signification |
|---|---|
| 200 | Succès |
| 401 | Token JWT manquant, invalide ou expiré (ou identifiants incorrects sur /auth/login) |
| 422 | Corps de requête invalide (ex. champ manquant sur /auth/login) |
| 500 | Erreur serveur (ex. base de données inaccessible) |

## Standards respectés

- Spécification OpenAPI 3.1 générée automatiquement par FastAPI
- Documentation interactive Swagger UI (`/docs`) et ReDoc (`/redoc`)
- Chaque route documente son schéma de réponse (Pydantic), ses codes
  d'erreur possibles, et une description métier
- Spec exportée en JSON statique dans `docs/openapi.json` pour consultation
  hors ligne (le serveur n'a pas besoin de tourner pour lire cette spec)
