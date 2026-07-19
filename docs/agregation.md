# BitcoinPipeline — Documentation du script d'agrégation (C3)

## Objectif

Décrire l'algorithme de fusion et de nettoyage qui transforme les résultats
bruts des 5 collectors (API, scraping, fichier, BDD, big data) en un jeu de
données unique, homogène et exploitable par l'API (C5).

## Dépendances

| Dépendance | Rôle |
|---|---|
| pandas | Fusion des 5 sources en un DataFrame unique, homogénéisation et tri |
| Python stdlib (datetime) | Parsing des timestamps individuels avant passage en DataFrame |
| Les 5 modules src/extract/*.py | Sources de données brutes |
| src/utils/logger.py | Traçabilité de chaque étape |

**Pourquoi pandas ?** Une fois les 5 dicts validés, il s'agit de les traiter
comme un tableau unique (une ligne par source) : arrondir une colonne,
reformater deux colonnes de dates, trier — exactement ce pour quoi pandas
est fait. La validation (`is_valid_entry`) reste en Python pur, car chaque
rejet a besoin d'un message d'erreur précis par entrée, qu'une opération
pandas vectorisée masquerait. Une agrégation multi-sources complémentaire,
côté relationnel cette fois (jointure SQL entre deux tables), est démontrée
séparément dans `src/aggregate_sql.py` (voir `docs/sql_queries.md`, Requête 5).

## Commandes

```bash
uv run python -m src.normalize
```

Ce script exécute successivement les 5 collectors, fusionne leurs résultats,
puis affiche le récapitulatif final dans les logs.

## Enchaînement logique de l'algorithme

### Étape 1 — Collecte

`collect_all()` appelle séquentiellement les 5 collectors
(`api_collector`, `scraper_collector`, `file_collector`, `db_collector`,
`bigdata_collector`). Chaque appel est isolé dans un `try/except` : si une
source échoue de façon inattendue, le pipeline continue avec les 4 autres
plutôt que de s'arrêter entièrement. C'est un choix de robustesse : la
défaillance d'une seule source (ex. Kraken bloque le scraping un jour) ne
doit jamais empêcher la collecte des 4 autres.

### Étape 2 — Validation (suppression des entrées corrompues)

`is_valid_entry()` rejette une entrée si :
- une des 4 clés obligatoires manque (`source`, `price_usd`, `timestamp`,
  `collected_at`)
- `price_usd` n'est pas un nombre compris entre 1 et 1 000 000 USD (filtre
  les valeurs aberrantes issues d'un bug de parsing en amont, par exemple
  un prix à 0 ou à plusieurs milliards)
- `timestamp` ou `collected_at` ne sont pas des chaînes ISO 8601 valides

Chaque rejet est loggé avec la source concernée et la raison précise.

### Étape 3 — Fusion et homogénéisation via pandas

Les entrées valides sont chargées dans un `DataFrame` pandas (une ligne par
source), puis homogénéisées en une passe vectorisée :
- `price_usd` arrondi à 2 décimales (`Series.round(2)`)
- `timestamp` et `collected_at` reformatés en ISO 8601 strict avec suffixe
  `Z` (UTC explicite), même si le format d'origine variait légèrement
  entre les sources (avec ou sans microsecondes)

### Étape 4 — Tri et sortie finale

Le DataFrame est trié par ordre alphabétique de `source`
(`sort_values("source")`), pour une sortie stable et reproductible d'une
exécution à l'autre, puis reconverti en liste de dicts (`to_dict("records")`)
pour le reste du pipeline (persist.py, API).

## Point d'attention : hétérogénéité temporelle des sources

Les 5 sources n'ont pas la même fraîcheur de données, et c'est volontaire :

| Source | Fraîcheur |
|---|---|
| API (CoinGecko) | Temps réel |
| Scraping (Kraken) | Temps réel |
| Fichier (Coinbase) | Dernière mise à jour du dataset Kaggle |
| BDD (Bitstamp) | Échantillon historique figé (10 000 lignes chargées une fois) |
| Big data (Bitfinex) | Archive figée à la date de collecte du dataset |

Les écarts de prix observés entre sources ne sont donc pas des anomalies :
ils reflètent la nature de chaque source (temps réel vs archive historique
figée). Ce point est assumé et documenté plutôt que masqué, car le projet
vise à démontrer 5 méthodes d'extraction différentes, pas à produire un
comparateur de prix en temps réel strict.

## Choix de nettoyage documentés

| Décision | Justification |
|---|---|
| Bornes prix [1, 1 000 000] USD | Filtre les erreurs de parsing sans introduire d'hypothèse arbitraire sur le "bon" prix du BTC |
| Timestamps ISO 8601 + suffixe Z | Élimine toute ambiguïté de fuseau horaire entre les sources |
| Un seul essai par collector, pas de retry au niveau normalize.py | Chaque collector gère déjà ses propres retries (voir leurs modules respectifs) ; normalize.py ne fait qu'orchestrer et agréger |
| Rejet silencieux mais loggé (pas de sys.exit) | Une source en échec ne doit jamais bloquer le pipeline global |
