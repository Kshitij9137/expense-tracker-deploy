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
| 4 | Date-filter code duplicated in `list_expenses` and `total_by_category` | Low (maintainability) | Open: extract a `_date_filter()` helper |
| 5 | `cli.run()` is a long if/elif chain | Low | Open: replace with a dispatch dictionary of handler functions |
| 6 | Month filter uses `LIKE`; a range (`>= first day AND < next month`) is more index-friendly | Low | Open |
| 7 | No logging of operations | Low | Open: add the `logging` module with a `--verbose` flag |

## Positive observations
- Layers are clearly separated and each can be tested alone.
- Money stored as integer cents; all SQL is parameterised.
- Database constraints back up application validation.
- Good test coverage (99%) and a regression test for every bug.

## Peer review
[Add your peer review here: reviewer name, date, their comments, and what you changed in response.]
