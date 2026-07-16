# BitcoinPipeline — Requêtes SQL documentées (C2)

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
