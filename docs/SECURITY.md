# Security Policy — A1 Field Pro

## Reporting a vulnerability
Email `security@a1fieldpro.com` with details + PoC. We acknowledge within 24 h
and aim to remediate critical issues within 7 days. Please do not file a public
GitHub issue.

## Threat model

| Asset | Threat | Mitigation |
|---|---|---|
| Customer PII (names, addresses, phone) | Cross-tenant data leak | All collections filter by `company_id`, enforced by router-level deps |
| Integration tokens (QBO, Helcim, etc.) | Token theft via DB compromise | Fernet symmetric encryption at rest (key in SecretsManager) |
| Stripe / Helcim / Twilio credentials | Compromise → financial loss | API keys never returned via REST (`redact()` masks); webhook signature verification on inbound |
| Auth credentials | Brute force / credential stuffing | bcrypt + 5-attempt lockout + MFA required for elevated roles |
| Webhooks | Spoofed inbound events | HMAC-SHA256 verification per provider |
| Outbound webhooks | Replayed / forged from app side | Recipient should verify `X-A1FP-Signature` (timestamp + HMAC) |
| Backend pods | Container escape | Non-root user (uid 10001), read-only FS where possible, no privileged mode |

## Authentication & access control

- JWT (HS256) in `httpOnly; secure; samesite=none` cookies — 7-day expiry
- All API routes require `get_current_user` unless prefixed with `/api/public/`,
  `/api/auth/`, or `/api/webhooks/in/`
- Role-based authorization at router level via `require_role()` / `require_perm()`
- 9 roles: `super_admin, owner, office_manager, dispatcher, csr, sales_rep, technician, accountant, customer`
- MFA via TOTP — required for `owner`, `super_admin`, `office_manager`
- Password policy: ≥ 8 chars, 1 letter + 1 number (enforced via Pydantic validator)
- Sessions tracked in `sessions` collection; admin can revoke individually
- Brute-force protection: 5 failed logins → 15-min lockout

## Data protection

- **At rest:** MongoDB Atlas encryption-at-rest with customer-managed KMS key
- **In transit:** TLS 1.2+ enforced via ALB security policy
- **Integration secrets:** Fernet-encrypted in Mongo; key rotation supported via `INTEGRATION_FERNET_KEY` env
- **Backups:** mongodump → S3 with SSE-KMS, optional GPG encryption layer
- **PII deletion:** `DELETE /api/customers/{id}?hard=true` purges customer + jobs + invoices (GDPR Art 17)

## Transport hardening

| Header | Value |
|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `geolocation=(self), camera=(), microphone=()` |
| `Content-Security-Policy` | default-src 'self'; tightened per env (see `nginx.conf`) |

## Rate limiting

In-memory token-bucket per IP × route prefix:
- Default: 600 req/min/IP
- Auth endpoints: 20 req/min/IP (configurable via `RATE_LIMIT_AUTH_RPM`)
- Returns `429 Retry-After` when exceeded

## Audit logging

Every privileged action writes to `activity` collection:
- `actor_id`, `actor_role`, `action`, `target_type`, `target_id`, `meta`, `created_at`, `company_id`
- 90-day retention (configurable per tenant)
- Surface in `/app/admin/activity`

## Vulnerability management

- Weekly CodeQL (`security.yml` cron Mon 06:00 UTC)
- Weekly pip-audit + yarn audit
- Weekly Trivy container scan (HIGH/CRITICAL surfaced as PR checks)
- gitleaks on every PR (secret detection)
- Annual third-party pen-test
- Dependabot auto-PRs for direct deps

## Incident response

1. **Detect** — PagerDuty alert from CloudWatch / Sentry / WAF
2. **Triage** — incident commander declares severity P0/P1/P2/P3 within 15 min
3. **Contain** — isolate affected tenant or revoke compromised credential
4. **Eradicate** — patch + rollout (`scripts/build_and_push.sh`)
5. **Recover** — verify health checks green for 30 min
6. **Postmortem** — published within 7 days for P0/P1

## Compliance posture

A1 Field Pro is built to be **SOC2-ready**. See `SOC2_CHECKLIST.md` for the
detailed control matrix. We are not yet attested.
