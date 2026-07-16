# BitcoinPipeline — Spécifications techniques (E1 · C1)

## 1. Contexte et objectifs

BitcoinPipeline est un pipeline de collecte automatisée du prix du Bitcoin
depuis 5 sources hétérogènes, réalisé dans le cadre du bloc de compétences 1
(C1-C5) du diplôme Développeur en Intelligence Artificielle (Simplon).

**Objectif fonctionnel :** produire un jeu de données unifié et fiable du
prix du BTC, exploitable via une API REST sécurisée.

**Objectif technique :** démontrer l'automatisation de l'extraction de
données depuis un service web (API), une page web (scraping), un fichier,
une base de données et un système big data.

## 2. Acteurs

| Rôle | Acteur |
|---|---|
| Développeur | Sulivan Moreau |
| Commanditaire | Simplon (évaluation E1) |
| Jury | Évaluateurs certification DevIA |

## 3. Objectifs fonctionnels

- Collecter le prix du BTC depuis 5 sources différentes
- Normaliser ces données en un format unique
- Stocker le résultat en base de données
- Exposer les données via une API REST authentifiée

## 4. Objectifs techniques

- Un script par source, exécutable indépendamment (`main.py --source X`)
- Gestion des erreurs et des cas d'indisponibilité de chaque source
- Script d'agrégation traçable et documenté
- Base de données conforme RGPD
- API REST protégée par JWT

## 5. Environnements et contraintes techniques

| Élément | Choix | Justification |
|---|---|---|
| Langage | Python 3.12 | Cohérence avec TomatoScan, écosystème data mature |
| Gestionnaire de paquets | uv | Rapide, lockfile reproductible |
| Base de données | PostgreSQL 16 (Docker) | Standard, gère bien les contraintes/upserts |
| API | FastAPI | Documentation OpenAPI automatique (exigence C5) |
| Auth | JWT (python-jose) + argon2 | Standard sécurisé, pas de credential en clair |
| Big data (test) | PySpark local[*] | Prouve la compétence système big data sans infra lourde |
| Versionnement | Git / GitHub | Exigence transverse |

## 6. Services externes

| Source | Type | Service |
|---|---|---|
| API REST | Service web | CoinGecko API (public, sans clé) |
| Scraping | Page web | Page HTML publique de cotation BTC |
| Fichier | CSV | Historique BTC (Kaggle, statique) |
| Base de données | SQL | Table `historical_prices` (SQLite/Postgres de test) |
| Big data | Fichier Parquet | Archive de test lue via PySpark |

## 7. Exigences de programmation

- Python 3.12, PEP8 (ruff)
- Un module par source (`src/extract/*.py`)
- Gestion des erreurs systématique (`try/except`, `sys.exit(1)` sur échec critique)
- Logging structuré (`src/utils/logger.py`)
- Aucun credential en dur (`.env`)

## 8. Accessibilité / disponibilité

- Code et documentation en français
- Dépôt Git public, README avec instructions d'installation reproductibles
- Documentation OpenAPI accessible via `/docs`

## 9. Périmètre couvert (mix de sources obligatoire)

Le script d'extraction couvre bien un mix des 5 catégories exigées par le
référentiel : service web REST, page web (scraping), fichier de données,
base de données, système big data.

## 10. Organisation du travail et planification

| Étape | Durée estimée |
|---|---|
| Cadrage + init projet | J1 |
| 5 collecteurs | J2-J4 |
| Normalisation + BDD | J5 |
| API + sécurité | J6 |
| Tests + documentation finale | J7 |

## 11. Budget

Projet pédagogique, coût nul : API publique gratuite, hébergement local
via Docker, pas de service payant.
