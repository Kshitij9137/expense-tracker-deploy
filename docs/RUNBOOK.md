# Operations Runbook

## 1. Monitoring
| What | How | Alert when |
|---|---|---|
| Availability | Uptime monitor (e.g. UptimeRobot free plan, 5-minute checks) on `GET /health`; also keeps a free Render service awake | Two failed checks in a row |
| Container health | Docker `HEALTHCHECK` / Render health check on `/health` | Status unhealthy |
| Errors | Count of log lines with `"level":"ERROR"` or `"status":5xx` | Any 5xx in production |
| Latency | `duration_ms` in request logs; `expense_tracker_request_seconds_sum / _count` | Average above 200 ms or p95 above 500 ms |
| Auth abuse | Many `"status":401` lines from the same period | More than 50 in 5 minutes |
| Data | `expense_tracker_expenses` gauge and backup file age | Backup older than 24 h |

Baseline measured locally (2 gunicorn workers, 8 concurrent clients, mixed read/write): about 530 requests/second, p50 13 ms, p95 22 ms, p99 28 ms, 0 server errors.

### Metrics (`GET /metrics`, needs the API key)
`expense_tracker_requests_total{status="200"}`, `expense_tracker_request_seconds_sum`, `expense_tracker_request_seconds_count`, `expense_tracker_uptime_seconds`, `expense_tracker_expenses`.

## 2. Reading logs
Logs are one JSON object per line on stdout.
```json
{"ts":"2026-10-28T07:58:20","level":"WARNING","msg":"request","request_id":"303a250b240f","method":"GET","path":"/api/expenses","status":401,"duration_ms":0.5}
```
| Field | Meaning |
|---|---|
| level | INFO = success, WARNING = client error (4xx), ERROR = server error (5xx) |
| request_id | Also returned in the `X-Request-ID` header and in 500 responses; quote it when investigating |
| duration_ms | Time taken by the application |

Where to look: Render dashboard > service > **Logs**; Docker host: `docker logs --tail 200 -f expense-tracker-production`.
Useful filters: `docker logs expense-tracker-production | grep '"level":"ERROR"'`, `... | grep '"status":5'`, `... | grep <request_id>`.
Passwords and API keys are never logged.

## 3. Troubleshooting
| Symptom | Likely cause | Action |
|---|---|---|
| Container exits immediately; log says `CONFIGURATION ERROR` | Missing or short `API_KEY`, bad `APP_ENV` | Fix the environment variable and redeploy |
| `/health` returns 503 or 500 | Database file missing, unwritable or corrupt | Check the volume/permissions; run `python -m expense_tracker.ops check --db /data/expenses.db`; restore a backup |
| All API calls return 401 | Wrong or missing `X-API-Key` header | Check the key in the client and in the service settings |
| 413 on POST | Body larger than `MAX_BODY_BYTES` | Send less data or raise the limit |
| `database is locked` in logs | Heavy concurrent writes | Reduce workers or move to PostgreSQL; WAL and a 10 s timeout are already enabled |
| Slow first request on Render | Free service was asleep | Expected; use an uptime monitor or a paid plan |
| Data disappeared after a restart on Render | Free plan has an ephemeral disk | Expected on the free plan; use a persistent disk or PostgreSQL |
| Smoke test fails after deploy | Bad release | Roll back (section 4), then investigate in staging |

## 4. Rollback
**Render:** dashboard > service > **Events** (or Deploys) > pick the last good deploy > **Rollback**. Then run the smoke test.
**Docker host:** `scripts/rollback.sh production` (redeploys the previous image tag and smoke tests it). `scripts/deploy.sh` rolls back automatically if its smoke test fails.
**Code:** `git revert <bad-commit>` on `main` and push; the pipeline redeploys the fixed version.
After any rollback: write down what happened (section 6), and reproduce the problem in staging before trying again.

## 5. Backup and restore
```bash
python -m expense_tracker.ops backup  --db /data/expenses.db --dest /data/backups --keep 7   # safe while running
python -m expense_tracker.ops check   --db /data/expenses.db
python -m expense_tracker.ops restore --db /data/expenses.db --from /data/backups/expenses-YYYYMMDD-HHMMSS.db
```
- Backups use SQLite's online backup API, are integrity-checked and are pruned to the newest 7.
- `deploy.sh` takes a backup before every deployment.
- Schedule a daily backup on a Docker host: `0 2 * * * docker exec expense-tracker-production python -m expense_tracker.ops backup --db /data/expenses.db --dest /data/backups --keep 7`
- Copy backups off the server regularly. A backup on the same disk does not protect against disk loss.
- **Restore test:** run a restore in staging every month. An untested backup is not a backup. Restore always keeps the previous database as `<db>.before-restore`.

## 6. Incident record (template)
| Field | Entry |
|---|---|
| Date / time detected | |
| How detected (alert, user, smoke test) | |
| Impact | |
| Request ids / log evidence | |
| Root cause | |
| Action taken (rollback, fix) | |
| Time to recover | |
| Prevention (new test, alert, check) | |
