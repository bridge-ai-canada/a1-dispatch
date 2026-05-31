#!/usr/bin/env bash
# Quick local security audit — run before every release.
# Combines pip-audit + yarn audit + ruff (security ruleset).
set -uo pipefail

echo "═══ pip-audit ════════════════════════════════════"
pip install -q pip-audit
pip-audit -r backend/requirements.txt --strict || true

echo
echo "═══ yarn audit ═══════════════════════════════════"
(cd frontend && yarn npm audit --severity high || true)

echo
echo "═══ ruff (security ruleset S) ════════════════════"
pip install -q ruff
ruff check backend --select S --output-format=concise || true

echo
echo "═══ Secret scan (gitleaks) ═══════════════════════"
if command -v gitleaks >/dev/null; then
  gitleaks detect --source . --no-banner --report-format=table || true
else
  echo "  install gitleaks → https://github.com/gitleaks/gitleaks"
fi

echo
echo "Done. Review HIGH/CRITICAL findings before tagging release."
