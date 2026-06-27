#!/usr/bin/env bash
# Snapshot Elasticsearch + tar named Docker volumes for chromadata/briefingsdata/redisdata.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups/$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$BACKUP_DIR"

echo "==> Backup to $BACKUP_DIR"

# 1. Elasticsearch snapshot via API
echo "--> ES snapshot..."
curl -s -X PUT "http://localhost:9200/_snapshot/backup_repo" \
  -H 'Content-Type: application/json' \
  -d '{"type":"fs","settings":{"location":"/tmp/es-snapshot"}}' | grep -q acknowledged \
  || { echo "WARN: could not register snapshot repo (ES may be down)"; }

curl -s -X PUT "http://localhost:9200/_snapshot/backup_repo/snap_$(date +%s)?wait_for_completion=true" \
  > "$BACKUP_DIR/es-snapshot.json" 2>&1 && echo "    ES snapshot saved" \
  || echo "    WARN: ES snapshot failed — platform may be offline"

# 2. Docker named volumes
for vol in chromadata briefingsdata redisdata; do
  full_vol="threat_int_mgmt_${vol}"
  echo "--> Volume $full_vol..."
  docker run --rm \
    -v "${full_vol}:/data:ro" \
    -v "$(realpath "$BACKUP_DIR"):/backup" \
    busybox tar czf "/backup/${vol}.tar.gz" -C /data . \
    && echo "    $vol → $BACKUP_DIR/${vol}.tar.gz" \
    || echo "    WARN: $vol backup failed (volume may not exist)"
done

echo "==> Done: $BACKUP_DIR"
