# Production Launch Checklist — A1 Field Pro

> Walk this top-to-bottom before flipping `app.a1fieldpro.com` to production traffic.
> Every item must have a 🟢 OWNER + DATE before launch.

## 0 — Pre-flight (T-14 days)

- [ ] All P0/P1 backlog items closed in PRD.md
- [ ] Pen-test executed (external vendor) — report on file
- [ ] Load test executed (`k6 run loadtest.js` at 100 RPS for 10 min) — p95 < 500 ms
- [ ] Backups restore-tested successfully on a clean Atlas project

## 1 — Infrastructure

- [ ] Terraform state stored in S3 + DynamoDB lock (no local `.tfstate`)
- [ ] Production VPC: 2 AZs, private subnets for tasks, NAT GW
- [ ] ALB has WAFv2 attached (managed CRS + rate-based rule 2 000 req/5min)
- [ ] ACM certificate for `*.a1fieldpro.com` in us-east-1 + verified
- [ ] CloudFront in front of ALB (TLS-1.2+, HTTP→HTTPS redirect)
- [ ] Route53 health checks with email/Slack failover
- [ ] AWS Backup vault configured for any EBS / RDS (Atlas is separate)

## 2 — Application config

- [ ] `MONGO_URL` points to Atlas **production** cluster (M10+, sharded if >50 GB)
- [ ] `JWT_SECRET` is 64-char random (not the test secret)
- [ ] `INTEGRATION_FERNET_KEY` set as Fernet-generated key (not derived)
- [ ] `CORS_ORIGINS` = `https://app.a1fieldpro.com` (no `*`)
- [ ] `ALLOWED_HOSTS` = `api.a1fieldpro.com,app.a1fieldpro.com`
- [ ] `RATE_LIMIT_DEFAULT_RPM` tuned (start 1200, observe)
- [ ] `RATE_LIMIT_AUTH_RPM` = 20
- [ ] `RESEND_API_KEY` + verified sender domain
- [ ] `STRIPE_API_KEY` = `sk_live_…` + webhook secret configured
- [ ] `TWILIO_ACCOUNT_SID` + verified phone number
- [ ] OAuth client IDs/secrets in Secrets Manager for each connected provider
- [ ] `APP_VERSION` injected from CI (`v1.0.0`) for /api/health visibility

## 3 — Database

- [ ] Atlas IP allow-list = NAT GW EIP only (no `0.0.0.0/0`)
- [ ] Atlas user has read/write on `a1_field_pro` only — no `admin@*`
- [ ] Encryption-at-rest with customer-managed key (AWS KMS)
- [ ] Backup window set to off-peak hours
- [ ] Migrations runner verified — `scripts/migrate.sh` returns `ran=[…] skipped=N`
- [ ] All unique indexes present (verify via `db.<col>.getIndexes()`)

## 4 — Security

- [ ] Every endpoint behind `get_current_user` or explicit public flag (CSR audit)
- [ ] MFA required for all `owner`, `super_admin`, `office_manager`
- [ ] Account-lockout policy (5 failed logins → 15-min lock)
- [ ] Password reset token TTL ≤ 60 min
- [ ] CSP header verified in browser dev tools
- [ ] No secrets in logs (`grep -i "sk_live_\|whsec_\|password" /var/log/...`)
- [ ] Dependabot enabled · CodeQL on green
- [ ] `gitleaks detect` returns 0 findings
- [ ] OWASP ZAP baseline scan green
- [ ] All admin actions logged to `activity` collection
- [ ] `webhook_subscriptions.secret` redacted in API responses
- [ ] HSTS preload submission (https://hstspreload.org/) once stable for 14 days

## 5 — Observability

- [ ] CloudWatch alarms:
   - ALB 5xx > 10 over 5 min → PagerDuty
   - ECS service `RUNNING` task count < `DESIRED` for 2 min
   - Atlas connection pool exhaustion
- [ ] Sentry project configured (`SENTRY_DSN` env)
- [ ] Synthetic check: every 1 min hit `/api/health` from 3 regions
- [ ] /api/metrics scraped by Grafana Cloud or Prometheus

## 6 — Customer-facing

- [ ] Terms of Service + Privacy Policy linked from footer + signup
- [ ] Cookie consent banner (if EU traffic expected)
- [ ] Email-verify flow working in prod (`/verify?token=…`)
- [ ] Stripe Customer Portal link functional
- [ ] Status page (statuspage.io / Atlassian) configured

## 7 — Operations

- [ ] On-call rotation defined in PagerDuty
- [ ] Runbooks for top 10 alerts written (`docs/RUNBOOK.md`)
- [ ] Internal docs: how to invite a tenant manually, how to refund a charge
- [ ] DPA (Data Processing Agreement) template signed by user
- [ ] DR drill performed end-to-end (kill primary, restore from backup) in last 90 d

## 8 — Launch day

- [ ] T-2 h: feature flag “maintenance mode” banner disabled
- [ ] T-1 h: tag `v1.0.0`, push to GitHub
- [ ] T-30 min: deploy.yml manual-approve → production
- [ ] T-0:    DNS cutover (Route53 weighted record 0 → 100)
- [ ] T+5 m:  smoke test (login, create job, charge invoice, send finance link)
- [ ] T+1 h:  review CloudWatch + Sentry, confirm no error spike
- [ ] T+24 h: post-launch retro

## Sign-off

| Role | Name | Date | Initials |
|---|---|---|---|
| Engineering lead | | | |
| Security lead    | | | |
| Product owner    | | | |
| Customer success | | | |
