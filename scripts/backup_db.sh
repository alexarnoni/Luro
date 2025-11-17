#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/luro_backups}"
CONTAINER_NAME="${CONTAINER_NAME:-luro-db-1}"
DB_USER="${DB_USER:-luro}"
DB_NAME="${DB_NAME:-luro}"

mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="${BACKUP_DIR}/luro_${STAMP}.sql"

echo "📦 Gerando backup do banco (${DB_NAME}) para ${BACKUP_PATH}"
docker exec "${CONTAINER_NAME}" pg_dump -U "${DB_USER}" "${DB_NAME}" > "${BACKUP_PATH}"
echo "✅ Backup concluído"
