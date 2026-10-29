#!/usr/bin/env bash
# Deploy to a Docker host (VM) with automatic smoke test and rollback.
# Usage: scripts/deploy.sh <staging|production> [image-tag]
# Needs: docker + docker compose, and STAGING_API_KEY / PRODUCTION_API_KEY exported.
set -euo pipefail

ENVIRONMENT="${1:?usage: deploy.sh <staging|production> [tag]}"
TAG="${2:-$(git rev-parse --short HEAD)}"
case "$ENVIRONMENT" in
  staging)    PORT=8001; KEYVAR=STAGING_API_KEY ;;
  production) PORT=8002; KEYVAR=PRODUCTION_API_KEY ;;
  *) echo "environment must be staging or production" >&2; exit 2 ;;
esac
COMPOSE="docker-compose.${ENVIRONMENT}.yml"
STATE_DIR=".deploy"; mkdir -p "$STATE_DIR"
PREVIOUS="$(cat "$STATE_DIR/$ENVIRONMENT.current" 2>/dev/null || true)"
API_KEY_VALUE="${!KEYVAR:?export $KEYVAR first}"

echo ">> Building image expense-tracker:$TAG"
docker build -t "expense-tracker:$TAG" .

if [ -n "$PREVIOUS" ] && docker ps --format '{{.Names}}' | grep -q "expense-tracker-$ENVIRONMENT"; then
  echo ">> Backing up the database before deploying"
  docker exec "expense-tracker-$ENVIRONMENT" python -m expense_tracker.ops backup --db /data/expenses.db --dest /data/backups --keep 7
fi

echo ">> Starting $ENVIRONMENT with tag $TAG (previous: ${PREVIOUS:-none})"
IMAGE_TAG="$TAG" docker compose -f "$COMPOSE" up -d

echo ">> Smoke test"
if python3 scripts/smoke_test.py "http://127.0.0.1:$PORT" --api-key "$API_KEY_VALUE" --wait 90; then
  echo "$TAG" > "$STATE_DIR/$ENVIRONMENT.current"
  [ -n "$PREVIOUS" ] && echo "$PREVIOUS" > "$STATE_DIR/$ENVIRONMENT.previous"
  echo ">> Deployment of $TAG to $ENVIRONMENT succeeded"
else
  echo "!! Smoke test FAILED" >&2
  if [ -n "$PREVIOUS" ]; then
    echo "!! Rolling back to $PREVIOUS" >&2
    IMAGE_TAG="$PREVIOUS" docker compose -f "$COMPOSE" up -d
    python3 scripts/smoke_test.py "http://127.0.0.1:$PORT" --api-key "$API_KEY_VALUE" --wait 60 \
      && echo "!! Rollback to $PREVIOUS succeeded" >&2 || echo "!! ROLLBACK ALSO FAILED - manual action needed (see docs/RUNBOOK.md)" >&2
  else
    echo "!! No previous version to roll back to; see docs/RUNBOOK.md" >&2
  fi
  exit 1
fi
