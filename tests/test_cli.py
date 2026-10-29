"""Integration tests (IT): CLI -> service -> SQLite file, called in-process."""
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from expense_tracker.cli import run


class CliIntegrationTests(unittest.TestCase):
    """Integration tests: CLI -> service -> real SQLite file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "t.db")

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *argv):
        out = io.StringIO()
        code = run(["--db", self.db, *argv], out=out)
        return code, out.getvalue()

    def test_full_workflow(self):
        """IT-12 Full CLI workflow: add, list, summary, budget, status, delete"""
        self.assertEqual(self.cli("add", "12.50", "food", "-d", "2026-10-01", "-n", "lunch")[0], 0)
        self.assertEqual(self.cli("add", "40", "travel", "-d", "2026-10-02")[0], 0)
        code, out = self.cli("list", "-c", "food")
        self.assertIn("12.50", out)
        self.assertNotIn("travel", out)
        code, out = self.cli("summary")
        self.assertIn("TOTAL", out)
        self.assertIn("52.50", out)
        self.cli("budget", "food", "10")
        code, out = self.cli("status", "--month", "2026-10")
        self.assertIn("OVER BUDGET", out)
        self.assertEqual(self.cli("delete", "1")[0], 0)
        self.assertIn("No expenses", self.cli("list", "-c", "food")[1])

    def test_errors_return_nonzero(self):
        """IT-13 CLI returns exit code 1 for bad amount, missing id and bad date"""
        self.assertEqual(self.cli("add", "abc", "food")[0], 1)
        self.assertEqual(self.cli("delete", "42")[0], 1)
        self.assertEqual(self.cli("add", "5", "food", "-d", "bad-date")[0], 1)


if __name__ == "__main__":
    unittest.main()


class CliExtraTests(CliIntegrationTests):
    def test_it14_update_and_export_commands(self):
        """IT-14 CLI update and export commands work and print confirmations"""
        self.cli("add", "5", "food", "-d", "2026-10-01")
        code, out = self.cli("update", "1", "--amount", "9", "--note", "changed")
        self.assertEqual((code, out.strip()), (0, "Updated #1"))
        path = os.path.join(self.tmp.name, "o.csv")
        code, out = self.cli("export", path)
        self.assertIn("Exported 1", out)
        self.assertTrue(os.path.exists(path))
        with open(path) as fh:
            self.assertIn("9.00", fh.read())

    def test_it15_summary_with_range_and_budget_status_default(self):
        """IT-15 CLI summary accepts a date range; status works with default month"""
        self.cli("add", "5", "food", "-d", "2026-10-01")
        code, out = self.cli("summary", "--start", "2026-10-01", "--end", "2026-10-31")
        self.assertIn("5.00", out)
        self.cli("budget", "food", "10")
        self.assertEqual(self.cli("status")[0], 0)

    test_full_workflow = None          # inherited tests already run in the parent class
    test_errors_return_nonzero = None
