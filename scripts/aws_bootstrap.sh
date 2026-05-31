#!/usr/bin/env bash
# Bootstrap AWS resources for A1 Field Pro production deployment.
#
# Prerequisites:
#   - AWS CLI v2 installed + authenticated as an admin/poweruser
#   - `terraform` >= 1.6
#   - `openssl` and `python3` (for secret generation)
#   - You're running this from the project root (/app)
#
# Usage:
#   AWS_REGION=us-east-1 ENVIRONMENT=production ./scripts/aws_bootstrap.sh
#
# What it does (idempotent):
#   1. Creates ECR repos for backend + frontend
#   2. Generates + stores 3 secrets in Secrets Manager
#   3. Creates Terraform S3 backend bucket + DynamoDB lock table
#   4. Creates GitHub OIDC provider + deploy role (for .github/workflows/deploy.yml)
#   5. Prints the values you need to paste into GitHub repo secrets/variables
#
# Total runtime: ~3 min. Total AWS cost: ~$2/month (S3 + DDB + Secrets).

set -euo pipefail

ENVIRONMENT="${ENVIRONMENT:-production}"
AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT="a1fp"
GH_ORG="${GH_ORG:?Set GH_ORG=your-github-org}"
GH_REPO="${GH_REPO:?Set GH_REPO=your-repo-name}"

echo "═══════════════════════════════════════════════════════════════"
echo " A1 Field Pro — AWS Bootstrap"
echo "   Environment: $ENVIRONMENT"
echo "   Region:      $AWS_REGION"
echo "   GitHub:      $GH_ORG/$GH_REPO"
echo "═══════════════════════════════════════════════════════════════"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
echo "AWS account: $ACCOUNT_ID"
read -rp "Continue? (yes/no) " ACK
[[ "$ACK" == "yes" ]] || { echo "aborted."; exit 1; }

# ─────────────────────────────────────────────────────────────────
# 1) ECR repositories
# ─────────────────────────────────────────────────────────────────
echo ""
echo "▶ [1/5] Creating ECR repositories"
for repo in backend frontend; do
  REPO="${PROJECT}-${repo}"
  aws ecr describe-repositories --repository-names "$REPO" --region "$AWS_REGION" >/dev/null 2>&1 \
    || aws ecr create-repository --repository-name "$REPO" \
        --image-scanning-configuration scanOnPush=true \
        --image-tag-mutability MUTABLE \
        --region "$AWS_REGION" >/dev/null
  echo "  ✓ ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO}"
done

# ─────────────────────────────────────────────────────────────────
# 2) Secrets in Secrets Manager
# ─────────────────────────────────────────────────────────────────
echo ""
echo "▶ [2/5] Creating Secrets Manager entries"

create_secret() {
  local NAME="$1"
  local VALUE="$2"
  if aws secretsmanager describe-secret --secret-id "$NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
    echo "  ⚠ ${NAME} already exists — skipping (use rotation to update)"
  else
    aws secretsmanager create-secret --name "$NAME" --secret-string "$VALUE" \
      --region "$AWS_REGION" --description "A1 Field Pro $ENVIRONMENT" >/dev/null
    echo "  ✓ ${NAME}"
  fi
}

read -rsp "Paste your MongoDB Atlas connection string (mongodb+srv://...): " MONGO_URL; echo
JWT_SECRET="$(openssl rand -hex 48)"
FERNET_KEY="$(python3 -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')"

create_secret "${PROJECT}/${ENVIRONMENT}/mongo-uri"   "$MONGO_URL"
create_secret "${PROJECT}/${ENVIRONMENT}/jwt-secret"  "$JWT_SECRET"
create_secret "${PROJECT}/${ENVIRONMENT}/fernet-key" "$FERNET_KEY"

# ─────────────────────────────────────────────────────────────────
# 3) Terraform state backend
# ─────────────────────────────────────────────────────────────────
echo ""
echo "▶ [3/5] Creating Terraform state backend"
TF_BUCKET="${PROJECT}-tfstate-${ACCOUNT_ID}"
TF_TABLE="${PROJECT}-tfstate-lock"

aws s3api head-bucket --bucket "$TF_BUCKET" --region "$AWS_REGION" 2>/dev/null \
  || aws s3 mb "s3://${TF_BUCKET}" --region "$AWS_REGION"
aws s3api put-bucket-versioning --bucket "$TF_BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$TF_BUCKET" \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms"}}]}'
aws s3api put-public-access-block --bucket "$TF_BUCKET" \
  --public-access-block-configuration 'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'
echo "  ✓ s3://${TF_BUCKET}"

aws dynamodb describe-table --table-name "$TF_TABLE" --region "$AWS_REGION" >/dev/null 2>&1 \
  || aws dynamodb create-table --table-name "$TF_TABLE" \
      --attribute-definitions AttributeName=LockID,AttributeType=S \
      --key-schema AttributeName=LockID,KeyType=HASH \
      --billing-mode PAY_PER_REQUEST --region "$AWS_REGION" >/dev/null
echo "  ✓ dynamodb://${TF_TABLE}"

# ─────────────────────────────────────────────────────────────────
# 4) GitHub OIDC provider + deploy role
# ─────────────────────────────────────────────────────────────────
echo ""
echo "▶ [4/5] Setting up GitHub Actions OIDC trust"
OIDC_PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_PROVIDER_ARN" >/dev/null 2>&1 \
  || aws iam create-open-id-connect-provider \
      --url https://token.actions.githubusercontent.com \
      --client-id-list sts.amazonaws.com \
      --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 >/dev/null
echo "  ✓ OIDC provider"

DEPLOY_ROLE="${PROJECT}-github-deploy"
ASSUME_DOC=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Federated": "${OIDC_PROVIDER_ARN}"},
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com"},
      "StringLike":   {"token.actions.githubusercontent.com:sub": "repo:${GH_ORG}/${GH_REPO}:*"}
    }
  }]
}
EOF
)
aws iam get-role --role-name "$DEPLOY_ROLE" >/dev/null 2>&1 \
  || aws iam create-role --role-name "$DEPLOY_ROLE" \
      --assume-role-policy-document "$ASSUME_DOC" >/dev/null
aws iam update-assume-role-policy --role-name "$DEPLOY_ROLE" \
  --policy-document "$ASSUME_DOC" >/dev/null

# Minimum-privilege policy: ECR + ECS + ALB describe + log groups
POLICY_DOC=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect":"Allow","Action":["ecr:GetAuthorizationToken","ecr:BatchGetImage","ecr:BatchCheckLayerAvailability","ecr:CompleteLayerUpload","ecr:GetDownloadUrlForLayer","ecr:InitiateLayerUpload","ecr:PutImage","ecr:UploadLayerPart"],"Resource":"*"},
    {"Effect":"Allow","Action":["ecs:UpdateService","ecs:DescribeServices","ecs:DescribeTaskDefinition","ecs:RegisterTaskDefinition","ecs:DescribeTasks","ecs:ListTasks"],"Resource":"*"},
    {"Effect":"Allow","Action":["iam:PassRole"],"Resource":"arn:aws:iam::${ACCOUNT_ID}:role/${PROJECT}-*"},
    {"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents","logs:DescribeLogGroups"],"Resource":"*"}
  ]
}
EOF
)
aws iam put-role-policy --role-name "$DEPLOY_ROLE" \
  --policy-name "${PROJECT}-deploy-policy" \
  --policy-document "$POLICY_DOC" >/dev/null
echo "  ✓ Role: arn:aws:iam::${ACCOUNT_ID}:role/${DEPLOY_ROLE}"

# ─────────────────────────────────────────────────────────────────
# 5) Summary — paste into GitHub
# ─────────────────────────────────────────────────────────────────
echo ""
echo "▶ [5/5] DONE"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Paste these into GitHub repo settings:"
echo ""
echo "  Settings → Secrets and variables → Actions → Secrets:"
echo "    AWS_DEPLOY_ROLE_ARN = arn:aws:iam::${ACCOUNT_ID}:role/${DEPLOY_ROLE}"
echo "    MONGO_URL_PROD       = (stored as a secret)"
echo ""
echo "  Settings → Secrets and variables → Actions → Variables:"
echo "    AWS_REGION       = ${AWS_REGION}"
echo "    ECR_BACKEND      = ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT}-backend"
echo "    ECR_FRONTEND     = ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT}-frontend"
echo "    ECS_CLUSTER      = ${PROJECT}-${ENVIRONMENT}-cluster"
echo "    BACKEND_SERVICE  = ${PROJECT}-${ENVIRONMENT}-backend"
echo "    FRONTEND_SERVICE = ${PROJECT}-${ENVIRONMENT}-frontend"
echo "    REACT_APP_BACKEND_URL = https://api.YOUR-DOMAIN.com"
echo "    SMOKE_HEALTH_URL = https://api.YOUR-DOMAIN.com/api/health"
echo ""
echo "  Now create infrastructure/terraform/${ENVIRONMENT}.tfvars:"
echo ""
cat <<EOF
environment        = "${ENVIRONMENT}"
region             = "${AWS_REGION}"
backend_image      = "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT}-backend:latest"
frontend_image     = "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT}-frontend:latest"
domain_name        = "YOUR-DOMAIN.com"
acm_certificate_arn = "arn:aws:acm:${AWS_REGION}:${ACCOUNT_ID}:certificate/CHANGE-ME"

mongo_uri_secret_arn       = "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:${PROJECT}/${ENVIRONMENT}/mongo-uri"
jwt_secret_arn             = "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:${PROJECT}/${ENVIRONMENT}/jwt-secret"
integration_fernet_key_arn = "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:${PROJECT}/${ENVIRONMENT}/fernet-key"
EOF
echo ""
echo "  Update infrastructure/terraform/main.tf to uncomment the S3 backend"
echo "  block with bucket=${TF_BUCKET} dynamodb_table=${TF_TABLE}, then:"
echo ""
echo "  cd infrastructure/terraform"
echo "  terraform init -reconfigure"
echo "  terraform workspace new ${ENVIRONMENT}"
echo "  terraform apply -var-file=${ENVIRONMENT}.tfvars"
echo ""
echo "═══════════════════════════════════════════════════════════════"
