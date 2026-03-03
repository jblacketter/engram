#!/bin/bash
set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U engram -Fc engram > "$BACKUP_DIR/engram_$TIMESTAMP.dump"
echo "Backup saved: $BACKUP_DIR/engram_$TIMESTAMP.dump"
