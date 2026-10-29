# Production Checklist

## Before deploying to staging
- [ ] All tests pass locally (`python -m unittest discover -s tests`) and coverage is at least 90%
- [ ] `requirements.txt` is up to date and pinned
- [ ] No secrets in the repository (`git grep -i "api_key="` shows only examples)
- [ ] `.env` is in `.gitignore`; `.env.example` is committed
- [ ] Docker image builds and starts (`docker build -t expense-tracker .`)

## Staging (final testing)
- [ ] Staging uses the same Docker image and settings as production, with its own API key and data
- [ ] `scripts/smoke_test.py` passes against staging
- [ ] Manual check: create, list, filter, summary and delete through the API
- [ ] Wrong key and missing key are rejected with 401
- [ ] Invalid input gives 400 (never 500)
- [ ] Logs show JSON lines with request ids; no secrets in logs
- [ ] `/metrics` responds; request counters increase
- [ ] Backup and restore tested on staging data
- [ ] Load test run (`scripts/loadtest.py`): no server errors, acceptable latency
- [ ] Restart test: data survives a container restart (on a persistent volume)

## Before and during the production release
- [ ] Staging has been healthy for the release candidate
- [ ] Fresh backup taken (automatic with `deploy.sh`)
- [ ] Production `API_KEY` is different from staging, 16+ characters, stored in a password manager
- [ ] Rollback method known and available (previous image tag or Render rollback)
- [ ] Deploy through the pipeline (merge `staging` into `main`)
- [ ] Smoke test passes against production
- [ ] Release tagged in Git (`v1.1.0`)

## After release
- [ ] Uptime monitor is checking `/health`
- [ ] Watch logs for 15 minutes; no 5xx
- [ ] Update `docs/` and the README if anything changed
- [ ] Record the deployment (date, version, who, result)
