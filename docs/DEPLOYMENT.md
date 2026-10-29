# Deployment Guide

## 1. Architecture and environments
```
 Developer --push--> GitHub --> GitHub Actions: tests (3 Python versions) + coverage gate + Docker build
                                   |
                  branch "staging" |                       branch "main"
                                   v                              v
                         STAGING deploy  --smoke test-->  PRODUCTION deploy --smoke test--> users
                      (replica of production)          (manual approval optional)
                                   \_______ both run the same Docker image: gunicorn -> WSGI app -> SQLite _______/
```
| | Development | Staging | Production |
|---|---|---|---|
| Purpose | Coding and debugging | Final testing, exact replica of production | Real users |
| `APP_ENV` | development | staging | production |
| Server | `python -m expense_tracker.web` (wsgiref) | gunicorn in Docker | gunicorn in Docker |
| API key | optional (auth off, warning logged) | required (16+ chars) | required (16+ chars) |
| Git branch | feature branches | `staging` | `main` |
| Data | throwaway | test data only | real data, backed up |

## 2. Configuration (environment variables)
No secret is ever stored in Git. Copy `.env.example` for local use.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | development | development, staging or production |
| `API_KEY` | (none) | Required for staging and production, at least 16 characters. Generate: `python -c "import secrets;print(secrets.token_urlsafe(32))"` |
| `DB_PATH` | expenses.db | SQLite file. Docker uses `/data/expenses.db` on a volume |
| `LOG_LEVEL` | INFO | DEBUG, INFO, WARNING or ERROR |
| `PORT` | 8000 | Port gunicorn listens on (Render sets this automatically) |
| `WEB_CONCURRENCY` | 2 | Number of gunicorn worker processes |
| `MAX_BODY_BYTES` | 10000 | Maximum request body size |

The application **fails fast**: with a missing or weak key in staging/production it exits with code 3 and the message `CONFIGURATION ERROR: ...` instead of running insecurely.

## 3. Production-readiness (what was prepared)
- **Optimized:** SQLite WAL mode and busy timeout for concurrent workers, database indexes, bulk insert, gunicorn with multiple workers, slim Docker image with cached dependency layer.
- **Security hardened:** API key authentication (constant-time comparison), only `/health` is public; request body size limit; parameterised SQL; input validation; generic 500 errors (no stack traces to clients, details only in logs); security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Cache-Control: no-store`); request ids sanitised; Docker container runs as a non-root user with a read-only filesystem and `no-new-privileges`; secrets only in environment variables.
- **Dependencies documented:** `requirements.txt` (runtime, pinned) and `requirements-dev.txt` (test tools). The application itself uses only the Python standard library.
- **Observability built in:** JSON logs to stdout, request ids, `/health`, `/metrics`.

## 4. Deployment path A: Render (free, easiest)
Render builds the Dockerfile directly from GitHub. Free web services sleep after 15 minutes without traffic and have no persistent disk (SQLite data is lost on restart/redeploy), which is acceptable for an internship demo but not for real data. Paid plans can attach a persistent disk.

1. Push the project to GitHub. Create the two branches: `git branch staging && git push -u origin staging` (main already exists).
2. Create a Render account and connect GitHub.
3. **New > Blueprint**, choose the repository. Render reads `render.yaml` and proposes two services (`expense-tracker-staging`, `expense-tracker-production`). If the Blueprint is rejected, create the two services manually: **New > Web Service**, runtime **Docker**, branch `staging` / `main`, health check path `/health`, and the environment variables from section 2.
4. When asked for `API_KEY`, enter a different long random key for each service. Save both keys in a password manager.
5. Wait for the first deploy. Open `https://<service-name>.onrender.com/health`. You should see `{"status": "ok", ...}`.
6. In each Render service, copy the **Deploy Hook** URL (Settings).
7. In GitHub: **Settings > Secrets and variables > Actions**, add: `STAGING_URL`, `STAGING_API_KEY`, `STAGING_DEPLOY_HOOK`, `PRODUCTION_URL`, `PRODUCTION_API_KEY`, `PRODUCTION_DEPLOY_HOOK`.
8. Optional approval gate: **Settings > Environments > production > Required reviewers**.

## 5. Deployment path B: any Linux server with Docker
```bash
git clone https://github.com/<you>/<repo>.git && cd <repo>
export STAGING_API_KEY=...  PRODUCTION_API_KEY=...        # different long random keys
scripts/deploy.sh staging                                 # build, start, smoke test, auto-rollback on failure
scripts/deploy.sh production                              # same for production (port 8002)
scripts/rollback.sh production                            # manual rollback to the previous version
```
Put a reverse proxy (Caddy or nginx) in front for HTTPS, and never expose ports 8001/8002 directly.

## 6. Release process
1. Merge feature work into `staging`. The pipeline runs the tests, deploys to staging and runs the smoke test.
2. Test in staging (checklist in `docs/PRODUCTION_CHECKLIST.md`).
3. If staging is good, merge `staging` into `main`. The pipeline checks staging is healthy, deploys to production and runs the smoke test.
4. Tag the release: `git tag -a v1.1.0 -m "First production release" && git push origin v1.1.0`.

## 7. Verify any deployment
```bash
python scripts/smoke_test.py https://<service>.onrender.com --api-key <KEY> --wait 90
```
Checks: health, auth rejects missing and wrong keys, create / list / delete round trip, validation returns 400, metrics available. Exit code 0 = pass.

## 8. API quick reference
| Method and path | Auth | Purpose |
|---|---|---|
| `GET /health` | no | Liveness and database check |
| `GET /metrics` | key | Prometheus-style metrics |
| `GET /api/expenses?category=&start=&end=` | key | List |
| `POST /api/expenses` | key | Create. JSON: `amount`, `category`, `date` (optional), `note` (optional) |
| `GET /api/expenses/<id>` | key | Fetch one |
| `DELETE /api/expenses/<id>` | key | Delete |
| `GET /api/summary?start=&end=` | key | Totals per category |

```bash
curl -X POST https://<service>/api/expenses -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"amount":"12.50","category":"food","note":"lunch"}'
```

## 9. Known limitations
- SQLite supports one server node; scaling beyond one machine needs PostgreSQL.
- `/metrics` counters are per worker process; the database-derived gauges are exact.
- Free Render plan: cold starts after idle and no persistent storage.
