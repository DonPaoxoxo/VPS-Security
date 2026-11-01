#!/usr/bin/env bash
# Server Security Center — PostgreSQL backup with optional encryption and
# off-server copy. Run from a cron job on the central hub VPS.
#
# Usage:
#   BACKUP_DIR=/var/backups/ssc GPG_RECIPIENT=you@yourdomain.com \
#   REMOTE_DEST=user@offsite-host:/backups/ssc \
#     bash backup.sh
#
# GPG_RECIPIENT and REMOTE_DEST are both optional:
#   - Without GPG_RECIPIENT, the dump is kept unencrypted locally (fine if
#     BACKUP_DIR is already on encrypted disk — otherwise set it).
#   - Without REMOTE_DEST, the backup stays local only, which does not
#     protect against this VPS's own disk failing. Set it to an off-server
#     destination reachable over SSH for a real backup.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../docker"

BACKUP_DIR="${BACKUP_DIR:-/var/backups/ssc}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

DUMP_FILE="$BACKUP_DIR/ssc-${TIMESTAMP}.sql.gz"

echo "==> Dumping database"
# shellcheck disable=SC1091
set -a; source .env; set +a
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-ssc}" "${POSTGRES_DB:-ssc}" | gzip > "$DUMP_FILE"
echo "    Wrote $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

FINAL_FILE="$DUMP_FILE"
if [[ -n "${GPG_RECIPIENT:-}" ]]; then
  echo "==> Encrypting for $GPG_RECIPIENT"
  gpg --yes --trust-model always --encrypt --recipient "$GPG_RECIPIENT" --output "${DUMP_FILE}.gpg" "$DUMP_FILE"
  rm -f "$DUMP_FILE"
  FINAL_FILE="${DUMP_FILE}.gpg"
fi

if [[ -n "${REMOTE_DEST:-}" ]]; then
  echo "==> Copying off-server to $REMOTE_DEST"
  scp -q "$FINAL_FILE" "$REMOTE_DEST/"
fi

echo "==> Pruning backups older than ${RETENTION_DAYS} days in $BACKUP_DIR"
find "$BACKUP_DIR" -name 'ssc-*.sql.gz*' -mtime "+${RETENTION_DAYS}" -delete

echo "==> Done: $FINAL_FILE"
