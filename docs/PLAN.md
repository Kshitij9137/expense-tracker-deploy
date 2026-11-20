# Project Plan - Expense Tracker 2.0 (Capstone)

## 1. Goal
Turn the command-line tool built across Phases 1-5 into a complete, deployed product a real person can use: a secure web dashboard on top of the existing tested API, with budgets, insights and exports. The capstone must integrate every skill from the internship and be a portfolio piece.

## 2. Why this project
It extends work I already understand deeply, so the time goes into quality rather than learning a new domain. It also demonstrates growth from day one (Hello World) to a deployed, tested, documented system. [Personalise: add one or two sentences about why personal finance tools or web development matter for your own career goals.]

## 3. Scope
**In scope**
- Dashboard: month insights, 12-month spending chart, category breakdown
- Expense management: add, edit, delete, filter, paginate
- Budgets with progress and over-budget warnings
- CSV export that is safe to open in a spreadsheet
- Brute-force protection for the API key
- Final security audit, performance tuning, full documentation, deployment through the existing pipeline

**Out of scope (future work):** multi-user accounts, PostgreSQL, recurring expenses, multiple currencies, mobile app.

## 4. Feature list
| ID | Feature | Priority |
|---|---|---|
| F1 | Month insights (total, change vs last month, top category, daily average, largest expense) | Must |
| F2 | 12-month bar chart and category breakdown | Must |
| F3 | Expense list with filters and pagination | Must |
| F4 | Edit expenses (API and UI) | Must |
| F5 | Budgets with progress bars and warnings | Must |
| F6 | CSV export with formula-injection protection | Must |
| F7 | Rate limiting of failed API-key attempts | Must |
| F8 | Strict Content-Security-Policy, no inline scripts | Must |
| F9 | Accessible, responsive, dark-mode UI | Should |
| F10 | Close all open code-review items from Phase 4 | Should |

## 5. Technical requirements
- Python 3.10+ standard library for the application; gunicorn for production (only runtime dependency)
- SQLite (WAL mode) with indexes tuned by measurement
- Vanilla JavaScript, no framework and no external requests (nothing to fetch from a CDN, nothing to patch)
- Docker image, GitHub Actions pipeline, Render hosting (staging and production), unchanged from Phase 5
- Quality gates: at least 90% coverage, smoke test after every deploy

## 6. Timeline (planned effort)
| Step | Work | Days |
|---|---|---|
| 1 | Plan and specification | 1 |
| 2 | Backend features (insights, monthly, budgets API, pagination, export, rate limiting) | 2 |
| 3 | Dashboard UI | 2 |
| 4 | Testing, debugging, security audit | 2 |
| 5 | Optimization (measure, then change) | 1 |
| 6 | Documentation | 1 |
| 7 | Deploy through staging to production, monitor | 1 |
| 8 | Presentation, feedback, final assessment | 1 |
| | **Total** | **11** |

[Edit this table to match the dates you actually worked.]

## 7. Resources
Existing codebase (Phases 3-5), GitHub and GitHub Actions, Render free plan, Python and Node.js (for the UI check), browser developer tools, mentor feedback sessions.

## 8. Risks and mitigations
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| UI bugs that Python tests cannot see | High | Medium | Run the real page in a simulated browser (jsdom) against a live server |
| XSS through stored text | Medium | High | Text-only DOM building, strict CSP, automated lint test, hostile-input UI test |
| New feature breaks old behaviour | Medium | High | 89 existing tests as a safety net, refactor only with tests green |
| Performance regression | Medium | Medium | Benchmark before and after; keep only changes that measure faster |
| Free-tier hosting limits (sleep, no persistent disk) | Certain | Low | Documented; backups; upgrade path |
| Scope creep | Medium | Medium | Fixed feature list above; extras go to future work |
