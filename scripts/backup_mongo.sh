#!/usr/bin/env bash
# Encrypted Mongo backup → S3 (intended for nightly cron / GitHub Action).
#
# Env:
#   MONGO_URL       — Mongo connection string (required)
#   S3_BUCKET       — destination bucket name (required)
#   S3_PREFIX       — key prefix (default: mongo-backups/)
#   GPG_RECIPIENT   — optional GPG recipient for encryption-at-rest
#   RETAIN_DAYS     — local cleanup window (default 7)
#
# Restore counterpart: scripts/restore_mongo.sh
set -euo pipefail

: "${MONGO_URL:?MONGO_URL is required}"
: "${S3_BUCKET:?S3_BUCKET is required}"

S3_PREFIX="${S3_PREFIX:-mongo-backups/}"
RETAIN_DAYS="${RETAIN_DAYS:-7}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTDIR="/tmp/mongo-backup-${STAMP}"
ARCHIVE="/tmp/mongo-backup-${STAMP}.archive.gz"

mkdir -p "$OUTDIR"

echo "▶ mongodump → $ARCHIVE"
mongodump --uri="$MONGO_URL" --archive="$ARCHIVE" --gzip

if [[ -n "${GPG_RECIPIENT:-}" ]]; then
  echo "▶ Encrypting with GPG for $GPG_RECIPIENT"
  gpg --batch --yes --trust-model always --output "${ARCHIVE}.gpg" \
      --encrypt --recipient "$GPG_RECIPIENT" "$ARCHIVE"
  rm "$ARCHIVE"
  ARCHIVE="${ARCHIVE}.gpg"
fi

S3_KEY="${S3_PREFIX}${STAMP}/$(basename "$ARCHIVE")"
echo "▶ Uploading to s3://${S3_BUCKET}/${S3_KEY}"
aws s3 cp "$ARCHIVE" "s3://${S3_BUCKET}/${S3_KEY}" \
    --storage-class STANDARD_IA \
    --server-side-encryption aws:kms

echo "▶ Cleanup local files older than ${RETAIN_DAYS}d"
find /tmp -maxdepth 1 -name "mongo-backup-*" -type d -mtime +"$RETAIN_DAYS" -exec rm -rf {} + 2>/dev/null || true
rm -rf "$OUTDIR" "$ARCHIVE" 2>/dev/null || true

echo "✓ Backup complete: s3://${S3_BUCKET}/${S3_KEY}"
