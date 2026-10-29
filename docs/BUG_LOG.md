# Bug Log

Found by exploratory testing and edge-case analysis. Every bug is fixed and has a regression test.

| ID | Severity | Steps to reproduce | Actual result (before) | Expected result | Root cause | Fix | Regression test |
|---|---|---|---|---|---|---|---|
| BUG-001 | High | `add 1e400 food` | Crash: `decimal.InvalidOperation` traceback | Clear error message | Huge exponent overflowed Decimal arithmetic | Compare with the maximum before multiplying | REG-01 |
| BUG-002 | High | `add 0.004 food` | Crash: `sqlite3.IntegrityError: CHECK constraint failed` | Clear error message | Amount rounded to 0 cents, violating the DB constraint | Reject amounts below 0.01 in `to_cents` | REG-02 |
| BUG-003 | High | `add 99999999999999999999 food` | Crash: `OverflowError: Python int too large to convert to SQLite INTEGER` | Clear error message | No upper limit on amount | Add `MAX_CENTS` (10,000,000,000.00) | REG-03 |
| BUG-004 | Medium | `status --month abc` / `--month 2026-13` | `abc`: ValueError traceback; `2026-13`: silently accepted, empty result | Clear error message for both | Month parsed with bare `int()` and no range check | New validated `parse_month()` | REG-04 |
| BUG-005 | Medium | `export /nonexistent_dir/o.csv` | Crash: `FileNotFoundError` traceback | Clear error message | OSError not handled in the CLI | Catch `OSError`, print `Error: file problem - ...`, exit 1 | REG-05 |
| BUG-006 | Low | `update 1` (no options) | Printed "Updated #1" although nothing changed | Error explaining what to provide | No check that at least one field was given | Raise `ValidationError` | REG-06 |
| BUG-007 | Low | `list --start 2026-12-01 --end 2026-01-01` | "No expenses found." (misleading) | Error: start after end | Reversed ranges not validated | `_check_range()` helper | REG-07 |

## Debugging approach
1. Reproduce the failure with the exact command.
2. Read the traceback from the bottom up to find the failing line.
3. Print or inspect values at that point (`python -m pdb`, `print()`, `Decimal` and `sqlite3` interactive checks).
4. Find the root cause, not just the symptom.
5. Fix it, write a regression test that fails before the fix and passes after, then re-run the whole suite.
