#!/usr/bin/env bash
# Build + push both images to ECR and trigger ECS rollout.
# Used locally for emergency redeploys; CI handles the normal path.
set -euo pipefail

: "${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"
: "${AWS_REGION:?Set AWS_REGION}"
: "${ECS_CLUSTER:?Set ECS_CLUSTER}"

REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
TAG="${1:-$(git rev-parse --short HEAD)}"
BACKEND_URL="${REACT_APP_BACKEND_URL:?Set REACT_APP_BACKEND_URL}"

echo "▶ ECR login"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

echo "▶ Build & push backend ($TAG)"
docker buildx build \
  --platform linux/amd64 \
  -t "$REGISTRY/a1fp-backend:$TAG" \
  -t "$REGISTRY/a1fp-backend:latest" \
  --push ./backend

echo "▶ Build & push frontend ($TAG)"
docker buildx build \
  --platform linux/amd64 \
  --build-arg REACT_APP_BACKEND_URL="$BACKEND_URL" \
  -t "$REGISTRY/a1fp-frontend:$TAG" \
  -t "$REGISTRY/a1fp-frontend:latest" \
  --push ./frontend

echo "▶ Forcing ECS rollout"
for svc in a1fp-production-backend a1fp-production-frontend; do
  aws ecs update-service --cluster "$ECS_CLUSTER" --service "$svc" --force-new-deployment >/dev/null
done

aws ecs wait services-stable --cluster "$ECS_CLUSTER" \
  --services a1fp-production-backend a1fp-production-frontend

echo "✓ Deploy complete: $TAG"
