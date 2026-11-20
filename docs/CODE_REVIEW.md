# Code Review

## Checklist used
| Area | Question |
|---|---|
| Correctness | Does the code do what the requirements say, including edge cases? |
| Readability | Clear names, short functions, helpful comments and docstrings? |
| Maintainability | Duplication? Single responsibility? Easy to change? |
| Error handling | Are all failure paths handled with clear messages? |
| Security | Parameterised SQL? No secrets in code? Input validated? |
| Performance | Work done in the database? Needless loops or commits? |
| Testing | Is every behaviour tested, including failures? |
| Standards | PEP 8 style, type hints, consistent naming? |

## Findings
| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | `to_cents` used a confusing one-line conditional (`... if value < Decimal("1e20") else True`) for the size check | Medium (readability) | Fixed: replaced by `if value > Decimal(MAX_CENTS) / 100` |
| 2 | Unhandled exceptions reached the user as tracebacks (see BUG-001 to BUG-005) | High | Fixed |
| 3 | One commit per inserted row is slow for bulk imports | Medium (performance) | Fixed: `add_many()` uses one transaction (about 7x faster) |
| 4 | Date-filter code duplicated in `list_expenses` and `total_by_category` | Low | **Closed (capstone):** shared `_date_clause()` used by list, count and totals (SV-09) |
| 5 | `cli.run()` is a long if/elif chain | Low | **Closed (capstone):** one handler per command in a `COMMANDS` table |
| 6 | Month filter uses `LIKE`; a date range is more index-friendly | Low | **Closed (capstone):** range queries plus a covering index; one-month total 10 ms to 0.7 ms |
| 7 | No logging | Low | **Closed (Phase 5):** structured JSON logs with request ids |

## Capstone review findings
| # | Finding | Status |
|---|---|---|
| 8 | Unbounded list endpoint | Closed (BUG-009) |
| 9 | CSV formula injection | Closed (BUG-008) |
| 10 | Dashboard race condition | Closed (BUG-010) |
| 11 | Grouped yearly query slower than 12 indexed lookups (measured 158 ms vs 95 ms; 55 ms vs 9 ms with a covering index) | Closed: `monthly_totals` uses 12 range lookups |
| 12 | Rate limiter state is per worker process | Accepted and documented (docs/SECURITY.md) |
| 13 | `web.py` is the largest module (about 360 lines) | Open: split routing into a `routes` module if it grows further |

## Positive observations
- Layers are clearly separated and each can be tested alone.
- Money stored as integer cents; all SQL is parameterised.
- Database constraints back up application validation.
- Good test coverage (99%) and a regression test for every bug.

## Peer review
[Add your peer review here: reviewer name, date, their comments, and what you changed in response.]
