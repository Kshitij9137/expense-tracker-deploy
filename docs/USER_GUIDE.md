# User Guide

## Web dashboard (recommended)
1. Open the service address in your browser and enter your **API key**. The key stays in this tab only; closing the tab signs you out.
2. **Dashboard**: spending for the chosen month (change it with the Month picker at the top), change versus last month, top category, daily average, largest expense, a 12-month chart and a breakdown by category.
3. **Expenses**: add an expense (amount, category, date, optional note). Use *Edit* or *Delete* on any row. Filter by category and dates, and page through results with Previous and Next.
4. **Budgets**: set a monthly limit per category. A bar shows how much is used, and **OVER BUDGET** appears when you pass the limit.
5. **Export CSV** downloads every expense as a spreadsheet file. Text that could be mistaken for a formula is made safe.
6. **Sign out** when you finish on a shared computer.
Messages appear at the bottom of the screen. If you see "Too many failed attempts", wait the number of seconds shown and then try the correct key.

## Command line
Run `python -m expense_tracker <command>` with `PYTHONPATH=src`. Use `--db FILE` to choose a database (default `expenses.db`).

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
| Message or symptom | What to do |
|---|---|
| `Error: Invalid amount` | Use a positive number with at most two decimals, for example `12.50` |
| `Error: Invalid date` / `Invalid month` | Use `YYYY-MM-DD` / `YYYY-MM` |
| `Error: No expense with id N` | Refresh the list to see valid ids |
| "That API key is not valid" | Check which environment you are using (staging and production have different keys) |
| Page loads slowly the first time | The free hosting plan was asleep; wait up to a minute |
| Data missing after a restart | Free hosting has no permanent disk; see docs/DEPLOYMENT.md |
