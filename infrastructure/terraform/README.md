# A1 Field Pro — AWS Infrastructure (Terraform)

This stack provisions a production-grade AWS deployment:

```
┌─────────────────┐    443    ┌──────────────┐    8080   ┌────────────────┐
│  Route53 / ACM  │ ────────► │ Application  │ ────────► │ ECS Fargate    │
└─────────────────┘           │ Load Balancer│           │ frontend × N   │
                              │              │   /api/*  ├────────────────┤
                              │              │ ────────► │ ECS Fargate    │
                              └──────────────┘    8001   │ backend × N    │
                                                         └──────┬─────────┘
                                                                │ NAT GW
                                                                ▼
                                              MongoDB Atlas (M10+ cluster)
                                              + Stripe / Twilio / etc.
```

## Prerequisites
1. AWS account with admin or scoped IAM permissions
2. Domain on Route53 (or any DNS) + ACM certificate in `var.region`
3. MongoDB Atlas cluster + connection string stored in SecretsManager
4. ECR repos:
   ```bash
   aws ecr create-repository --repository-name a1fp-backend
   aws ecr create-repository --repository-name a1fp-frontend
   ```

## Bootstrap secrets

```bash
aws secretsmanager create-secret --name a1fp/prod/mongo-uri --secret-string "mongodb+srv://..."
aws secretsmanager create-secret --name a1fp/prod/jwt-secret --secret-string "$(openssl rand -hex 48)"
aws secretsmanager create-secret --name a1fp/prod/fernet-key --secret-string "$(python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')"
```

## Deploy

```bash
cd infrastructure/terraform
terraform init
terraform workspace new staging   # or production
terraform plan -var-file=staging.tfvars
terraform apply -var-file=staging.tfvars
```

Example `staging.tfvars`:

```hcl
environment        = "staging"
region             = "us-east-1"
backend_image      = "123.dkr.ecr.us-east-1.amazonaws.com/a1fp-backend:latest"
frontend_image     = "123.dkr.ecr.us-east-1.amazonaws.com/a1fp-frontend:latest"
domain_name        = "staging.a1fieldpro.com"
acm_certificate_arn = "arn:aws:acm:us-east-1:123:certificate/abc"

mongo_uri_secret_arn       = "arn:aws:secretsmanager:us-east-1:123:secret:a1fp/staging/mongo-uri-AbC"
jwt_secret_arn             = "arn:aws:secretsmanager:us-east-1:123:secret:a1fp/staging/jwt-secret-AbC"
integration_fernet_key_arn = "arn:aws:secretsmanager:us-east-1:123:secret:a1fp/staging/fernet-key-AbC"
```

## Output

```bash
terraform output alb_dns_name
# Then create a Route53 A-alias from api.<domain> → that ALB.
```

## Rolling update

The GitHub Actions `deploy.yml` workflow:
1. Builds + pushes new tag to ECR
2. Calls `aws ecs update-service --force-new-deployment`
3. Waits for `services-stable`
4. Hits `/api/health` to confirm

## Tearing down (sandbox only!)

```bash
terraform destroy -var-file=staging.tfvars
```
