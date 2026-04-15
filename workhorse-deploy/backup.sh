#!/usr/bin/env bash
set -euo pipefail
DATESTAMP=$(date +%Y-%m-%d)
LOGFILE="/var/log/workhorse-backup.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOGFILE"; }
mountpoint -q /mnt/usb-archive || { log "ERROR: USB not mounted"; exit 1; }
docker exec workhorse-postgres pg_dump -U workhorse_user workhorse | gzip > "/mnt/usb-archive/daily/workhorse-${DATESTAMP}.sql.gz"
rsync -a /srv/projects/*/parsed/ "/mnt/usb-archive/daily/parsed-${DATESTAMP}/"
rsync -a /srv/shared/digests/ "/mnt/usb-archive/daily/digests-${DATESTAMP}/"
find /mnt/usb-archive/daily/ -maxdepth 1 -mtime +30 -exec rm -rf {} \; 2>/dev/null || true
[ "$(date +%u)" = "7" ] && tar -czf "/mnt/usb-archive/weekly/projects-${DATESTAMP}.tar.gz" /srv/projects/
log "Backup complete"
