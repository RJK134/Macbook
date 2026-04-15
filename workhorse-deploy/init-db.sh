#!/usr/bin/env bash
set -euo pipefail
CONTAINER="workhorse-postgres"
for i in $(seq 1 20); do
  docker exec $CONTAINER pg_isready -U postgres >/dev/null 2>&1 && break
  echo "Waiting for postgres... ($i/20)"
  sleep 3
done

docker exec $CONTAINER psql -U postgres -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='workhorse_user') THEN CREATE USER workhorse_user WITH PASSWORD 'changeme_secure'; END IF; END \$\$;"
docker exec $CONTAINER psql -U postgres -c "SELECT 1 FROM pg_database WHERE datname='workhorse'" | grep -q 1 || docker exec $CONTAINER psql -U postgres -c "CREATE DATABASE workhorse OWNER postgres ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;"
docker exec $CONTAINER psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE workhorse TO workhorse_user;"
docker exec -i $CONTAINER psql -U postgres -d workhorse < /srv/core/schema.sql

docker exec $CONTAINER psql -U postgres -d workhorse -c "SELECT slug, display_name, priority FROM projects ORDER BY priority, slug;"
