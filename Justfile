default:
    just --list

db-check:
    docker compose exec postgres_warehouse psql -U bitcoin -d bitcoin_db -c "\dt"
