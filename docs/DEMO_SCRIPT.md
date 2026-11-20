# Presentation, Demo Script and Assessment

## 1. Audience and goal
Mentors, peers and (if possible) an industry professional. Goal in 12 minutes: tell the story of the project, show it working, explain the decisions, and collect feedback.

## 2. Talk track (7 slides, about 12 minutes)
| # | Slide | Time | Key message |
|---|---|---|---|
| 1 | Title and story | 1 min | From a Hello World in week one to a deployed, tested product |
| 2 | Problem and goals | 1.5 min | People lose track of spending; I wanted a simple, secure, fast tool |
| 3 | Architecture | 2 min | Layered design: dashboard, API, service, SQLite; one codebase for CLI and web |
| 4 | Live demo | 3 min | See section 3 |
| 5 | Quality and security | 2 min | 124 tests, 29 browser checks, 95% coverage; 10 bugs found and fixed; security audit |
| 6 | Deployment and operations | 1.5 min | Staging then production, CI/CD, smoke tests, monitoring, backups, rollback |
| 7 | Lessons and next steps | 1 min | What I would do next; thank you and questions |

## 3. Live demo (3 minutes, rehearse twice)
Preparation: open the production URL, have the API key ready (not on screen), seed a few expenses beforehand, have a second tab with the staging URL and the GitHub Actions run.
1. Open the dashboard. Sign in with a **wrong key** (shows the error), then the right key.
2. Dashboard: point at the insight cards, the 12-month chart and category bars. Change the month.
3. Expenses: add one (`12.50`, `coffee`), watch the totals change. Show filtering and paging. Edit one.
4. Security moment: add an expense whose note is `<img src=x onerror=alert(1)>` and show it appearing as plain text.
5. Budgets: set a budget lower than current spending and show the OVER BUDGET warning.
6. Export CSV; open it.
7. Show `/health` and the GitHub Actions run (green: tests, staging, production).
Backup plan: if the free instance is asleep, open it a minute before; keep screenshots of every step in a folder.

## 4. Questions to prepare for
| Question | Short answer |
|---|---|
| Why SQLite? | Fits single-node, zero-ops, fast with the right indexes; migration path to PostgreSQL is documented |
| Why no framework? | Fewer dependencies, smaller attack surface, shows I understand the basics; trade-off is more hand-written code |
| How do you know it is secure? | Threat model, audit checklist, automated lint and hostile-input tests; residual risks are listed honestly |
| What was the hardest bug? | The stale-response race in the dashboard, found only by running the page in a simulated browser |
| What would you do with more time? | Accounts, PostgreSQL, shared rate limit, commit id in /health |
| What is not tested? | Real browsers beyond the simulation, concurrent multi-process writes, Windows/macOS |
| How would it scale? | More workers need PostgreSQL; the service layer is already separate from the database |

## 5. Feedback form (give to each reviewer)
| Question | Rating 1-5 | Comment |
|---|---|---|
| The project solves a real problem | | |
| Technical quality of the code and architecture | | |
| Testing and security practices | | |
| Documentation (could someone else run and extend it?) | | |
| Clarity of the presentation and demo | | |
| Overall impression | | |
What should I improve first? What was most impressive?

## 6. Feedback received
[Fill in after your presentation: date, who attended, ratings, key comments, and what you will change.]

## 7. Self-assessment against the internship
| Phase | Skill demonstrated in the capstone | Evidence | Self-rating (1-5) |
|---|---|---|---|
| 1 Fundamentals and setup | Git/GitHub workflow, project structure, README | Branches, tags, repository layout | [ ] |
| 2 Core concepts | Functions, classes, data structures, validation | models.py, service.py | [ ] |
| 3 Practical project | Planning, architecture, database design, integration | docs/PLAN.md, SPECIFICATION.md | [ ] |
| 4 Testing and QA | Test levels, edge cases, debugging, code review | 124 tests, BUG_LOG.md, CODE_REVIEW.md | [ ] |
| 5 Deployment | Docker, CI/CD, staging, monitoring, rollback | Pipeline runs, RUNBOOK.md | [ ] |
| 6 Capstone | Product thinking, UI, security audit, optimisation, communication | This report and presentation | [ ] |
Strengths: [ ]   Areas to improve: [ ]   Next learning goals: [ ]
