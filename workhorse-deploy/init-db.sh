#!/usr/bin/env bash
set -euo pipefail
CONTAINER="workhorse-postgres"
DB_USER="workhorse_user"
DB_NAME="workhorse"
DB_PASS="changeme_secure"

echo "Waiting for PostgreSQL to be ready..."
READY=false
for i in $(seq 1 20); do
  if docker exec -e PGPASSWORD="$DB_PASS" "$CONTAINER" pg_isready -U "$DB_USER" >/dev/null 2>&1; then
    READY=true
    echo "PostgreSQL is ready."
    break
  fi
  echo "Waiting for postgres... ($i/20)"
  sleep 3
done

if [ "$READY" != "true" ]; then
  echo "ERROR: PostgreSQL did not become ready after 60 seconds."
  echo "Container logs:"
  docker logs --tail 20 "$CONTAINER" 2>&1 || true
  exit 1
fi

echo "Quick connectivity test..."
docker exec -e PGPASSWORD="$DB_PASS" "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" || {
  echo "ERROR: psql cannot connect. Container logs:"
  docker logs --tail 20 "$CONTAINER" 2>&1 || true
  exit 1
}

echo "Copying schema.sql into container..."
docker cp /srv/core/schema.sql "$CONTAINER":/tmp/schema.sql

echo "Loading schema..."
docker exec -e PGPASSWORD="$DB_PASS" "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -f /tmp/schema.sql

echo ""
echo "--- Verifying tables and seed data ---"
docker exec -e PGPASSWORD="$DB_PASS" "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT slug, display_name, priority FROM projects ORDER BY priority, slug;"

echo ""
echo "Schema loaded successfully."
