# Architecture

## Overview
The application uses a layered architecture so each part has one responsibility and can be tested on its own.

```
CLI (cli.py)  ->  Service (service.py)  ->  Database (database.py / SQLite)
                         |
                  Models (models.py): validation, money helpers
```

| Layer | File | Responsibility |
|---|---|---|
| Presentation | `cli.py` | Parse arguments, print results, convert errors to exit codes |
| Business logic | `service.py` | CRUD, filtering, totals, budgets, CSV export |
| Data | `database.py` | Open connection, create schema and indexes |
| Models | `models.py` | `Expense` dataclass, validation, money conversion |

## Technology choices
- **Python 3 standard library only**: no installation problems, easy for reviewers to run.
- **SQLite**: file-based relational database, ideal for a single-user local app; supports SQL aggregation and indexes.
- **argparse**: built-in, gives sub-commands and automatic `--help`.
- **unittest**: built-in test framework.

## Database design
```
expenses(id PK, amount_cents INT > 0, category TEXT, description TEXT, spent_on TEXT YYYY-MM-DD)
budgets(category PK, limit_cents INT > 0)
Indexes: idx_expenses_date(spent_on), idx_expenses_category(category)
```

## Key decisions
1. **Money stored as integer cents.** Floating point cannot represent values such as 0.10 exactly, so sums drift. Integers are exact. Conversion uses `Decimal`.
2. **Parameterised SQL everywhere.** User input is never concatenated into queries, which prevents SQL injection (covered by a test).
3. **Validation at the boundary.** Amounts, dates and categories are validated in `models.py` before reaching the database. `NaN` and `inf` are rejected explicitly.
4. **Database CHECK constraints** are a second line of defence for invalid amounts.
5. **Dates stored as ISO text** so range queries work with simple string comparison and sort correctly.
6. **Single aggregate queries** (`GROUP BY`, `LEFT JOIN`) instead of looping in Python, so work happens inside the database.
7. **Dependency injection**: `ExpenseService` receives a connection, so tests use an in-memory database.

## Error handling
`ValidationError` (bad input) and `KeyError` (missing record) are caught in the CLI, shown as `Error: ...` on stderr, and return exit code 1.

## Possible future improvements
Recurring expenses, multiple currencies, a web or GUI front end, charts, and database migrations.
