"""Integration tests (IT): service layer working with a real SQLite database."""
import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from expense_tracker.database import connect
from expense_tracker.models import ValidationError, to_cents
from expense_tracker.service import ExpenseService


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.svc = ExpenseService(connect(":memory:"))

    # --- validation / edge cases
    def test_money_uses_cents_without_float_errors(self):
        """IT-01 Service stores money as exact cents"""
        self.assertEqual(to_cents("0.10") + to_cents("0.20"), 30)
        self.assertEqual(to_cents(19.99), 1999)

    def test_invalid_amounts_rejected(self):
        """IT-02 Service never stores invalid amounts"""
        for bad in ("abc", "-5", "0", "", "NaN", "inf"):
            with self.assertRaises(ValidationError, msg=bad):
                to_cents(bad)

    def test_invalid_date_and_category_rejected(self):
        """IT-03 Service rejects invalid date and category"""
        with self.assertRaises(ValidationError):
            self.svc.add_expense("5", "food", "2026-13-40")
        with self.assertRaises(ValidationError):
            self.svc.add_expense("5", "   ", "2026-10-01")

    def test_sql_injection_is_harmless(self):
        """IT-04 SQL injection text is stored as plain data"""
        self.svc.add_expense("5", "food'; DROP TABLE expenses;--", "2026-10-01")
        self.assertEqual(len(self.svc.list_expenses()), 1)

    # --- CRUD
    def test_add_get_update_delete(self):
        """IT-05 Create, read, update and delete round trip"""
        e = self.svc.add_expense("12.50", "Food", "2026-10-02", " lunch ")
        self.assertEqual((e.amount_cents, e.category, e.description), (1250, "food", "lunch"))
        u = self.svc.update_expense(e.id, amount="15", description="dinner")
        self.assertEqual((u.amount_cents, u.description), (1500, "dinner"))
        self.svc.delete_expense(e.id)
        with self.assertRaises(KeyError):
            self.svc.get_expense(e.id)

    def test_delete_missing_raises(self):
        """IT-06 Deleting a missing expense raises KeyError"""
        with self.assertRaises(KeyError):
            self.svc.delete_expense(999)

    # --- filtering and analysis
    def _seed(self):
        self.svc.add_expense("10", "food", "2026-10-01")
        self.svc.add_expense("20", "food", "2026-10-15")
        self.svc.add_expense("50", "travel", "2026-10-20")
        self.svc.add_expense("30", "food", "2026-09-30")

    def test_filters(self):
        """IT-07 Category and date filters return correct rows"""
        self._seed()
        self.assertEqual(len(self.svc.list_expenses(category="food")), 3)
        self.assertEqual(len(self.svc.list_expenses(start="2026-10-01", end="2026-10-31")), 3)

    def test_totals_and_monthly(self):
        """IT-08 Totals per category and monthly totals are correct"""
        self._seed()
        self.assertEqual(self.svc.total_by_category(), {"food": 6000, "travel": 5000})
        self.assertEqual(self.svc.monthly_total(2026, 10), 8000)
        self.assertEqual(self.svc.monthly_total(2020, 1), 0)

    def test_budget_status(self):
        """IT-09 Budget status flags over-budget categories"""
        self._seed()
        self.svc.set_budget("food", "25")
        self.svc.set_budget("travel", "100")
        status = {s["category"]: s for s in self.svc.budget_status(2026, 10)}
        self.assertTrue(status["food"]["over"])
        self.assertFalse(status["travel"]["over"])

    def test_budget_update_overwrites(self):
        """IT-10 Setting a budget twice overwrites the first"""
        self.svc.set_budget("food", "10")
        self.svc.set_budget("food", "99")
        self.assertEqual(self.svc.budget_status(2026, 10)[0]["limit"], 9900)

    def test_export_csv(self):
        """IT-11 CSV export writes header plus all rows"""
        self._seed()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.csv")
            self.assertEqual(self.svc.export_csv(path), 4)
            with open(path, newline="") as fh:
                self.assertEqual(len(list(csv.reader(fh))), 5)  # header + 4


if __name__ == "__main__":
    unittest.main()
