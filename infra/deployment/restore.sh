#!/usr/bin/env bash
# Server Security Center — restore a backup produced by backup.sh.
#
# DESTRUCTIVE: this drops and recreates data in the target database. Intended
# for disaster recovery or for periodically testing that backups are actually
# restorable (do that against a scratch database, not production — see the
# --target-db flag).
#
# Usage:
#   bash restore.sh /var/backups/ssc/ssc-20260101-000000.sql.gz[.gpg] [--target-db ssc_restore_test]
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../docker"

FILE="${1:?Usage: restore.sh <backup-file> [--target-db NAME]}"
TARGET_DB="${POSTGRES_DB:-ssc}"

if [[ "${2:-}" == "--target-db" ]]; then
  TARGET_DB="${3:?--target-db requires a database name}"
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

WORK_FILE="$FILE"
if [[ "$FILE" == *.gpg ]]; then
  echo "==> Decrypting $FILE"
  WORK_FILE="${FILE%.gpg}"
  gpg --yes --output "$WORK_FILE" --decrypt "$FILE"
fi

echo "==> This will DROP and recreate database '$TARGET_DB'. Press Ctrl+C within 5s to abort."
sleep 5

echo "==> Recreating database $TARGET_DB"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-ssc}" -d postgres -c "DROP DATABASE IF EXISTS ${TARGET_DB};"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-ssc}" -d postgres -c "CREATE DATABASE ${TARGET_DB} OWNER ${POSTGRES_USER:-ssc};"

echo "==> Restoring $WORK_FILE into $TARGET_DB"
gunzip -c "$WORK_FILE" | docker compose exec -T postgres psql -U "${POSTGRES_USER:-ssc}" -d "$TARGET_DB"

if [[ "$WORK_FILE" != "$FILE" ]]; then
  rm -f "$WORK_FILE"  # remove the decrypted plaintext copy
fi

echo "==> Restore complete into database: $TARGET_DB"
if [[ "$TARGET_DB" != "${POSTGRES_DB:-ssc}" ]]; then
  echo "    (restored into a scratch database, not production — this was a restore test)"
fi
