-- BitcoinPipeline — Schéma SQL de référence (C4)
-- Ce fichier centralise le DDL réel du projet pour consultation.
-- Chaque table est aussi créée automatiquement (CREATE TABLE IF NOT EXISTS)
-- par son script correspondant au premier lancement :
--   - bitcoin_prices  -> src/persist.py
--   - users           -> src/api/services/auth_service.py
--   - historical_prices_bitstamp -> scripts/seed_bitstamp.py
--   - coinbase_prices -> scripts/seed_coinbase.py
--   - bitstamp_prices_2022_sample -> scripts/seed_bitstamp_join_sample.py

-- Jeu de données final du pipeline (C3, C4)
CREATE TABLE IF NOT EXISTS bitcoin_prices (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    price_usd NUMERIC(12, 2) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL
);

-- Authentification de l'API (C5)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Échantillon de test pour le collecteur BDD Bitstamp (C2)
CREATE TABLE IF NOT EXISTS historical_prices_bitstamp (
    id SERIAL PRIMARY KEY,
    ts_unix BIGINT NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC,
    UNIQUE(ts_unix)
);

-- Historique Coinbase, pour la jointure SQL multi-sources (C3)
CREATE TABLE IF NOT EXISTS coinbase_prices (
    id SERIAL PRIMARY KEY,
    ts_unix BIGINT NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC,
    UNIQUE(ts_unix)
);

-- Échantillon Bitstamp recalé sur la période Coinbase (2022), pour permettre
-- un chevauchement temporel lors de la jointure SQL (C3, voir src/aggregate_sql.py)
CREATE TABLE IF NOT EXISTS bitstamp_prices_2022_sample (
    id SERIAL PRIMARY KEY,
    ts_unix BIGINT NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC,
    UNIQUE(ts_unix)
);
