# Maintenance and Extension Guide

## 1. Routine maintenance
| When | Task | How |
|---|---|---|
| Every deploy | Smoke test | `python scripts/smoke_test.py <url> --api-key <key>` (the pipeline does this) |
| Daily | Backup (hosts with a persistent disk) | `python -m expense_tracker.ops backup ...` (cron) |
| Weekly | Read error logs, check uptime monitor | Logs: filter `"level":"ERROR"` |
| Monthly | Restore drill in staging | `ops restore`, then smoke test |
| Monthly | Dependency check | Review `requirements.txt` (gunicorn) and GitHub Actions versions; read release notes; upgrade in staging first |
| Quarterly | Rotate API keys | docs/SECURITY.md, section 4 |
| Quarterly | Review open items | docs/CODE_REVIEW.md, docs/PLAN.md "future work" |

## 2. How the code is organised (rules to keep it maintainable)
| Layer | File | Rule |
|---|---|---|
| Models | `models.py` | Validation and money conversion only. No I/O. |
| Database | `database.py` | Schema and connection only. |
| Service | `service.py` | All business rules and SQL. Never imports web or CLI code. |
| Web | `web.py` | Routing, auth, headers. Calls the service; contains no SQL. |
| CLI | `cli.py` | One small handler per command in the `COMMANDS` table. |
| Dashboard | `static/` | No framework, no inline code, text-only DOM building. |
Rules: every user-supplied value is validated in `models.py`; every SQL statement is parameterised; every new behaviour gets a test; refactor only while tests are green.

## 3. How to add a feature (worked example: "tags" on expenses)
1. **Specification**: add a requirement row to `docs/SPECIFICATION.md` with acceptance criteria.
2. **Model**: add validation (`clean_tag`) in `models.py` with unit tests.
3. **Database**: add a column/table in `database.py`. Existing databases need a migration: use `ALTER TABLE ... ADD COLUMN` guarded by a `PRAGMA table_info` check, and test it on a copy of real data first.
4. **Service**: extend `ExpenseService` methods; write service tests (edge cases first).
5. **API**: add the route in `web.py` (`need(method, (...))` for 405 handling); add API tests (success, validation, 401, 404).
6. **Dashboard**: add form fields with `<label for>` in `index.html`, and rendering in `app.js` using `el()` (text only). Run `tools/ui/ui_check.js`.
7. **Docs**: update the API table, the user guide and the changelog.
8. **Release**: merge to `staging`, check the pipeline and the smoke test, then promote to `main`.

## 4. Test commands
```bash
export PYTHONPATH=src
python -m unittest discover -s tests -v                                        # 124 tests
coverage run --branch --source=src/expense_tracker -m unittest discover -s tests && coverage report -m
python tools/generate_test_report.py                                          # refresh docs/TEST_RESULTS.md
cd tools/ui && npm install && BASE=http://127.0.0.1:8000 KEY=<key> node ui_check.js   # 29 browser-level checks (needs a running server)
```

## 5. Configuration reference
`APP_ENV`, `API_KEY`, `DB_PATH`, `LOG_LEVEL`, `PORT`, `WEB_CONCURRENCY`, `MAX_BODY_BYTES`, `RATE_LIMIT_FAILS` (default 10), `RATE_LIMIT_WINDOW` (seconds, default 60). See `.env.example`.

## 6. Troubleshooting pointers
Operations problems: `docs/RUNBOOK.md`. Deployment steps: `docs/DEPLOYMENT.md`. A 429 in the dashboard means too many wrong keys; wait for the `Retry-After` seconds.

## 7. Future work
PostgreSQL and multiple users with proper accounts; recurring expenses; currencies; shared rate-limit store; commit id in `/health` (the version check already proves the release; a commit id would prove the exact build); cookie-based sessions.
