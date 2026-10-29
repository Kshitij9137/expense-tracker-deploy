#!/usr/bin/env bash
# Manually roll an environment back to the previously deployed image tag.
# Usage: scripts/rollback.sh <staging|production>
set -euo pipefail
ENVIRONMENT="${1:?usage: rollback.sh <staging|production>}"
case "$ENVIRONMENT" in
  staging)    PORT=8001; KEYVAR=STAGING_API_KEY ;;
  production) PORT=8002; KEYVAR=PRODUCTION_API_KEY ;;
  *) echo "environment must be staging or production" >&2; exit 2 ;;
esac
PREVIOUS="$(cat ".deploy/$ENVIRONMENT.previous" 2>/dev/null || true)"
[ -n "$PREVIOUS" ] || { echo "No previous version recorded for $ENVIRONMENT" >&2; exit 1; }
API_KEY_VALUE="${!KEYVAR:?export $KEYVAR first}"
echo ">> Rolling $ENVIRONMENT back to $PREVIOUS"
IMAGE_TAG="$PREVIOUS" docker compose -f "docker-compose.$ENVIRONMENT.yml" up -d
python3 scripts/smoke_test.py "http://127.0.0.1:$PORT" --api-key "$API_KEY_VALUE" --wait 60
CURRENT="$(cat ".deploy/$ENVIRONMENT.current" 2>/dev/null || true)"
echo "$PREVIOUS" > ".deploy/$ENVIRONMENT.current"; echo "$CURRENT" > ".deploy/$ENVIRONMENT.previous"
echo ">> Rollback complete"
