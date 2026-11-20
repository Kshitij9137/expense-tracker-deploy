# Expense Tracker 2.0

A secure, tested and deployed personal-finance tool: a web dashboard and JSON API on top of a command-line app. Built as the capstone of my internship, it grew from a "Hello World" in week one into a production service with CI/CD, monitoring and a full security review.

> \*\*Live demo:\*\* https://expense-tracker-production-woys.onrender.com  |  \*\*Staging:\*\* https://expense-tracker-staging-fvaw.onrender.com  

## Features

* **Dashboard**: monthly total, change versus last month, top category, daily average, largest expense, 12-month chart, category breakdown
* **Expenses**: add, edit, delete, filter by category and dates, paginated list
* **Budgets**: monthly limits with progress bars and OVER BUDGET warnings
* **CSV export** that is safe to open in a spreadsheet (formula-injection protection)
* **Security**: API key authentication, brute-force rate limiting, strict Content-Security-Policy, no inline code, parameterised SQL
* **Operations**: health check, Prometheus-style metrics, JSON logs with request ids, verified backups and restore, smoke tests, rollback scripts
* **Command-line interface** sharing the same tested business logic

## Architecture

```
Browser (HTML + CSS + vanilla JS)  --HTTPS, X-API-Key-->  web.py (WSGI, gunicorn)
                                                              |
                         cli.py ---------------------->  service.py (business logic)
                                                              |
                                                   database.py (SQLite, WAL)   models.py (validation)
```

Design rules: validation at the boundary, all SQL parameterised, money stored as integer cents, no business logic in the web or CLI layers.

## Quick start

```bash
pip install -r requirements.txt
export PYTHONPATH=src
export APP\_ENV=development            # development needs no key; staging/production require API\_KEY (16+ chars)
python -m expense\_tracker.web         # open http://127.0.0.1:8000
```

Production-style: `APP\_ENV=staging API\_KEY=<long random key> gunicorn expense\_tracker.wsgi:app --bind 127.0.0.1:8000 --workers 2`
Docker: `docker build -t expense-tracker .` then `docker run -p 8000:8000 -e APP\_ENV=staging -e API\_KEY=<16+ chars> expense-tracker`

Command line:

```bash
python -m expense\_tracker add 12.50 food -n "lunch"
python -m expense\_tracker summary
python -m expense\_tracker status --month 2026-10
```

## API (all except `/`, static files and `/health` need the `X-API-Key` header)

`GET/POST /api/expenses` | `GET/PUT/DELETE /api/expenses/{id}` | `GET /api/summary` | `GET /api/monthly?year=` | `GET /api/insights?month=` | `GET /api/budgets` | `PUT/DELETE /api/budgets/{category}` | `GET /api/export.csv` | `GET /metrics`  
Full reference: [docs/SPECIFICATION.md](docs/SPECIFICATION.md)

## Quality

|||
|-|-|
|Automated tests|**124** (unit, integration, system, user acceptance, edge case, regression, API, rate limit, security)|
|Browser-level UI checks|**29** (real page driven in jsdom against a live server)|
|Branch coverage|**95%** (pipeline fails below 90%)|
|Bugs found and fixed|10, each with a regression check ([docs/BUG\_LOG.md](docs/BUG_LOG.md))|
|Load test (2 workers, 8 clients)|\~590 requests/s, p95 18 ms, 0 errors|
|Query performance (200,000 rows)|one-month total 10 ms to 0.7 ms; page of data 0.3 ms|

```bash
export PYTHONPATH=src
python -m unittest discover -s tests -v
coverage run --branch --source=src/expense\_tracker -m unittest discover -s tests \&\& coverage report -m
```

## Deployment

GitHub Actions runs tests on Python 3.10 to 3.12, enforces coverage, deploys to **staging**, smoke-tests it, then deploys to **production** and smoke-tests again. Hosted on Render from the Dockerfile; Docker-host scripts with automatic rollback are included. Guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md), operations: [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Documentation

|Document|Purpose|
|-|-|
|[docs/PLAN.md](docs/PLAN.md)|Goals, scope, features, timeline, risks|
|[docs/SPECIFICATION.md](docs/SPECIFICATION.md)|Requirements, API, data model, traceability to tests|
|[docs/SECURITY.md](docs/SECURITY.md)|Threat model, audit results, residual risks|
|[docs/MAINTENANCE.md](docs/MAINTENANCE.md)|Maintenance schedule and how to extend the project|
|[docs/USER\_GUIDE.md](docs/USER_GUIDE.md)|Using the dashboard and CLI|
|[docs/TEST\_PLAN.md](docs/TEST_PLAN.md), [TEST\_RESULTS.md](docs/TEST_RESULTS.md), [BUG\_LOG.md](docs/BUG_LOG.md), [CODE\_REVIEW.md](docs/CODE_REVIEW.md)|Quality record|
|[docs/DEMO\_SCRIPT.md](docs/DEMO_SCRIPT.md)|Presentation, demo and assessment|

## Project story

|Phase|What I built|
|-|-|
|1|Environment, Git and GitHub, Hello World|
|2|Core concepts: functions, classes, validation, tests|
|3|Command-line Expense Tracker with SQLite|
|4|Test strategy, 7 bugs found, 99% coverage, code review|
|5|Web API, Docker, CI/CD, staging and production, monitoring|
|6|Dashboard, insights, budgets, security audit, optimisation, documentation|

## Known limitations

Single shared API key (no user accounts), single-node SQLite, per-worker rate limit counters, free hosting tier has no persistent disk. See [docs/SECURITY.md](docs/SECURITY.md) and [docs/MAINTENANCE.md](docs/MAINTENANCE.md) for the roadmap.

## Author

Kshitij Gupta - https://www.linkedin.com/in/kshitij-gupta-7a0059343/

