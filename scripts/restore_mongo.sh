#!/usr/bin/env bash
# Restore a Mongo backup from S3.
#
# Usage: scripts/restore_mongo.sh s3://bucket/key/backup.archive.gz[.gpg] mongodb+srv://...

set -euo pipefail

S3_URI="${1:?usage: $0 s3://bucket/key target_mongo_uri}"
TARGET_URI="${2:?usage: $0 s3://bucket/key target_mongo_uri}"

LOCAL="/tmp/restore-$(date +%s)-$(basename "$S3_URI")"
echo "▶ Downloading $S3_URI"
aws s3 cp "$S3_URI" "$LOCAL"

if [[ "$LOCAL" == *.gpg ]]; then
  echo "▶ Decrypting"
  gpg --batch --yes --output "${LOCAL%.gpg}" --decrypt "$LOCAL"
  rm "$LOCAL"
  LOCAL="${LOCAL%.gpg}"
fi

read -rp "⚠ This will RESTORE into $TARGET_URI — type 'YES' to continue: " ACK
[[ "$ACK" == "YES" ]] || { echo "aborted"; exit 1; }

echo "▶ mongorestore"
mongorestore --uri="$TARGET_URI" --archive="$LOCAL" --gzip --drop

rm -f "$LOCAL"
echo "✓ Restore complete"
