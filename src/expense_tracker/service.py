"""Business logic layer. All SQL uses parameters to prevent SQL injection."""
import csv
import sqlite3
from typing import List, Optional

from .models import (Expense, ValidationError, clean_category, parse_date,
                     to_cents)


def _check_range(start, end):
    if start and end and parse_date(start) > parse_date(end):
        raise ValidationError("Start date must not be after end date")


def _row_to_expense(row: sqlite3.Row) -> Expense:
    return Expense(row["id"], row["amount_cents"], row["category"],
                   row["description"], row["spent_on"])


class ExpenseService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ---- create / read / update / delete -------------------------------
    def add_expense(self, amount, category, spent_on, description="") -> Expense:
        cents = to_cents(amount)
        category = clean_category(category)
        spent_on = parse_date(spent_on)
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO expenses (amount_cents, category, description, spent_on) "
                "VALUES (?, ?, ?, ?)", (cents, category, description.strip(), spent_on))
        return self.get_expense(cur.lastrowid)

    def add_many(self, items) -> int:
        """Add many (amount, category, spent_on[, description]) tuples in ONE transaction.

        All rows are validated first; if any is invalid nothing is saved. A single
        commit is about 7x faster than one commit per row (see docs/TEST_PLAN.md).
        """
        rows = []
        for item in items:
            amount, category, spent_on, *rest = item
            rows.append((to_cents(amount), clean_category(category),
                         (rest[0] if rest else "").strip(), parse_date(spent_on)))
        with self.conn:
            self.conn.executemany(
                "INSERT INTO expenses (amount_cents, category, description, spent_on) "
                "VALUES (?, ?, ?, ?)", rows)
        return len(rows)

    def get_expense(self, expense_id: int) -> Expense:
        row = self.conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
        if row is None:
            raise KeyError(f"No expense with id {expense_id}")
        return _row_to_expense(row)

    def list_expenses(self, category: Optional[str] = None, start: Optional[str] = None,
                      end: Optional[str] = None) -> List[Expense]:
        _check_range(start, end)
        sql, params = "SELECT * FROM expenses WHERE 1=1", []
        if category:
            sql += " AND category = ?"
            params.append(clean_category(category))
        if start:
            sql += " AND spent_on >= ?"
            params.append(parse_date(start))
        if end:
            sql += " AND spent_on <= ?"
            params.append(parse_date(end))
        sql += " ORDER BY spent_on DESC, id DESC"
        return [_row_to_expense(r) for r in self.conn.execute(sql, params)]

    def update_expense(self, expense_id: int, amount=None, category=None,
                       spent_on=None, description=None) -> Expense:
        if all(v is None for v in (amount, category, spent_on, description)):
            raise ValidationError("Nothing to update: give at least one of --amount, --category, --date, --note")
        current = self.get_expense(expense_id)
        cents = to_cents(amount) if amount is not None else current.amount_cents
        cat = clean_category(category) if category is not None else current.category
        day = parse_date(spent_on) if spent_on is not None else current.spent_on
        desc = description.strip() if description is not None else current.description
        with self.conn:
            self.conn.execute(
                "UPDATE expenses SET amount_cents=?, category=?, description=?, spent_on=? "
                "WHERE id=?", (cents, cat, desc, day, expense_id))
        return self.get_expense(expense_id)

    def delete_expense(self, expense_id: int) -> None:
        self.get_expense(expense_id)  # raises KeyError if missing
        with self.conn:
            self.conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))

    # ---- analysis -------------------------------------------------------
    def total_by_category(self, start=None, end=None) -> dict:
        """Return {category: total_cents} using a single aggregate query."""
        _check_range(start, end)
        sql, params = "SELECT category, SUM(amount_cents) AS total FROM expenses WHERE 1=1", []
        if start:
            sql += " AND spent_on >= ?"
            params.append(parse_date(start))
        if end:
            sql += " AND spent_on <= ?"
            params.append(parse_date(end))
        sql += " GROUP BY category ORDER BY total DESC"
        return {r["category"]: r["total"] for r in self.conn.execute(sql, params)}

    def monthly_total(self, year: int, month: int) -> int:
        prefix = f"{year:04d}-{month:02d}-%"
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) AS t FROM expenses WHERE spent_on LIKE ?",
            (prefix,)).fetchone()
        return row["t"]

    # ---- budgets ---------------------------------------------------------
    def set_budget(self, category: str, limit) -> None:
        category, cents = clean_category(category), to_cents(limit)
        with self.conn:
            self.conn.execute(
                "INSERT INTO budgets (category, limit_cents) VALUES (?, ?) "
                "ON CONFLICT(category) DO UPDATE SET limit_cents = excluded.limit_cents",
                (category, cents))

    def budget_status(self, year: int, month: int) -> list:
        """Return a list of dicts comparing monthly spending with each budget."""
        prefix = f"{year:04d}-{month:02d}-%"
        rows = self.conn.execute(
            "SELECT b.category, b.limit_cents, COALESCE(SUM(e.amount_cents), 0) AS spent "
            "FROM budgets b LEFT JOIN expenses e "
            "ON e.category = b.category AND e.spent_on LIKE ? "
            "GROUP BY b.category, b.limit_cents ORDER BY b.category", (prefix,))
        return [{"category": r["category"], "limit": r["limit_cents"], "spent": r["spent"],
                 "over": r["spent"] > r["limit_cents"]} for r in rows]

    # ---- export ----------------------------------------------------------
    def export_csv(self, path: str) -> int:
        expenses = self.list_expenses()
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["id", "date", "category", "amount", "description"])
            for e in expenses:
                writer.writerow([e.id, e.spent_on, e.category, f"{e.amount_cents / 100:.2f}", e.description])
        return len(expenses)
