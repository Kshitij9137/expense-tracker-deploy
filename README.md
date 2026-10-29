# Expense Tracker

> **v1.1.0 - production release.** CLI app plus a deployable web API (Docker, gunicorn, CI/CD, monitoring, backups). Deployment guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Operations: [docs/RUNBOOK.md](docs/RUNBOOK.md) | Checklist: [docs/PRODUCTION_CHECKLIST.md](docs/PRODUCTION_CHECKLIST.md)

A command-line application for recording personal expenses, analysing spending by category, and tracking monthly budgets. Built as the Phase 3 practical implementation project of my internship.

## Features
- Add, list, update and delete expenses
- Filter by category and date range
- Totals per category and monthly totals
- Monthly budgets per category with over-budget warnings
- Export all expenses to CSV
- Input validation with clear error messages
- SQLite storage (no external dependencies)

## Requirements
Python 3.8 or newer. No third-party packages are needed.

## Quick start
```bash
git clone https://github.com/<your-username>/expense-tracker.git
cd expense-tracker
export PYTHONPATH=src          # Windows PowerShell: $env:PYTHONPATH="src"

python -m expense_tracker add 12.50 food -n "lunch"
python -m expense_tracker add 40 travel -d 2026-10-02 -n "bus pass"
python -m expense_tracker list
python -m expense_tracker summary
python -m expense_tracker budget food 20
python -m expense_tracker status --month 2026-10
python -m expense_tracker export my_expenses.csv
```

## Run the tests
```bash
python -m unittest discover -s tests -v
```
89 tests (unit, integration, system, user acceptance, edge case, regression, web/API, configuration, operations) with 94% coverage. See `docs/TEST_PLAN.md`.

## Run as a web service
```bash
pip install -r requirements.txt
export PYTHONPATH=src APP_ENV=staging API_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(32))") DB_PATH=/tmp/expenses.db
gunicorn expense_tracker.wsgi:app --bind 127.0.0.1:8000 --workers 2
python scripts/smoke_test.py http://127.0.0.1:8000 --api-key "$API_KEY"
```
With Docker: `docker build -t expense-tracker .` then `docker run -p 8000:8000 -e APP_ENV=staging -e API_KEY=<16+ chars> -v data:/data expense-tracker`.

## Quality assurance
```bash
coverage run --branch --source=src/expense_tracker -m unittest discover -s tests
coverage report -m
python tools/generate_test_report.py   # refreshes docs/TEST_RESULTS.md
```

## Project structure
```
expense-tracker/
├── src/expense_tracker/
│   ├── cli.py        # presentation layer (argparse)
│   ├── service.py    # business logic
│   ├── database.py   # SQLite connection and schema
│   ├── models.py     # data model and validation
│   └── __main__.py   # entry point
├── tests/            # 64 tests: unit, integration, system, UAT, edge case, regression
├── scripts/          # smoke_test.py, loadtest.py, deploy.sh, rollback.sh
├── tools/            # generate_test_report.py
├── Dockerfile, docker-compose.*.yml, render.yaml, requirements*.txt, .env.example
├── .github/workflows/  # ci.yml, deploy.yml
├── docs/
│   ├── DEPLOYMENT.md, RUNBOOK.md, PRODUCTION_CHECKLIST.md
│   ├── TEST_PLAN.md
│   ├── TEST_RESULTS.md
│   ├── BUG_LOG.md
│   ├── CODE_REVIEW.md
│   ├── ARCHITECTURE.md
│   └── USER_GUIDE.md
└── README.md
```

See `docs/ARCHITECTURE.md` for design decisions and `docs/USER_GUIDE.md` for all commands.

## Author
[Your Name]
