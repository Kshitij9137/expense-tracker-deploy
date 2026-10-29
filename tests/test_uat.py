"""User acceptance tests (UAT): realistic user stories checked from the user's point of view."""
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from expense_tracker.cli import run


class UserAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "uat.db")

    def tearDown(self):
        self.tmp.cleanup()

    def do(self, *argv):
        out = io.StringIO()
        code = run(["--db", self.db, *argv], out=out)
        return code, out.getvalue()

    def test_uat01_student_tracks_a_week(self):
        """UAT-01 As a student, I log a week of spending and see where my money went"""
        for amount, cat, day in [("3.50", "food", "01"), ("12", "food", "02"),
                                 ("45", "books", "03"), ("20", "transport", "04")]:
            self.assertEqual(self.do("add", amount, cat, "-d", f"2026-10-{day}")[0], 0)
        _, out = self.do("summary")
        self.assertIn("books", out)
        self.assertIn("15.50", out)       # food total
        self.assertIn("80.50", out)       # grand total
        first_line = out.splitlines()[0]
        self.assertIn("books", first_line)  # biggest category listed first

    def test_uat02_budget_warning(self):
        """UAT-02 As a user, I get a clear warning when I overspend a budget"""
        self.do("budget", "food", "50")
        self.do("add", "30", "food", "-d", "2026-10-01")
        _, out = self.do("status", "--month", "2026-10")
        self.assertIn("ok", out)
        self.do("add", "25", "food", "-d", "2026-10-05")
        _, out = self.do("status", "--month", "2026-10")
        self.assertIn("OVER BUDGET", out)

    def test_uat03_fix_a_mistake(self):
        """UAT-03 As a user, I can correct a wrongly entered amount and category"""
        self.do("add", "100", "fod", "-d", "2026-10-01")
        self.assertEqual(self.do("update", "1", "--amount", "10", "--category", "food")[0], 0)
        _, out = self.do("list")
        self.assertIn("10.00", out)
        self.assertIn("food", out)
        self.assertNotIn("fod", out)

    def test_uat04_look_at_one_month(self):
        """UAT-04 As a user, I can look at just one month of spending"""
        self.do("add", "10", "food", "-d", "2026-09-30")
        self.do("add", "20", "food", "-d", "2026-10-01")
        _, out = self.do("list", "--start", "2026-10-01", "--end", "2026-10-31")
        self.assertIn("20.00", out)
        self.assertNotIn("10.00", out)

    def test_uat05_helpful_errors(self):
        """UAT-05 As a user, mistakes give me a message that tells me how to fix them"""
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.do("add", "5", "food", "-d", "10/01/2026")
            self.do("status", "--month", "October")
        text = err.getvalue()
        self.assertIn("YYYY-MM-DD", text)
        self.assertIn("YYYY-MM", text)

    def test_uat06_delete_removes_from_totals(self):
        """UAT-06 As a user, deleting an expense removes it from my totals"""
        self.do("add", "40", "fun", "-d", "2026-10-01")
        self.do("delete", "1")
        _, out = self.do("summary")
        self.assertIn("0.00", out)
        self.assertNotIn("fun", out)


if __name__ == "__main__":
    unittest.main()
