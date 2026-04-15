#!/usr/bin/env bash
set -euo pipefail
CONTAINER="workhorse-postgres"
DB_USER="workhorse_user"
DB_NAME="workhorse"

echo "Waiting for PostgreSQL to be ready..."
for i in $(seq 1 20); do
  docker exec $CONTAINER pg_isready -U "$DB_USER" >/dev/null 2>&1 && break
  echo "Waiting for postgres... ($i/20)"
  sleep 3
done

# Database and user are already created by docker-compose env vars
# (POSTGRES_DB=workhorse, POSTGRES_USER=workhorse_user)
# Just load the schema into the existing database.

echo "Loading schema..."
docker exec -i $CONTAINER psql -U "$DB_USER" -d "$DB_NAME" < /srv/core/schema.sql

echo ""
echo "--- Verifying tables and seed data ---"
docker exec $CONTAINER psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT slug, display_name, priority FROM projects ORDER BY priority, slug;"
