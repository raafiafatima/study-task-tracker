# Runs the smoke tests in an isolated Compose project (own network, own
# throwaway database volume, port 18080), then cleans up. Your demo stack and
# its data are not touched.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$project = "study-task-tracker-test"
# Throwaway values for the disposable test database only.
if (-not $env:POSTGRES_DB)       { $env:POSTGRES_DB = "tasks_test" }
if (-not $env:POSTGRES_USER)     { $env:POSTGRES_USER = "tasks_test" }
if (-not $env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD = "test-only-" + [guid]::NewGuid().ToString("N") }
$env:WEB_PORT = "18080"

docker compose -p $project -f compose.yaml -f compose.test.yaml run --rm --build smoke
$code = $LASTEXITCODE
docker compose -p $project -f compose.yaml -f compose.test.yaml down -v --remove-orphans
exit $code
