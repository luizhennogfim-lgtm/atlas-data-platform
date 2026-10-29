#!/bin/bash
# Runs once, on first start of the Postgres container (empty volume only).
# Creates a separate database for Airflow's own metadata; the atlas database is POSTGRES_DB.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    CREATE DATABASE airflow OWNER ${POSTGRES_USER};
SQL
