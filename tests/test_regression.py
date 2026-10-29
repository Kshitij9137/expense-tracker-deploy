"""Regression tests (REG): one test for every bug found during QA, so it can never return."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from expense_tracker.database import connect
from expense_tracker.models import ValidationError, parse_month, to_cents
from expense_tracker.service import ExpenseService


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.svc = ExpenseService(connect(":memory:"))

    def test_reg01_bug001_huge_exponent_amount(self):
        """REG-01 BUG-001: amount 1e400 crashed with decimal.InvalidOperation"""
        with self.assertRaises(ValidationError):
            to_cents("1e400")

    def test_reg02_bug002_sub_cent_amount(self):
        """REG-02 BUG-002: amount 0.004 rounded to 0 and crashed with sqlite IntegrityError"""
        with self.assertRaises(ValidationError):
            self.svc.add_expense("0.004", "food", "2026-10-01")
        self.assertEqual(self.svc.list_expenses(), [])

    def test_reg03_bug003_integer_overflow(self):
        """REG-03 BUG-003: a 20-digit amount crashed with OverflowError"""
        with self.assertRaises(ValidationError):
            self.svc.add_expense("99999999999999999999", "food", "2026-10-01")

    def test_reg04_bug004_invalid_month(self):
        """REG-04 BUG-004: --month abc crashed; --month 2026-13 was silently accepted"""
        with self.assertRaises(ValidationError):
            parse_month("abc")
        with self.assertRaises(ValidationError):
            parse_month("2026-13")

    def test_reg05_bug005_export_unwritable_path(self):
        """REG-05 BUG-005: export to a missing folder showed a traceback"""
        from test_edge_cases import CliErrorHandlingTests  # reuse CLI harness
        t = CliErrorHandlingTests("test_ec15_cli_never_shows_traceback")
        t.setUp()
        try:
            code, err = t.code("export", "/nonexistent_dir/o.csv")
            self.assertEqual(code, 1)
            self.assertNotIn("Traceback", err)
        finally:
            t.tearDown()

    def test_reg06_bug006_update_with_no_changes(self):
        """REG-06 BUG-006: update with no fields printed 'Updated' although nothing changed"""
        e = self.svc.add_expense("1", "a", "2026-10-01")
        with self.assertRaises(ValidationError):
            self.svc.update_expense(e.id)

    def test_reg07_bug007_reversed_date_range(self):
        """REG-07 BUG-007: start date after end date silently returned 'No expenses found'"""
        with self.assertRaises(ValidationError):
            self.svc.list_expenses(start="2026-12-01", end="2026-01-01")


if __name__ == "__main__":
    unittest.main()
