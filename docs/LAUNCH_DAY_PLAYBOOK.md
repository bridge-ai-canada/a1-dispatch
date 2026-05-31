# Launch Day Playbook — A1 Field Pro v1.0.0

> Time-boxed, sequential plan for the 24 hours surrounding the go-live cut.
> Print this out. Tick boxes as you go. Don't skip ahead.

## Roles (assign before T-24h)

| Role | Owner | Backup | Slack handle |
|---|---|---|---|
| **Incident Commander** (calls go/no-go) | | | |
| **DevOps lead** (deploys, rollbacks) | | | |
| **Backend on-call** | | | |
| **Frontend on-call** | | | |
| **Customer Success** (status updates, first responses) | | | |
| **Founder / Comms** (announces launch, replies on social) | | | |

War-room channel: `#launch-day-v1`
Bridge call: `meet.google.com/[your-link]` (keep open from T-2h to T+4h)

---

## T-7 days

- [ ] All P0/P1 backlog closed (cross-check PRD.md)
- [ ] Penetration test report on file (use Cobalt.io or HackerOne if not done)
- [ ] Load test: `k6 run loadtest.js` at 100 RPS for 10 min — p95 < 500 ms
- [ ] Backup restore drill on clean Atlas project
- [ ] All status-page subscribers email-verified
- [ ] Customer Success team trained on top-10 support flows
- [ ] First 5 paying customers given launch ETA + escalation paths

## T-48h

- [ ] Final dependency security scan green (`scripts/security_audit.sh`)
- [ ] Production secrets rotated (JWT_SECRET, INTEGRATION_FERNET_KEY)
- [ ] Production DNS TTLs lowered to 60 s (for fast rollback if needed)
- [ ] On-call rotation confirmed in PagerDuty
- [ ] CloudWatch alarms tested (intentionally trigger one, confirm
      Slack + PagerDuty fire)

## T-24h

- [ ] Maintenance-mode banner ready to enable from `/api/admin/maintenance`
- [ ] All team members confirm availability for T-0 ± 4h
- [ ] Release notes drafted (see `docs/RELEASE_NOTES_v1.0.0.md`)
- [ ] Marketing site queued: tweet, LinkedIn post, ProductHunt draft

## T-4h

- [ ] **Code freeze.** No merges to `main` until launch confirmed stable.
- [ ] Final smoke run on staging — login, create job, send finance link,
      pay invoice, verify webhook fires
- [ ] AWS cost alerting reset for launch-day spike
- [ ] Status page set to "Scheduled maintenance — launch deployment"

## T-2h

- [ ] Bridge call opens
- [ ] Incident Commander confirms all roles staffed
- [ ] DevOps tags `v1.0.0` and pushes:
      ```bash
      git tag -a v1.0.0 -m "A1 Field Pro v1.0.0 — production launch"
      git push origin v1.0.0
      ```
- [ ] GitHub Actions `deploy.yml` (production env) triggers
- [ ] Monitor `aws ecs describe-services` — wait for `services-stable`

## T-30 min

- [ ] First synthetic check against new image — `curl /api/health` →
      `version: v1.0.0` confirmed
- [ ] DNS cutover: Route53 weighted record old → new (0% → 5% canary)
- [ ] Watch CloudWatch dashboard: 5xx rate, p95 latency, db pool
- [ ] At 5 min: if no anomalies, flip to 50%, then 100%

## T-0 (GO-LIVE)

- [ ] DNS is 100% on new image
- [ ] Maintenance banner removed
- [ ] Status page set to "All systems operational"
- [ ] Customer Success sends "We're live!" email to existing customers
      with link to login + What's New
- [ ] Founder posts launch tweet / LinkedIn / Product Hunt
- [ ] Comms team monitors Twitter, Reddit r/SaaS, HackerNews mentions

## T+5 min

- [ ] Smoke test as a real user: login, create job, charge invoice,
      send finance link
- [ ] Confirm Sentry dashboard shows fewer than 5 events/min (sane noise)
- [ ] Stripe live dashboard shows new charges flowing (if any signups)
- [ ] Outbound webhooks firing — check
      `GET /api/webhooks/deliveries`

## T+1h

- [ ] CloudWatch review: no unexpected error spikes
- [ ] Sentry review: any new error groups? Investigate, don't dismiss
- [ ] First customer reports: triage / escalate via PagerDuty if P1
- [ ] Bridge call may close if green; on-call remains active for 24h

## T+24h

- [ ] Post-launch retro (30 min, full team)
- [ ] Doc all surprises in `docs/retro/v1.0.0.md`
- [ ] Send "Thanks for shipping" all-hands message
- [ ] Lower CloudWatch sensitivity back to normal
- [ ] DNS TTLs restored to 300 s
- [ ] Status page incident "Launch deployment" closed

---

## 🚨 If anything goes wrong — Rollback procedure

**Decision tree:**
1. **5xx rate > 5% for 2 min** → roll back IMMEDIATELY (no debugging in prod)
2. **p95 latency > 2× baseline** → roll back if cause not obvious in 5 min
3. **Specific customer-impacting bug** → keep up, hotfix forward
4. **Data integrity issue** → roll back, restore from backup, postmortem

**Rollback commands:**
```bash
# Revert ECS to previous task definition revision
PREV_REV=$(aws ecs describe-services --cluster a1fp-production-cluster \
  --services a1fp-production-backend --query 'services[0].deployments[1].taskDefinition' --output text)
aws ecs update-service --cluster a1fp-production-cluster \
  --service a1fp-production-backend --task-definition "$PREV_REV"

# Revert frontend the same way
aws ecs update-service --cluster a1fp-production-cluster \
  --service a1fp-production-frontend --task-definition <prev_rev>

# Watch services come back stable
aws ecs wait services-stable --cluster a1fp-production-cluster \
  --services a1fp-production-backend a1fp-production-frontend
```

ECS deployment circuit breaker (`rollback = true` in Terraform) does most
of this automatically if health checks fail within `health_check_grace_period_seconds`.

---

## Final sign-off

| Stage | Name | Date / Time | Initials |
|---|---|---|---|
| T-7 days readiness | | | |
| T-24h readiness | | | |
| T-0 go/no-go | | | |
| T+1h all clear | | | |
| T+24h all clear | | | |

🚀 **Go ship.**
