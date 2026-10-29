# Test Plan - Expense Tracker

## 1. Purpose and scope
Show that the Expense Tracker is correct, robust and reliable. In scope: input validation, CRUD, filtering, analysis, budgets, CSV export, CLI behaviour, error handling, persistence and performance. Out of scope: GUI (none exists), multi-user concurrency, network features.

## 2. Test levels
| Level | Prefix | Question answered | File(s) | Count |
|---|---|---|---|---|
| Unit | UT | Does each function work in isolation? | `tests/test_models.py` | 13 |
| Integration | IT | Do layers share data correctly (CLI -> service -> SQLite)? | `tests/test_service.py`, `tests/test_cli.py` | 15 |
| System | ST | Does the whole program work as a separate process? | `tests/test_system.py` | 6 |
| User acceptance | UAT | Can a user complete real tasks? | `tests/test_uat.py` | 6 |
| Edge case / error | EC | Does it cope with unusual or hostile input? | `tests/test_edge_cases.py` | 17 |
| Regression | REG | Do fixed bugs stay fixed? | `tests/test_regression.py` | 7 |
| **Total** | | | | **64** |

## 3. Techniques used
- **Boundary value analysis**: 0.01 and 10,000,000,000.00 accepted; 0.004 and 10,000,000,000.01 rejected; category length 30 vs 31; leap day.
- **Equivalence partitioning**: valid / non-numeric / zero / negative / non-finite amounts.
- **Error guessing**: SQL injection text, `NaN`, `1e400`, unicode, 5,000-character descriptions, unwritable export path.
- **Exploratory testing**: running the program by hand with odd input; this found BUG-001 to BUG-007.
- **State and persistence testing**: data must survive separate process runs.

## 4. Tools
| Tool | Use |
|---|---|
| unittest | Test framework |
| coverage.py (`--branch`) | Statement and branch coverage |
| cProfile / time.perf_counter | Performance analysis |
| `tools/generate_test_report.py` | Produces `docs/TEST_RESULTS.md` |
| Python traceback + `python -m pdb` | Debugging failures |

## 5. How to run
```bash
export PYTHONPATH=src
python -m unittest discover -s tests -v                 # run all tests
coverage run --branch --source=src/expense_tracker -m unittest discover -s tests
coverage report -m                                      # coverage summary
python tools/generate_test_report.py                    # refresh docs/TEST_RESULTS.md
```

## 6. Entry and exit criteria
- Entry: code compiles and basic smoke test (`add`, `list`) works.
- Exit: 100% of tests pass, no open critical/high bugs, coverage of at least 90%.

## 7. Results summary
- 64 of 64 tests pass (see `docs/TEST_RESULTS.md`).
- Coverage: 99% (237 statements, 56 branches). Uncovered: `__main__.py` and `main()`, which run in a separate process in system tests so coverage.py does not count them.
- 7 bugs found and fixed (see `docs/BUG_LOG.md`); each has a regression test.
- Performance: 5,000 single inserts 0.12 s vs 0.016 s in one transaction (about 7x faster) - implemented as `add_many()`.

## 8. Known issues and limitations
1. Multi-process concurrent writes were not tested.
2. Tested on Linux with Python 3.12 only; Windows and macOS not tested here.
3. Amounts support 2 decimal places only; extra digits are rounded.
4. Month filters use `LIKE 'YYYY-MM-%'`; a date-range query would be more index-friendly (see `docs/CODE_REVIEW.md`).
5. `list_expenses` and `total_by_category` contain duplicated date-filter code (technical debt).

## 9. Phase 5 additions (deployable release v1.1.0)
| Level | Prefix | File | Count |
|---|---|---|---|
| Web/API | WT | `tests/test_web.py` | 15 |
| Configuration | CF | `tests/test_web.py` | 5 |
| Operations (backup/restore) | OP | `tests/test_web.py` | 5 |

Total is now **89 tests, all passing; branch coverage 94%** (`wsgi.py`, `__main__.py` and the development server `main()` run in separate processes and are verified by the smoke test and CF-05 instead). The CI pipeline fails below 90% coverage.
Post-deployment verification is automated by `scripts/smoke_test.py`; load behaviour by `scripts/loadtest.py`.
