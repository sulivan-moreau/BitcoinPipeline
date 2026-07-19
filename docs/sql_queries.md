# BitcoinPipeline — Requêtes SQL documentées (C2)

## Note sur l'usage de SQLAlchemy

Le projet utilise SQLAlchemy **Core** (fonction `text()`, SQL brut paramétré)
plutôt que l'ORM déclaratif (classes de modèles). Choix délibéré : garder le
contrôle explicite sur les requêtes réellement exécutées, ce qui facilite la
démonstration pédagogique du SQL sous-jacent (C2) — l'ORM déclaratif
masquerait justement ce qu'on cherche ici à mettre en avant.

## Requête 1 — Dernier prix Bitstamp (db_collector.py)

**Contexte métier :** récupérer le relevé de prix le plus récent disponible
dans l'échantillon Bitstamp chargé en base.

```sql
SELECT ts_unix, close
FROM historical_prices_bitstamp
ORDER BY ts_unix DESC
LIMIT 1
```

**Explication :**
- `ORDER BY ts_unix DESC` : tri décroissant sur le timestamp Unix pour
  faire remonter l'enregistrement le plus récent en première position.
- `LIMIT 1` : évite de charger l'intégralité des 10 000 lignes en mémoire
  Python ; le filtrage est délégué au moteur SQL, plus efficace qu'un tri
  côté application.
- Pas de `WHERE` nécessaire ici : la table ne contient que des données
  déjà nettoyées (NaN supprimés au moment du seed).

**Optimisation :** `ts_unix` bénéficierait d'un index pour accélérer le tri
sur de plus gros volumes ; non nécessaire ici vu la taille de l'échantillon
(10 000 lignes), mais documenté comme axe d'amélioration.

## Requête 2 — Statistiques descriptives Bitstamp (db_collector.py)

**Contexte métier :** vérifier la cohérence de l'échantillon chargé
(détecter d'éventuelles valeurs aberrantes avant de les exposer via l'API).

```sql
SELECT COUNT(*) AS total_rows, AVG(close) AS avg_close,
       MIN(close) AS min_close, MAX(close) AS max_close
FROM historical_prices_bitstamp
```

**Explication :**
- Agrégation en une seule requête plutôt que 4 requêtes séparées (COUNT,
  AVG, MIN, MAX) : réduit les allers-retours avec la base.
- Usage informatif uniquement (log), n'impacte pas le résultat retourné
  par l'API.

## Requête 3 — Dernier prix Bitfinex via PySpark (bigdata_collector.py)

**Contexte métier :** extraire le relevé le plus récent depuis l'archive
big data (~4.5M lignes) sans charger l'intégralité du jeu de données en
mémoire driver.

```python
df.orderBy(col("time").desc()).first()
```

Équivalent SQL logique : `SELECT * FROM bitfinex ORDER BY time DESC LIMIT 1`

**Explication :**
- `orderBy(desc)` + `first()` : Spark optimise ce pattern en un seul
  partitionnement distribué plutôt qu'un `collect()` complet suivi d'un
  tri en mémoire Python, ce qui serait impossible à l'échelle (~4.5M lignes).
- Le calcul reste distribué sur les partitions Spark jusqu'à la toute
  dernière étape (`first()` ne matérialise qu'une seule ligne).

## Requête 4 — Statistiques Bitfinex via PySpark (bigdata_collector.py)

**Contexte métier :** même logique de vérification que pour Bitstamp, mais
à l'échelle big data.

```python
df.agg(avg("close"), min("close"), max("close"))
```

**Explication :**
- Agrégations Spark natives (`avg`, `min`, `max`) exécutées de façon
  distribuée sur l'ensemble du DataFrame, sans jamais rapatrier les 4.5M
  lignes côté driver Python.
- Résultat retourné en une seule ligne agrégée, collectée en mémoire de
  façon négligeable (quelques octets).

**Optimisation :** le fichier Parquet (plutôt que CSV) permet à Spark de ne
lire que les colonnes nécessaires (`close`, `time`) grâce au format colonnaire,
réduisant l'I/O disque par rapport à une lecture CSV complète.

## Requête 5 — Jointure SQL Bitstamp × Coinbase (src/aggregate_sql.py, C3)

**Contexte métier :** comparer, heure par heure, le prix de clôture Bitstamp
(base de données, C2) et Coinbase (fichier, C1) sur une même fenêtre
temporelle — une agrégation d'au moins deux sources réalisée directement en
SQL, plutôt qu'en mémoire côté application comme dans `src/normalize.py`.

```sql
WITH bitstamp_hourly AS (
    SELECT
        date_trunc('hour', to_timestamp(ts_unix)) AS hour_bucket,
        AVG(close) AS bitstamp_avg_close
    FROM bitstamp_prices_2022_sample
    GROUP BY date_trunc('hour', to_timestamp(ts_unix))
),
coinbase_hourly AS (
    SELECT
        date_trunc('hour', to_timestamp(ts_unix)) AS hour_bucket,
        close AS coinbase_close
    FROM coinbase_prices
)
SELECT
    b.hour_bucket,
    ROUND(b.bitstamp_avg_close, 2) AS bitstamp_avg_close,
    c.coinbase_close,
    ROUND(b.bitstamp_avg_close - c.coinbase_close, 2) AS price_diff_usd
FROM bitstamp_hourly b
JOIN coinbase_hourly c ON b.hour_bucket = c.hour_bucket
ORDER BY b.hour_bucket DESC
LIMIT 20
```

**Explication :**
- Deux CTE (`WITH`) préparent chaque source séparément avant la jointure :
  `bitstamp_hourly` agrège les relevés minute Bitstamp en moyenne horaire
  (`GROUP BY` + `AVG`), car Coinbase n'a qu'un relevé par heure — sans cette
  agrégation préalable, le `JOIN` produirait plusieurs lignes Bitstamp pour
  une seule ligne Coinbase.
- Le `JOIN` relie les deux CTE sur l'heure commune (`hour_bucket`) et calcule
  l'écart de prix entre les deux exchanges dans la même requête.
- **Point d'attention conservé volontairement :** Bitstamp (via
  `db_collector.py`) contient des données récentes, alors que le CSV
  Coinbase s'arrête au 2022-03-01. Sans recalage, la jointure ne
  retournerait aucune ligne (aucun chevauchement temporel). Le script
  `scripts/seed_bitstamp_join_sample.py` charge donc un échantillon Bitstamp
  distinct (`bitstamp_prices_2022_sample`), recalé sur la période Coinbase
  via le `MAX(ts_unix)` de `coinbase_prices` — ce choix est documenté plutôt
  que masqué, et n'affecte pas la table `historical_prices_bitstamp` utilisée
  par le collecteur BDD (C2).

**Optimisation :** l'agrégation horaire (`GROUP BY`) est faite côté SQL
avant la jointure plutôt qu'après, pour que le moteur ne joigne que des
lignes déjà réduites (une par heure) au lieu de multiplier chaque ligne
Coinbase par toutes les minutes Bitstamp correspondantes.
