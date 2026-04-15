#!/usr/bin/env bash
###############################################################################
# deploy.sh — Full workhorse deployment to Ubuntu MacBook via SSH
#
# Run this from your MAIN laptop (the one with SSH access to the MacBook).
# Usage:  bash deploy.sh
#
# Prerequisites:
#   - SSH key-based access to the MacBook already configured
#   - This script and its sibling files in the same directory
###############################################################################
set -euo pipefail

MAC_IP="${MAC_IP:-192.168.1.120}"
MAC_USER="${MAC_USER:-richard}"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=15"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

ssh_cmd() { ssh $SSH_OPTS "${MAC_USER}@${MAC_IP}" "$@"; }
scp_cmd() { scp $SSH_OPTS "$@"; }

red()   { printf '\033[1;31m%s\033[0m\n' "$1"; }
green() { printf '\033[1;32m%s\033[0m\n' "$1"; }
blue()  { printf '\033[1;34m%s\033[0m\n' "$1"; }
sep()   { echo "===================================================================="; }

fail() { red "FAILED: $1"; echo "Stopping. Fix the issue above and re-run."; exit 1; }

###############################################################################
# PHASE 0 — VERIFY CURRENT STATE
###############################################################################
sep
blue "PHASE 0 — VERIFY CURRENT STATE"
sep

echo "Connecting to ${MAC_USER}@${MAC_IP}..."
ssh_cmd "echo CONNECTED" || fail "Cannot SSH into ${MAC_USER}@${MAC_IP}"
green "SSH connection OK"

echo ""
echo "--- System Info ---"
ssh_cmd "systemctl get-default && free -h && df -h /"
echo ""

DOCKER_EXISTS=$(ssh_cmd "docker --version 2>/dev/null && echo YES || echo NO")
COMPOSE_EXISTS=$(ssh_cmd "docker compose version 2>/dev/null && echo YES || echo NO")

echo "--- Docker Status ---"
echo "Docker installed: ${DOCKER_EXISTS}"
echo "Docker Compose:   ${COMPOSE_EXISTS}"
echo ""

###############################################################################
# PHASE 1 — INSTALL DOCKER + COMPOSE + TAILSCALE (if needed)
###############################################################################
sep
blue "PHASE 1 — INSTALL DOCKER + COMPOSE + TAILSCALE"
sep

if echo "$DOCKER_EXISTS" | grep -q "YES"; then
  green "Docker already installed — skipping Docker install"
else
  echo "Installing prerequisites..."
  ssh_cmd "sudo apt update && sudo apt install -y curl wget jq rsync logrotate ufw postgresql-client" \
    || fail "apt install of prerequisites"
  green "Prerequisites installed"

  echo "Installing Docker..."
  ssh_cmd "curl -fsSL https://get.docker.com | sudo sh" \
    || fail "Docker install script"
  green "Docker installed"

  echo "Configuring Docker service..."
  ssh_cmd "sudo usermod -aG docker ${MAC_USER} && sudo systemctl enable docker && sudo systemctl start docker" \
    || fail "Docker service setup"
  green "Docker service enabled and started"
fi

if echo "$COMPOSE_EXISTS" | grep -q "YES"; then
  green "Docker Compose plugin already installed — skipping"
else
  echo "Installing Docker Compose plugin..."
  ssh_cmd "sudo apt install -y docker-compose-plugin" \
    || fail "docker-compose-plugin install"
  green "Docker Compose plugin installed"
fi

# Tailscale
TAILSCALE_EXISTS=$(ssh_cmd "tailscale version 2>/dev/null && echo YES || echo NO")
if echo "$TAILSCALE_EXISTS" | grep -q "YES"; then
  green "Tailscale already installed — skipping"
else
  echo "Installing Tailscale..."
  ssh_cmd "curl -fsSL https://tailscale.com/install.sh | sudo sh" \
    || fail "Tailscale install"
  green "Tailscale installed"
fi

echo ""
echo "--- Verification ---"
ssh_cmd "docker --version && docker compose version && systemctl is-enabled docker && systemctl is-active docker" \
  || fail "Docker verification"
green "Docker + Compose verified and running"

echo ""
blue "REMINDER: You still need to run 'sudo tailscale up' on the MacBook to authenticate it."
echo ""

###############################################################################
# PHASE 2 — CREATE FOLDER STRUCTURE
###############################################################################
sep
blue "PHASE 2 — CREATE FOLDER STRUCTURE"
sep

echo "Creating /srv and /mnt/usb-archive directory trees..."
ssh_cmd "sudo mkdir -p \
  /srv/projects/sjms/{raw,parsed,reports,exports} \
  /srv/projects/mycoursematchmaker/{raw,parsed,reports,exports} \
  /srv/projects/shakespeare-is-boring/{raw,parsed,reports,exports} \
  /srv/projects/coursepulse/{raw,parsed,reports,exports} \
  /srv/projects/future-horizons/{raw,parsed,reports,exports} \
  /srv/projects/funding-watch/{raw,parsed,reports,exports} \
  /srv/projects/film-opps/{raw,parsed,reports,exports} \
  /srv/projects/career-opps/{raw,parsed,reports,exports} \
  /srv/core/n8n \
  /srv/core/postgres \
  /srv/shared/{notes,exports,digests} \
  /mnt/usb-archive/{daily,weekly,monthly} \
  && sudo chown -R ${MAC_USER}:${MAC_USER} /srv" \
  || fail "Directory structure creation"
green "Directory structure created"

echo ""
echo "--- Directory tree (top 3 levels) ---"
ssh_cmd "find /srv -maxdepth 3 -type d | sort | head -n 100"
echo ""

###############################################################################
# PHASE 3 — UPLOAD STACK FILES TO MACBOOK
###############################################################################
sep
blue "PHASE 3 — UPLOAD STACK FILES TO MACBOOK"
sep

for f in docker-compose.yml schema.sql backup.sh health-check.sh init-db.sh; do
  echo "Uploading $f..."
  scp_cmd "${SCRIPT_DIR}/${f}" "${MAC_USER}@${MAC_IP}:/tmp/${f}" \
    || fail "SCP upload of $f"
done
green "All files uploaded to /tmp/"

###############################################################################
# PHASE 4 — DEPLOY FILES ON MACBOOK
###############################################################################
sep
blue "PHASE 4 — DEPLOY FILES TO /srv/core"
sep

ssh_cmd "sudo cp /tmp/docker-compose.yml /srv/core/ \
  && sudo cp /tmp/schema.sql /srv/core/ \
  && sudo cp /tmp/backup.sh /srv/core/ \
  && sudo cp /tmp/health-check.sh /srv/core/ \
  && sudo cp /tmp/init-db.sh /srv/core/ \
  && sudo chmod +x /srv/core/*.sh \
  && sudo chown -R ${MAC_USER}:${MAC_USER} /srv/core" \
  || fail "Deploying files to /srv/core"
green "Files deployed to /srv/core"

echo ""
echo "--- /srv/core contents ---"
ssh_cmd "ls -la /srv/core/"
echo ""

###############################################################################
# PHASE 5 — START DOCKER STACK
###############################################################################
sep
blue "PHASE 5 — START DOCKER STACK"
sep

echo "Starting Docker Compose stack..."
ssh_cmd "cd /srv/core && sudo docker compose up -d" \
  || fail "docker compose up"
green "Docker Compose started"

echo "Waiting 20 seconds for containers to stabilize..."
sleep 20

echo ""
echo "--- Container Status ---"
CONTAINER_STATUS=$(ssh_cmd "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")
echo "$CONTAINER_STATUS"
echo ""

# Check both containers are Up
if echo "$CONTAINER_STATUS" | grep -q "workhorse-postgres" && echo "$CONTAINER_STATUS" | grep -q "workhorse-n8n"; then
  if echo "$CONTAINER_STATUS" | grep "workhorse-postgres" | grep -qi "up" && \
     echo "$CONTAINER_STATUS" | grep "workhorse-n8n" | grep -qi "up"; then
    green "Both containers are UP"
  else
    red "One or both containers are not in 'Up' state"
    echo "--- Postgres logs ---"
    ssh_cmd "docker logs --tail 30 workhorse-postgres 2>&1" || true
    echo "--- n8n logs ---"
    ssh_cmd "docker logs --tail 30 workhorse-n8n 2>&1" || true
    fail "Containers not healthy"
  fi
else
  red "Expected containers not found"
  ssh_cmd "docker ps -a --format 'table {{.Names}}\t{{.Status}}'" || true
  echo "--- Postgres logs ---"
  ssh_cmd "docker logs --tail 30 workhorse-postgres 2>&1" || true
  echo "--- n8n logs ---"
  ssh_cmd "docker logs --tail 30 workhorse-n8n 2>&1" || true
  fail "Expected containers missing"
fi

###############################################################################
# PHASE 6 — INITIALISE DATABASE
###############################################################################
sep
blue "PHASE 6 — INITIALISE DATABASE"
sep

echo "Running init-db.sh..."
ssh_cmd "cd /srv/core && sudo bash ./init-db.sh" \
  || fail "Database initialisation (init-db.sh)"
green "Database initialised"

echo ""
echo "--- Tables ---"
ssh_cmd "docker exec workhorse-postgres psql -U postgres -d workhorse -c '\dt'" \
  || fail "Listing tables"

echo ""
echo "--- Projects ---"
ssh_cmd "docker exec workhorse-postgres psql -U postgres -d workhorse -c 'SELECT slug, priority FROM projects ORDER BY priority, slug;'" \
  || fail "Querying projects"

###############################################################################
# PHASE 7 — FINAL HEALTH CHECK
###############################################################################
sep
blue "PHASE 7 — FINAL HEALTH CHECK"
sep

echo "--- Health Check ---"
ssh_cmd "bash /srv/core/health-check.sh" || true

echo ""
echo "--- Resources ---"
ssh_cmd "free -h && df -h /"

echo ""
sep
green "DEPLOYMENT COMPLETE"
sep
echo ""
echo "Access points:"
echo "  n8n UI:       http://${MAC_IP}:5678"
echo "  PostgreSQL:   ${MAC_IP}:5433  db=workhorse  user=workhorse_user"
echo ""
red "ACTION REQUIRED:"
echo "  1. Change passwords in /srv/core/docker-compose.yml on the MacBook"
echo "     - POSTGRES_PASSWORD (currently: changeme_secure)"
echo "     - DB_POSTGRESDB_PASSWORD (must match POSTGRES_PASSWORD)"
echo "     - N8N_BASIC_AUTH_PASSWORD (currently: changeme_n8n)"
echo "     Then restart: cd /srv/core && sudo docker compose down && sudo docker compose up -d"
echo ""
echo "  2. Run 'sudo tailscale up' on the MacBook to authenticate Tailscale"
echo ""
echo "  3. Next step: import or generate n8n workflows"
echo ""
