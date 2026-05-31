# Operations Runbook — A1 Field Pro

## 0 · Heartbeat
- Health URL: `https://api.a1fieldpro.com/api/health`
- Readiness: `https://api.a1fieldpro.com/api/health/ready`
- Status page: https://status.a1fieldpro.com

---

## 🚨 Alert: ALB 5xx > 10 over 5 min

1. Check `/ecs/a1fp-production/backend` for `ERROR` lines:
   ```bash
   aws logs tail /ecs/a1fp-production/backend --since 10m --follow
   ```
2. Check ECS task health:
   ```bash
   aws ecs list-tasks --cluster a1fp-production-cluster --service-name a1fp-production-backend
   aws ecs describe-tasks --cluster ... --tasks <task-arn>
   ```
3. Confirm Atlas reachability — `/api/health/ready` should be `200 db:ok`.
4. **Quick mitigation:** force a redeploy of the latest known-good image.
   ```bash
   aws ecs update-service --cluster ... --service ... --force-new-deployment
   ```
5. Rollback to previous image tag if needed:
   ```bash
   aws ecs update-service --cluster ... --service ... --task-definition <prev-revision>
   ```

## 🚨 Alert: Service `RUNNING` < `DESIRED` for 2 min

Usually a task crash-loop. Inspect `stoppedReason`:
```bash
aws ecs describe-tasks --cluster ... --tasks $(aws ecs list-tasks --cluster ... --desired-status STOPPED --query 'taskArns[0]' --output text)
```
Common causes: bad env var, image pull failure, OOMKilled (raise memory).

## 🚨 Alert: Atlas connection pool exhaustion

1. Scale up backend `desired_count` temporarily (more pods = more pool slots).
2. Verify no runaway queries:
   ```js
   db.currentOp({ "secs_running": { $gte: 5 } })
   ```
3. Increase Mongo cluster tier if persistent (>70 % connection saturation).

## 🚨 Alert: Webhook delivery failure rate > 5 %

1. `GET /api/webhooks/deliveries` to see recent failures.
2. Most failures are recipient-side (network, 4xx). Notify tenant if their
   endpoint has failed > 10 deliveries in 24 h.
3. If A1FP-side error (5xx in `error` field), bounce backend pods.

---

## Common runbooks

### Promote a tenant to a higher plan

```bash
TENANT=acme-co
mongosh "$MONGO_URL" --eval "db.companies.updateOne({ name: '$TENANT' }, { \$set: { 'subscription.plan': 'enterprise' }})"
```

### Refund a Stripe charge

```bash
stripe refunds create --charge ch_xxx
# then mark invoice as refunded in app:
curl -X PATCH https://api.a1fieldpro.com/api/invoices/<id> -H "Authorization: Bearer $ADMIN_KEY" -d '{"status":"refunded"}'
```

### Rotate JWT_SECRET

⚠ This invalidates ALL active sessions. Plan a maintenance window.
```bash
NEW=$(openssl rand -hex 48)
aws secretsmanager update-secret --secret-id a1fp/prod/jwt-secret --secret-string "$NEW"
aws ecs update-service --cluster ... --service a1fp-production-backend --force-new-deployment
```

### Rotate INTEGRATION_FERNET_KEY

⚠ This invalidates stored OAuth tokens for all integrations. Tenants will
need to reconnect. Currently no key-rotation grace window — implement before
the first major customer reconnects.

### Manually run migrations

```bash
MONGO_URL=mongodb+srv://... scripts/migrate.sh
```

### Restore from backup (DR drill)

```bash
scripts/restore_mongo.sh s3://a1fp-backups/2026-05-22/dump.archive.gz.gpg mongodb+srv://restore-target
```

### Drain a tenant's data (GDPR)

```bash
curl -X DELETE https://api.a1fieldpro.com/api/super/tenants/<id>?purge=true \
  -H "Authorization: Bearer $SUPER_ADMIN_KEY"
```

---

## Useful one-liners

```bash
# Tail backend logs across all pods
aws logs tail /ecs/a1fp-production/backend --since 5m --follow

# Find recently slow requests
aws logs filter-log-events --log-group-name /ecs/a1fp-production/backend \
  --filter-pattern '{ $.latency_ms > 1000 }'

# Top tenants by job volume (last 24 h)
mongosh "$MONGO_URL" --quiet --eval '
  db.jobs.aggregate([
    {$match:{ created_at:{$gte: new Date(Date.now()-86400000).toISOString()}}},
    {$group:{ _id:"$company_id", n:{$sum:1}}}, {$sort:{n:-1}}, {$limit:10}
  ])'

# Per-route latency
curl -s https://api.a1fieldpro.com/api/metrics | jq .avg_latency_ms_by_route
```
