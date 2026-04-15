#!/usr/bin/env bash
DISK=$(df / | awk 'NR==2{print $5}' | tr -d '%')
RAM=$(free -m | awk 'NR==2{print $3}')
USB=$(mountpoint -q /mnt/usb-archive && echo true || echo false)
DB=$(docker exec workhorse-postgres pg_isready -U workhorse_user >/dev/null 2>&1 && echo true || echo false)
LAST=$(find /mnt/usb-archive/daily/ -name "workhorse-*.sql.gz" -printf '%T@\n' 2>/dev/null | sort -n | tail -1)
AGE=$( [ -n "$LAST" ] && echo $(( ($(date +%s) - ${LAST%.*}) / 3600 )) || echo 999 )
printf '{"disk_used_pct":%s,"usb_mounted":%s,"ram_used_mb":%s,"db_reachable":%s,"backup_age_hours":%s,"checked_at":"%s"}\n' "$DISK" "$USB" "$RAM" "$DB" "$AGE" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
