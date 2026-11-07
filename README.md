# Study Task Tracker

A deliberately small three-tier app for a Cloud Computing CEA. The app is tiny so the focus stays on containers, networking and CI/CD.

```
Browser ──► Nginx (web, :80) ──/api/*──► Flask + Gunicorn (api, :8000) ──► PostgreSQL
                 │  └─ /health  (200 only if Flask can reach the database)
                 └─ static HTML/CSS/JS
```

## File tree

```
study-task-tracker/
├── compose.yaml            local stack: web + api + db (only web published, :8080)
├── compose.aws.yaml        EC2 stack: web + api (db is private RDS), web on :80
├── compose.test.yaml       test overlay: adds a one-shot smoke-test container
├── .env.example            local settings template  (copy to .env)
├── api.aws.env.example     EC2 runtime DB settings template (copy to api.aws.env on EC2)
├── .gitignore  .gitattributes
├── api/
│   ├── Dockerfile  .dockerignore  requirements.txt
│   └── app.py              Flask API (parameterized SQL, no secrets in logs/errors)
├── web/
│   ├── Dockerfile  .dockerignore  nginx.conf
│   └── html/               index.html  style.css  app.js
├── db/
│   ├── init.sql            idempotent schema (admin runs this)
│   └── app_user.sql        creates the limited app user + minimal grants (admin runs this)
├── certs/                  put the RDS CA bundle here on EC2 (git-ignored)
└── scripts/
    ├── smoke_test.py       stdlib-only tests, run through Nginx
    ├── test.ps1            one-command test run (Windows)
    └── test.sh             same for CI (Linux)
```

## Run it locally (Windows 11, PowerShell, Docker Desktop)

Make sure Docker Desktop is running in Linux-containers mode.

```powershell
Copy-Item .env.example .env      # first time only; then edit .env and set your own password
docker compose up --build -d     # ONE COMMAND: build and run everything
```

Open <http://localhost:8080>. First startup waits for PostgreSQL to be healthy, creates the schema from `db/init.sql`, then starts Flask and Nginx in order. Check status with `docker compose ps`; logs with `docker compose logs -f`.

Stop (keeps your data): `docker compose down`
Stop **and delete the database volume**: `docker compose down -v`

Useful quick checks:

```powershell
Invoke-RestMethod http://localhost:8080/health
Invoke-RestMethod http://localhost:8080/api/tasks
Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/tasks -ContentType 'application/json' -Body '{"title":"From PowerShell"}'
```

## Run the tests

```powershell
.\scripts\test.ps1               # ONE COMMAND: build, test through Nginx, clean up
```

If PowerShell blocks the script: `powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1`.

It starts a separate Compose project (`study-task-tracker-test`, own network, throwaway database, host port 18080), runs `scripts/smoke_test.py` from a container on that network, then removes everything. Your demo stack and data are untouched. It checks: page served, `/health` through Nginx, valid task → 201 and listed newest-first, trimmed titles, 120 chars accepted, and rejection (HTTP 400 + JSON error) of empty, whitespace-only, 121-char, missing, non-string and non-JSON input.

For CI on Linux: `sh scripts/test.sh`. The script exits non-zero on any failure.
You can also point the same tests at any running instance: `python scripts/smoke_test.py http://localhost:8080` (they create a few tasks, so avoid a database you care about).

## Demo: data survives a restart

```powershell
docker compose up --build -d
# 1. Open http://localhost:8080 and add the task "Revise the TCP handshake".
docker compose down              # removes the containers but KEEPS the pgdata volume
docker compose up -d             # new containers, same volume
# 2. Refresh the page: the task is still there.
Invoke-RestMethod http://localhost:8080/api/tasks
```

Never add `-v` to `down` during this demo; that deletes the volume.

## Change the page heading (future CI/CD demo)

Edit the `<h1>` (and, if you like, `<title>`) in `web/html/index.html`:

```html
<h1 id="page-heading">Study Task Tracker v2</h1>
```

Locally: `docker compose up --build -d web`. In the pipeline, only the **web** image changes, which makes it a clean demonstration of build → push to ECR → pull and restart on EC2. The smoke test checks for an `<h1>`, not specific heading text, so changing the heading won't break it.

## Design notes

- **Relative URLs.** The browser only calls `/api/tasks`. Nginx forwards `/api/...` to `http://api:8000/api/...` with the prefix intact (`proxy_pass` has no URI part).
- **Readiness.** `/health` on Nginx proxies to Flask's `/api/health`, which runs `SELECT 1 FROM tasks LIMIT 1`. It returns 200 `{"status":"ok"}` only if the database is reachable and the schema and permissions are in place; otherwise 503 `{"status":"unavailable"}` (or 502 from Nginx if Flask is down). No internal details are returned. Use `/health` as the ALB target-group health check path, expecting 200.
- **Nginx resolves `api` at request time** (Docker DNS `127.0.0.11`), so it starts even if Flask is briefly down.
- **Secrets.** Flask reads `DB_*` variables only. Logs and error responses contain no credentials or driver messages. Real values live only in `.env` / `api.aws.env`, both git-ignored.
- **Local database user.** Locally Flask connects as the Postgres user from `.env` for simplicity. In AWS it must use the limited user (below).

## AWS handoff

You handle AWS infrastructure, GitHub OIDC and the workflow. This is what the app side needs.

### 1. Images (build and push from CI or your machine)

```powershell
docker build -t "$ECR/study-task-tracker-web:$TAG" ./web
docker build -t "$ECR/study-task-tracker-api:$TAG" ./api
docker push "$ECR/study-task-tracker-web:$TAG"
docker push "$ECR/study-task-tracker-api:$TAG"
```

No secrets are baked into either image.

### 2. Database setup (once, by a database administrator)

Needs a network path to the private RDS instance (for example from the EC2 host, which needs Docker only; the `postgres` image supplies `psql`). The database named in `DB_NAME` must already exist. Download the RDS CA bundle first (step 3). Run on EC2 (bash) from the project folder:

```bash
export PGHOST=<rds-endpoint> PGUSER=<rds-admin-user> PGDATABASE=tasks
export PGSSLMODE=verify-full PGSSLROOTCERT=/certs/global-bundle.pem
read -rsp "RDS admin password: " PGPASSWORD; echo; export PGPASSWORD
export APP_DB_USER=tasks_app
read -rsp "New password for tasks_app: " APP_DB_PASSWORD; echo; export APP_DB_PASSWORD

docker run --rm -v "$PWD/db:/db:ro" -v "$PWD/certs:/certs:ro" \
  -e PGHOST -e PGUSER -e PGPASSWORD -e PGDATABASE -e PGSSLMODE -e PGSSLROOTCERT \
  -e APP_DB_USER -e APP_DB_PASSWORD postgres:16-alpine \
  sh -c 'psql -v ON_ERROR_STOP=1 -f /db/init.sql && psql -v ON_ERROR_STOP=1 -f /db/app_user.sql'
```

`init.sql` creates the table (idempotent). `app_user.sql` creates the login role and grants only `CONNECT`, `USAGE` on schema `public`, and `SELECT, INSERT` on `tasks` (no `UPDATE`, `DELETE`, DDL or superuser rights). `id` is an identity column, so no sequence grant is needed. Both scripts are safe to re-run. The running Flask app never sees admin credentials.

### 3. EC2 host files

Create these on the EC2 host (neither is in Git):

```bash
mkdir -p certs
curl -fsSL -o certs/global-bundle.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem

cp api.aws.env.example api.aws.env     # then edit; set DB_PASSWORD to the tasks_app password
chmod 600 api.aws.env
```

`api.aws.env` variables (all required):

| Variable | Meaning |
|---|---|
| `DB_HOST` | RDS endpoint hostname |
| `DB_PORT` | `5432` |
| `DB_NAME` | database name (e.g. `tasks`) |
| `DB_USER` | the **limited** user (e.g. `tasks_app`), not the RDS admin |
| `DB_PASSWORD` | that user's password |
| `DB_SSLMODE` | `verify-full` (verifies certificate chain and that the hostname matches) |
| `DB_SSLROOTCERT` | `/certs/global-bundle.pem` (path inside the container) |

Shell variables read by `compose.aws.yaml`: `WEB_IMAGE` and `API_IMAGE` (required; full ECR URI and tag), plus optional `API_ENV_FILE` (default `./api.aws.env`) and `RDS_CA_BUNDLE_FILE` (default `./certs/global-bundle.pem`; must exist as a file, or Docker creates a directory in its place). `DB_SSLMODE=verify-full` requires `DB_HOST` to be the RDS endpoint name, not an IP address.

### 4. Deploy

```bash
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
export WEB_IMAGE=<account>.dkr.ecr.<region>.amazonaws.com/study-task-tracker-web:<tag>
export API_IMAGE=<account>.dkr.ecr.<region>.amazonaws.com/study-task-tracker-api:<tag>
docker compose -f compose.aws.yaml pull
docker compose -f compose.aws.yaml up -d --remove-orphans
docker compose -f compose.aws.yaml ps
curl -i http://localhost/health        # expect 200
```

Only `compose.aws.yaml`, `api.aws.env`, and `certs/global-bundle.pem` (and `db/` for the one-time setup) need to be on the host; the images carry the code.

### 5. Things your infrastructure needs to allow

- Inbound 80 to EC2 (from the ALB or your IP); outbound from EC2 to RDS on 5432. Add an RDS security-group rule allowing the EC2 security group.
- ALB target-group health check: `GET /health`, success code `200`.
- Flask is not published on the host; only Nginx listens on port 80.
- The app speaks plain HTTP. If you terminate HTTPS at the ALB, no app changes are needed.

## Troubleshooting

- `Copy .env.example to .env first`: create `.env` (see above).
- Port 8080 in use: set `WEB_PORT=8090` in `.env` and use that port.
- Page shows "Couldn't load your tasks": `docker compose logs api db`. A 503 means Flask cannot reach or use the database.
- Changed the schema locally? `init.sql` only runs on an empty volume. Use `docker compose down -v` to reset.
