#!/usr/bin/env sh
# Same as scripts/test.ps1, for CI runners (Linux/macOS).
set -u
cd "$(dirname "$0")/.."

PROJECT=study-task-tracker-test
export POSTGRES_DB="${POSTGRES_DB:-tasks_test}"
export POSTGRES_USER="${POSTGRES_USER:-tasks_test}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-test-only-$(date +%s)}"
export WEB_PORT=18080

docker compose -p "$PROJECT" -f compose.yaml -f compose.test.yaml run --rm --build smoke
code=$?
docker compose -p "$PROJECT" -f compose.yaml -f compose.test.yaml down -v --remove-orphans
exit $code
