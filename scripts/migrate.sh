#!/usr/bin/env bash
# Apply pending Mongo migrations against the configured cluster.
# Safe to run during a rolling deploy — migrations are idempotent.
set -euo pipefail

cd "$(dirname "$0")/../backend"
python -m migrations.runner
