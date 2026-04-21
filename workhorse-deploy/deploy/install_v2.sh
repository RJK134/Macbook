#!/usr/bin/env bash
###############################################################################
# install_v2.sh — Workhorse v2 installer
#
# Run on the MacBook (Ubuntu) once the repo is pulled to ~/macbook-deploy.
# Idempotent: re-running upgrades the venv, refreshes cron, applies schema.
###############################################################################
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$HOME/macbook-deploy}"
SCRAPERS_SRC="$REPO_ROOT/workhorse-deploy/scrapers"
SCRAPERS_DEST="/srv/scrapers"
USB_ROOT="${USB_ROOT:-/mnt/usb-archive}"
ENV_FILE="$SCRAPERS_DEST/.env"

red()   { printf '\033[1;31m%s\033[0m\n' "$1"; }
green() { printf '\033[1;32m%s\033[0m\n' "$1"; }
blue()  { printf '\033[1;34m%s\033[0m\n' "$1"; }
sep()   { echo "===================================================================="; }
fail()  { red "FAILED: $1"; exit 1; }

sep
blue "Workhorse v2 install"
sep

# 1. Install Python toolchain
blue "[1/8] Ensuring Python 3.11 + venv tooling"
if ! command -v python3.11 >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3.11 python3.11-venv python3-pip
fi
green "Python OK"

# 2. Sync scraper code to /srv/scrapers
blue "[2/8] Syncing scrapers to $SCRAPERS_DEST"
sudo mkdir -p "$SCRAPERS_DEST"
sudo rsync -a --delete --exclude '.venv' --exclude '__pycache__' --exclude '.env' \
    "$SCRAPERS_SRC/" "$SCRAPERS_DEST/"
sudo chown -R "$USER:$USER" "$SCRAPERS_DEST"
green "Code synced"

# 3. Create / update venv + install requirements
blue "[3/8] Creating venv + installing requirements"
if [ ! -d "$SCRAPERS_DEST/.venv" ]; then
  python3.11 -m venv "$SCRAPERS_DEST/.venv"
fi
"$SCRAPERS_DEST/.venv/bin/pip" install --upgrade pip
"$SCRAPERS_DEST/.venv/bin/pip" install -r "$SCRAPERS_DEST/requirements.txt"
green "Venv ready"

# 4. Make sure .env exists (create from example if missing)
blue "[4/8] Ensuring .env exists"
if [ ! -f "$ENV_FILE" ]; then
  cp "$SCRAPERS_DEST/.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  red "  Created $ENV_FILE from template — EDIT IT to set"
  red "  PERPLEXITY_API_KEY, GMAIL_APP_PASSWORD, DB_PASSWORD before next cron run"
else
  green ".env present (not overwritten)"
fi

# 5. USB layout
blue "[5/8] Creating USB folder structure"
mkdir -p "$USB_ROOT"/raw/{courses,jobs,funding,film,gmail,job_trends,financial}
mkdir -p "$USB_ROOT"/databases
mkdir -p "$USB_ROOT"/reports
mkdir -p "$USB_ROOT"/backups/{daily,weekly,monthly}
mkdir -p "$USB_ROOT"/logs/{scrapers,reports}
green "USB layout ready"

# 6. Apply schema-v2 to Postgres
blue "[6/8] Applying schema-v2.sql to Postgres"
DB_PASS=$(grep '^DB_PASSWORD=' "$ENV_FILE" | cut -d'=' -f2- | tr -d '"')
docker cp "$REPO_ROOT/workhorse-deploy/schema-v2.sql" workhorse-postgres:/tmp/schema-v2.sql
docker exec -e PGPASSWORD="$DB_PASS" workhorse-postgres \
    psql -U workhorse_user -d workhorse -f /tmp/schema-v2.sql \
    || fail "schema-v2 apply failed"
green "Schema v2 applied"

# 7. Install cron
blue "[7/8] Installing cron schedule"
CRONTAB_FILE="$REPO_ROOT/workhorse-deploy/deploy/crontab.txt"
TMP_CRON=$(mktemp)
crontab -l 2>/dev/null | grep -v 'workhorse-v2' > "$TMP_CRON" || true
echo "" >> "$TMP_CRON"
echo "# workhorse-v2 — auto-installed by install_v2.sh" >> "$TMP_CRON"
cat "$CRONTAB_FILE" >> "$TMP_CRON"
crontab "$TMP_CRON"
rm "$TMP_CRON"
green "Cron installed (run 'crontab -l' to view)"

# 8. Build & start FastAPI course server
blue "[8/8] Building course-api Docker container"
cd "$REPO_ROOT/workhorse-deploy"
sudo docker compose build course-api || fail "course-api build"
sudo docker compose up -d course-api
green "course-api running on http://0.0.0.0:8000"

sep
green "Workhorse v2 install complete"
sep
echo
echo "Next steps:"
echo "  1. Edit $ENV_FILE — set PERPLEXITY_API_KEY and GMAIL_APP_PASSWORD"
echo "  2. Test a scraper: $SCRAPERS_DEST/.venv/bin/python -m scrapers.courses.orchestrator --dry-run"
echo "  3. Test the digest: $SCRAPERS_DEST/.venv/bin/python -m scrapers.reports.master_digest --dry-run"
echo "  4. Course API: curl http://localhost:8000/health"
echo "  5. View cron: crontab -l"
