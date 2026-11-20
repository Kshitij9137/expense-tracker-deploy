# Specification - Expense Tracker 2.0

## 1. Functional requirements
| ID | Requirement | Acceptance criteria | Verified by |
|---|---|---|---|
| FR-01 | Record an expense (amount, category, date, note) | Valid input is stored; invalid input is rejected with a clear message | IT-05, WT-03, UAT-01 |
| FR-02 | Edit and delete expenses | Changes persist; missing ids give 404; an empty update is rejected | IT-05, WT-18, UAT-03, UAT-06, UI check |
| FR-03 | List with filters and pagination | Filters by category and dates; pages of at most 500; total reported | IT-07, SV-01, SV-09, WT-16, WT-17 |
| FR-04 | Totals per category for any period | Sorted by size; date range inclusive | IT-08, WT-08 |
| FR-05 | Monthly totals for a year | Always 12 values; month boundaries exact, including December | SV-02, SV-03, WT-21 |
| FR-06 | Month insights | Total, change vs previous month, top category, largest expense, daily average; empty month handled | SV-04, SV-05, WT-22 |
| FR-07 | Budgets with warnings | Budget per category; status shows spent, percent and over-budget flag; exactly meeting a budget is not over | IT-09, IT-10, EC-09, SV-06, WT-19, WT-20, UAT-02 |
| FR-08 | CSV export | All expenses; quotes handled; cells starting with = + - @ neutralised | IT-11, SV-07, SV-08, WT-23, REG-08 |
| FR-09 | Web dashboard | Sign in with key; dashboard, expenses and budgets views; export; sign out | SC-01, SC-02, SC-06, UI check (29 checks) |
| FR-10 | Command-line interface | All commands work; errors give exit code 1 and no traceback | IT-12 to IT-15, ST-01 to ST-06, EC-15 |

## 2. Non-functional requirements
| ID | Requirement | Target | Verified by |
|---|---|---|---|
| NFR-01 | Money is exact | Integer cents, no float drift | UT-01, UT-02, UT-05, EC-07 |
| NFR-02 | Input validation | Every field validated at the boundary | UT-03 to UT-12, WT-04, WT-05, EC-15 |
| NFR-03 | Authentication | Only /health and the dashboard files are public | WT-02, WT-25 |
| NFR-04 | Brute-force protection | Block after repeated wrong keys; recovers after the window | RL-01 to RL-07 |
| NFR-05 | XSS resistance | Strict CSP; no inline script or style; no HTML-parsing APIs; hostile text shown as text | SC-01, SC-04, SC-05, UI check |
| NFR-06 | Graceful failure | No stack traces to users; fail fast on bad configuration | WT-10, EC-15, CF-02, CF-05 |
| NFR-07 | Performance | p95 latency under 100 ms; page of data under 5 ms; month query under 5 ms | Load test (p95 18 ms), benchmarks (0.3 ms, 0.7 ms) |
| NFR-08 | Data durability | Data survives restarts; backups verified and restorable | WT-13, ST-03, OP-01 to OP-05 |
| NFR-09 | Observability | Health, metrics, JSON logs with request ids | WT-11, WT-14, WT-09 |
| NFR-10 | Accessibility | Language, labels for every input, live status region, keyboard operable, reduced motion respected | SC-06, UI check |
| NFR-11 | Maintainability | Layered design, coverage at least 90%, documented extension points | Coverage 95%, docs/MAINTENANCE.md |

## 3. Architecture
```
Browser (dashboard: HTML + CSS + JS, no framework)
   |  HTTPS, X-API-Key header
   v
web.py  (WSGI: routing, auth, rate limiter, headers, JSON, logging)   <-- gunicorn workers
   |
service.py  (business logic: CRUD, insights, budgets, CSV)            <-- also used by cli.py
   |
database.py (SQLite, WAL, covering index)      models.py (validation, money)
```

## 4. Data model
```
expenses(id PK, amount_cents INT > 0, category TEXT, description TEXT, spent_on TEXT 'YYYY-MM-DD')
budgets(category PK, limit_cents INT > 0)
Indexes: (spent_on, amount_cents) covering, (category)
```

## 5. API
| Method and path | Auth | Description |
|---|---|---|
| GET / , /static/app.js , /static/app.css | no | Dashboard files (CSP header on the page) |
| GET /health | no | Liveness and database check |
| GET /metrics | key | Prometheus-style metrics |
| GET /api/expenses?category&start&end&limit&offset | key | Page of expenses plus total (limit 1-500, default 100) |
| POST /api/expenses | key | Create |
| GET, PUT, DELETE /api/expenses/{id} | key | Read, update, delete |
| GET /api/summary?start&end | key | Totals per category |
| GET /api/monthly?year | key | 12 monthly totals |
| GET /api/insights?month=YYYY-MM | key | Headline numbers for a month |
| GET /api/budgets?month=YYYY-MM | key | Budget status |
| PUT, DELETE /api/budgets/{category} | key | Set or remove a budget |
| GET /api/export.csv | key | CSV download |

Status codes: 200, 201, 204, 400 (validation), 401 (key), 404, 405 (with Allow), 413 (body too large), 429 (rate limited, with Retry-After), 500 (generic, with request id).

## 6. Security requirements
Key checked in constant time; failed attempts rate limited per client; strict CSP (`default-src 'self'`, no inline code); security headers on every response; parameterised SQL; body size limit; CSV formula neutralisation; generic 500 responses; secrets only in environment variables. Details: `docs/SECURITY.md`.

## 6a. Known limitations
Single-user (one shared key), single-node SQLite, per-worker rate limit and metrics counters, free-tier Render has no persistent disk.
