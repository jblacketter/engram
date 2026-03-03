#!/bin/bash
set -e
BACKUP_FILE="$1"
if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: ./scripts/restore.sh <backup_file>"
  exit 1
fi
docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore -U engram -d engram --clean --if-exists < "$BACKUP_FILE"
echo "Restored from: $BACKUP_FILE"
