# Test Results

Generated: 2026-10-28  
Total: 89  |  Passed: 89  |  Failed: 0  |  Time: 0.96s

| ID | Test case | Result | File |
|---|---|---|---|
| CF-01 | Defaults are valid for development | PASS | test_web.py |
| CF-02 | Staging and production refuse to start without a strong API key | PASS | test_web.py |
| CF-03 | Invalid APP_ENV, LOG_LEVEL, DB_PATH and MAX_BODY_BYTES are rejected | PASS | test_web.py |
| CF-04 | Environment values are trimmed and case-normalised | PASS | test_web.py |
| CF-05 | The production entry point exits with code 3 and a clear message when misconfigured | PASS | test_web.py |
| EC-01 | Empty database: list, totals and monthly total are empty or zero | PASS | test_edge_cases.py |
| EC-02 | Unicode text and a very long description are stored intact | PASS | test_edge_cases.py |
| EC-03 | Expenses on the same day are listed newest id first | PASS | test_edge_cases.py |
| EC-04 | Start and end dates are inclusive | PASS | test_edge_cases.py |
| EC-05 | Leap day 29 February is accepted in a leap year only | PASS | test_edge_cases.py |
| EC-06 | Categories differing only by case are treated as one | PASS | test_edge_cases.py |
| EC-07 | Summing many large values stays exact | PASS | test_edge_cases.py |
| EC-08 | A budget with no spending shows 0 spent and is not over | PASS | test_edge_cases.py |
| EC-09 | Spending exactly equal to the budget is not over budget | PASS | test_edge_cases.py |
| EC-10 | Update with no fields is rejected | PASS | test_edge_cases.py |
| EC-11 | Updating a missing id raises KeyError | PASS | test_edge_cases.py |
| EC-12 | A start date after the end date is rejected | PASS | test_edge_cases.py |
| EC-13 | Export of an empty database works; an unwritable path raises OSError | PASS | test_edge_cases.py |
| EC-14 | The database itself refuses a zero amount (second safeguard) | PASS | test_edge_cases.py |
| EC-15 | Bad input never produces a Python traceback, only 'Error: ...' | PASS | test_edge_cases.py |
| EC-16 | add_many saves every row, or none if any row is invalid | PASS | test_edge_cases.py |
| EC-17 | total_by_category respects start and end dates | PASS | test_edge_cases.py |
| IT-01 | Service stores money as exact cents | PASS | test_service.py |
| IT-02 | Service never stores invalid amounts | PASS | test_service.py |
| IT-03 | Service rejects invalid date and category | PASS | test_service.py |
| IT-04 | SQL injection text is stored as plain data | PASS | test_service.py |
| IT-05 | Create, read, update and delete round trip | PASS | test_service.py |
| IT-06 | Deleting a missing expense raises KeyError | PASS | test_service.py |
| IT-07 | Category and date filters return correct rows | PASS | test_service.py |
| IT-08 | Totals per category and monthly totals are correct | PASS | test_service.py |
| IT-09 | Budget status flags over-budget categories | PASS | test_service.py |
| IT-10 | Setting a budget twice overwrites the first | PASS | test_service.py |
| IT-11 | CSV export writes header plus all rows | PASS | test_service.py |
| IT-12 | Full CLI workflow: add, list, summary, budget, status, delete | PASS | test_cli.py |
| IT-13 | CLI returns exit code 1 for bad amount, missing id and bad date | PASS | test_cli.py |
| IT-14 | CLI update and export commands work and print confirmations | PASS | test_cli.py |
| IT-15 | CLI summary accepts a date range; status works with default month | PASS | test_cli.py |
| OP-01 | Backup creates a complete, integrity-checked copy | PASS | test_web.py |
| OP-02 | Backup retention keeps only the newest N files | PASS | test_web.py |
| OP-03 | Restore brings back deleted data and saves the previous database | PASS | test_web.py |
| OP-04 | Backup of a missing database and restore of a corrupt backup fail safely | PASS | test_web.py |
| OP-05 | The ops command line backs up, checks and restores, with exit codes | PASS | test_web.py |
| REG-01 | BUG-001: amount 1e400 crashed with decimal.InvalidOperation | PASS | test_regression.py |
| REG-02 | BUG-002: amount 0.004 rounded to 0 and crashed with sqlite IntegrityError | PASS | test_regression.py |
| REG-03 | BUG-003: a 20-digit amount crashed with OverflowError | PASS | test_regression.py |
| REG-04 | BUG-004: --month abc crashed; --month 2026-13 was silently accepted | PASS | test_regression.py |
| REG-05 | BUG-005: export to a missing folder showed a traceback | PASS | test_regression.py |
| REG-06 | BUG-006: update with no fields printed 'Updated' although nothing changed | PASS | test_regression.py |
| REG-07 | BUG-007: start date after end date silently returned 'No expenses found' | PASS | test_regression.py |
| ST-01 | --help and --version work and exit with code 0 | PASS | test_system.py |
| ST-02 | Running with no command prints usage and exits non-zero | PASS | test_system.py |
| ST-03 | Data saved by one process is visible to the next process | PASS | test_system.py |
| ST-04 | Add expenses, export to CSV, and verify the CSV file | PASS | test_system.py |
| ST-05 | Errors are written to stderr, nothing on stdout, exit code 1 | PASS | test_system.py |
| ST-06 | Different --db files do not share data | PASS | test_system.py |
| UAT-01 | As a student, I log a week of spending and see where my money went | PASS | test_uat.py |
| UAT-02 | As a user, I get a clear warning when I overspend a budget | PASS | test_uat.py |
| UAT-03 | As a user, I can correct a wrongly entered amount and category | PASS | test_uat.py |
| UAT-04 | As a user, I can look at just one month of spending | PASS | test_uat.py |
| UAT-05 | As a user, mistakes give me a message that tells me how to fix them | PASS | test_uat.py |
| UAT-06 | As a user, deleting an expense removes it from my totals | PASS | test_uat.py |
| UT-01 | to_cents converts whole and decimal amounts exactly | PASS | test_models.py |
| UT-02 | to_cents avoids floating point drift (0.10 + 0.20 == 0.30) | PASS | test_models.py |
| UT-03 | to_cents rejects non-numeric text | PASS | test_models.py |
| UT-04 | to_cents rejects zero, negative, NaN and infinity | PASS | test_models.py |
| UT-05 | to_cents accepts the smallest and largest valid amounts | PASS | test_models.py |
| UT-06 | to_cents rejects values below 0.01 and above the maximum | PASS | test_models.py |
| UT-07 | parse_date accepts valid ISO dates including leap day | PASS | test_models.py |
| UT-08 | parse_date rejects impossible and malformed dates | PASS | test_models.py |
| UT-09 | parse_month returns (year, month) | PASS | test_models.py |
| UT-10 | parse_month rejects bad months and formats | PASS | test_models.py |
| UT-11 | clean_category trims and lowercases | PASS | test_models.py |
| UT-12 | clean_category rejects empty and over-long names | PASS | test_models.py |
| UT-13 | format_money shows two decimals and thousands separators | PASS | test_models.py |
| WT-01 | /health is public and reports status, version and environment | PASS | test_web.py |
| WT-02 | API endpoints return 401 without a key or with a wrong key | PASS | test_web.py |
| WT-03 | Create, list, fetch and delete an expense through the API | PASS | test_web.py |
| WT-04 | Invalid amount, date or category returns 400 with a clear message | PASS | test_web.py |
| WT-05 | Malformed JSON and non-object JSON return 400 | PASS | test_web.py |
| WT-06 | A request body above the limit is refused with 413 | PASS | test_web.py |
| WT-07 | Unknown paths return 404 and wrong methods return 405 | PASS | test_web.py |
| WT-08 | Summary and date filters work through the API | PASS | test_web.py |
| WT-09 | Responses carry security headers and a request id (echoed if supplied) | PASS | test_web.py |
| WT-10 | An unexpected server error returns a generic 500 and logs the details | PASS | test_web.py |
| WT-11 | /metrics exposes request counters and the expense count | PASS | test_web.py |
| WT-12 | SQL injection text sent through the API is stored harmlessly | PASS | test_web.py |
| WT-13 | Data survives an application restart (new app instance, same database file) | PASS | test_web.py |
| WT-14 | Each request is logged as one JSON line with request id, status and duration | PASS | test_web.py |
| WT-15 | In development without a key the API is open (with a logged warning) | PASS | test_web.py |
