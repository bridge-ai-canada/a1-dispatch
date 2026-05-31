# Deployment Guide — A1 Field Pro

## Architecture at a glance

| Tier | Tech | Scaling |
|---|---|---|
| Frontend | React 19 build served by nginx (port 8080 in container) | Stateless, ECS Fargate 2-N tasks |
| Backend  | FastAPI + uvicorn (port 8001) | Stateless, ECS Fargate 2-8 tasks (autoscaling on CPU 65 %) |
| Database | MongoDB Atlas (M10+, sharded for >50 GB) | Managed |
| Object storage | S3 (logos, signed PDFs) | Managed |
| Edge | CloudFront → ALB | Managed |
| Secrets | AWS Secrets Manager (MONGO_URL, JWT_SECRET, INTEGRATION_FERNET_KEY, provider OAuth clients) | Managed |
| Background jobs | APScheduler in-process (sync engine) | Per-task instance |
| Cache | None today; Redis (ElastiCache) recommended at >5 k DAU |

## Environments

| Env | DNS | Branch | Purpose |
|---|---|---|---|
| `dev`        | `dev.a1fieldpro.com`      | `develop`   | continuous |
| `staging`    | `staging.a1fieldpro.com`  | `main`      | smoke / UAT |
| `production` | `app.a1fieldpro.com`      | tags `v*`   | live customers |

## Local first

```bash
cp backend/.env.example backend/.env
docker compose up --build
# Frontend: http://localhost:3000
# Backend : http://localhost:8001/api/health
```

## AWS bring-up (one-time)

1. **ECR repos** — `aws ecr create-repository --repository-name a1fp-{backend,frontend}`
2. **Secrets** —
   ```bash
   aws secretsmanager create-secret --name a1fp/prod/mongo-uri --secret-string "mongodb+srv://..."
   aws secretsmanager create-secret --name a1fp/prod/jwt-secret  --secret-string "$(openssl rand -hex 48)"
   aws secretsmanager create-secret --name a1fp/prod/fernet-key  --secret-string "$(python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')"
   ```
3. **OIDC role for GitHub Actions** — see Terraform `github_oidc.tf` (TODO add).
4. **Terraform** — `cd infrastructure/terraform && terraform init && terraform apply -var-file=prod.tfvars`
5. **DNS** — Route53 A-alias `app.a1fieldpro.com` → ALB DNS output.
6. **First deploy** — `scripts/build_and_push.sh v0.1.0`

## CI/CD flow

```
push → main      ─► CI (lint+test+build)  ─► deploy.yml → staging   (auto)
git tag v1.2.3   ─► CI                     ─► deploy.yml → production (manual approval)
schedule nightly ─► backup.yml             ─► s3://a1fp-backups
schedule weekly  ─► security.yml           ─► CodeQL + Trivy + pip-audit
```

## Rolling update

ECS service `deployment_circuit_breaker = enable + rollback = true` — failed health checks within `health_check_grace_period_seconds` (60s) auto-rollback. Manual:

```bash
aws ecs update-service --cluster <c> --service <s> --force-new-deployment
aws ecs wait services-stable --cluster <c> --services <s>
```

## Database migrations

Migrations live in `backend/migrations/NNNN_*.py`. Runner is idempotent and runs on FastAPI startup, so a normal deploy applies them automatically. To run out-of-band:

```bash
scripts/migrate.sh   # uses env MONGO_URL from current shell
```

## Logs & metrics

- CloudWatch log groups: `/ecs/a1fp-{env}/{backend,frontend}` — 30-day retention
- Container Insights: enabled on ECS cluster (CPU, mem, network per task)
- App metrics: `GET /api/metrics` (JSON), `GET /api/metrics/prom` (Prometheus exposition)
- Tracing (optional): set `SENTRY_DSN` env var; FastAPI middleware will attach request IDs

## Backup & DR

- `scripts/backup_mongo.sh` runs nightly via `.github/workflows/backup.yml`
- Archives are KMS-encrypted at rest in S3 Standard-IA
- Retention: 30 days hot, lifecycle-rule to Glacier at 30d, expire at 365d
- Restore: `scripts/restore_mongo.sh s3://a1fp-backups/path mongodb+srv://target`
- RTO target: 1 h · RPO target: 24 h

## Cost ballpark (us-east-1, low-traffic month)

- ECS Fargate 4× tasks @ 0.5 vCPU/1 GB: **~$40**
- ALB: **~$20**
- NAT GW: **~$33**
- Atlas M10: **~$60**
- S3 + CloudWatch: **~$5**
- CloudFront: pay-per-use (~$5 at 100 GB egress)
- **Total at MVP scale: ~$165/mo**
