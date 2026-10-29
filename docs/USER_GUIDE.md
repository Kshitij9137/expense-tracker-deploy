# User Guide

Run commands with `python -m expense_tracker <command>` (set `PYTHONPATH=src` first). Use `--db FILE` to choose a database file (default `expenses.db`).

| Command | Example | Description |
|---|---|---|
| add | `add 12.50 food -d 2026-10-01 -n "lunch"` | Add an expense (date defaults to today) |
| list | `list -c food --start 2026-10-01 --end 2026-10-31` | List expenses, optionally filtered |
| update | `update 3 --amount 15 --note "dinner"` | Change fields of an expense |
| delete | `delete 3` | Delete an expense |
| summary | `summary --start 2026-10-01` | Totals per category and grand total |
| budget | `budget food 200` | Set or change a category budget |
| status | `status --month 2026-10` | Compare spending with budgets |
| export | `export out.csv` | Write all expenses to a CSV file |

## Troubleshooting
- `Error: Invalid amount` - use a positive number such as `12.50`.
- `Error: Invalid date` - use the format `YYYY-MM-DD`.
- `Error: No expense with id N` - run `list` to see valid ids.
- `ModuleNotFoundError: expense_tracker` - set `PYTHONPATH=src`.
