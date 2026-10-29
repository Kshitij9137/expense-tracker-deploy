"""Edge-case and error-handling tests (EC)."""
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from expense_tracker.cli import run
from expense_tracker.database import connect
from expense_tracker.models import ValidationError
from expense_tracker.service import ExpenseService


class EdgeCaseTests(unittest.TestCase):
    def setUp(self):
        self.svc = ExpenseService(connect(":memory:"))

    def test_ec01_empty_database(self):
        """EC-01 Empty database: list, totals and monthly total are empty or zero"""
        self.assertEqual(self.svc.list_expenses(), [])
        self.assertEqual(self.svc.total_by_category(), {})
        self.assertEqual(self.svc.monthly_total(2026, 10), 0)
        self.assertEqual(self.svc.budget_status(2026, 10), [])

    def test_ec02_unicode_and_long_description(self):
        """EC-02 Unicode text and a very long description are stored intact"""
        text = "café ☕ चाय " + "x" * 5000
        e = self.svc.add_expense("3", "food", "2026-10-01", text)
        self.assertEqual(self.svc.get_expense(e.id).description, text.strip())

    def test_ec03_same_day_ordering(self):
        """EC-03 Expenses on the same day are listed newest id first"""
        a = self.svc.add_expense("1", "a", "2026-10-01")
        b = self.svc.add_expense("2", "a", "2026-10-01")
        self.assertEqual([e.id for e in self.svc.list_expenses()], [b.id, a.id])

    def test_ec04_date_boundaries_inclusive(self):
        """EC-04 Start and end dates are inclusive"""
        self.svc.add_expense("1", "a", "2026-10-01")
        self.svc.add_expense("1", "a", "2026-10-31")
        self.assertEqual(len(self.svc.list_expenses(start="2026-10-01", end="2026-10-31")), 2)

    def test_ec05_leap_day(self):
        """EC-05 Leap day 29 February is accepted in a leap year only"""
        self.svc.add_expense("1", "a", "2028-02-29")
        with self.assertRaises(ValidationError):
            self.svc.add_expense("1", "a", "2027-02-29")

    def test_ec06_category_case_insensitive(self):
        """EC-06 Categories differing only by case are treated as one"""
        self.svc.add_expense("1", "Food", "2026-10-01")
        self.svc.add_expense("1", "FOOD", "2026-10-01")
        self.assertEqual(self.svc.total_by_category(), {"food": 200})

    def test_ec07_large_total_exact(self):
        """EC-07 Summing many large values stays exact"""
        for _ in range(100):
            self.svc.add_expense("9999999999.99", "big", "2026-10-01")
        self.assertEqual(self.svc.total_by_category()["big"], 100 * 999999999999)

    def test_ec08_budget_with_no_spending(self):
        """EC-08 A budget with no spending shows 0 spent and is not over"""
        self.svc.set_budget("food", "10")
        status = self.svc.budget_status(2026, 10)[0]
        self.assertEqual((status["spent"], status["over"]), (0, False))

    def test_ec09_budget_exactly_met_not_over(self):
        """EC-09 Spending exactly equal to the budget is not over budget"""
        self.svc.set_budget("food", "10")
        self.svc.add_expense("10", "food", "2026-10-01")
        self.assertFalse(self.svc.budget_status(2026, 10)[0]["over"])

    def test_ec10_update_nothing_rejected(self):
        """EC-10 Update with no fields is rejected"""
        e = self.svc.add_expense("1", "a", "2026-10-01")
        with self.assertRaises(ValidationError):
            self.svc.update_expense(e.id)

    def test_ec11_update_missing_id(self):
        """EC-11 Updating a missing id raises KeyError"""
        with self.assertRaises(KeyError):
            self.svc.update_expense(123, amount="5")

    def test_ec12_reversed_date_range(self):
        """EC-12 A start date after the end date is rejected"""
        with self.assertRaises(ValidationError):
            self.svc.list_expenses(start="2026-12-01", end="2026-01-01")
        with self.assertRaises(ValidationError):
            self.svc.total_by_category(start="2026-12-01", end="2026-01-01")

    def test_ec13_export_empty_and_bad_path(self):
        """EC-13 Export of an empty database works; an unwritable path raises OSError"""
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.svc.export_csv(os.path.join(d, "e.csv")), 0)
        with self.assertRaises(OSError):
            self.svc.export_csv("/nonexistent_dir/x.csv")

    def test_ec14_database_check_constraint(self):
        """EC-14 The database itself refuses a zero amount (second safeguard)"""
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.svc.conn.execute(
                "INSERT INTO expenses (amount_cents, category, spent_on) VALUES (0, 'a', '2026-10-01')")


class CliErrorHandlingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "t.db")

    def tearDown(self):
        self.tmp.cleanup()

    def code(self, *argv):
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = run(["--db", self.db, *argv], out=io.StringIO())
        return code, err.getvalue()

    def test_ec15_cli_never_shows_traceback(self):
        """EC-15 Bad input never produces a Python traceback, only 'Error: ...'"""
        cases = [("add", "1e400", "food"), ("add", "0.004", "food"), ("add", "abc", "food"),
                 ("status", "--month", "abc"), ("status", "--month", "2026-13"),
                 ("export", "/nonexistent_dir/o.csv"), ("update", "1"),
                 ("list", "--start", "2026-12-01", "--end", "2026-01-01"),
                 ("budget", "food", "1e400"), ("delete", "999")]
        for argv in cases:
            code, err = self.code(*argv)
            self.assertEqual(code, 1, msg=str(argv))
            self.assertTrue(err.startswith("Error:"), msg=f"{argv}: {err!r}")
            self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()


class BulkAndRangeTests(unittest.TestCase):
    def setUp(self):
        self.svc = ExpenseService(connect(":memory:"))

    def test_ec16_add_many_is_all_or_nothing(self):
        """EC-16 add_many saves every row, or none if any row is invalid"""
        good = [("1", "a", "2026-10-01"), ("2", "b", "2026-10-02", "note")]
        self.assertEqual(self.svc.add_many(good), 2)
        with self.assertRaises(ValidationError):
            self.svc.add_many([("5", "a", "2026-10-01"), ("bad", "a", "2026-10-01")])
        self.assertEqual(len(self.svc.list_expenses()), 2)

    def test_ec17_total_by_category_date_range(self):
        """EC-17 total_by_category respects start and end dates"""
        self.svc.add_many([("10", "a", "2026-09-30"), ("20", "a", "2026-10-15"),
                           ("30", "a", "2026-11-01")])
        self.assertEqual(self.svc.total_by_category(start="2026-10-01", end="2026-10-31"), {"a": 2000})
        self.assertEqual(self.svc.total_by_category(start="2026-10-16"), {"a": 3000})
        self.assertEqual(self.svc.total_by_category(end="2026-10-01"), {"a": 1000})
