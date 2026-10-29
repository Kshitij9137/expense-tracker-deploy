"""System tests (ST): the whole application run as a real separate process."""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
ENV = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))


class SystemTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "sys.db")

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *argv):
        p = subprocess.run([sys.executable, "-m", "expense_tracker", "--db", self.db, *argv],
                           capture_output=True, text=True, env=ENV, cwd=ROOT)
        return p.returncode, p.stdout, p.stderr

    def test_st01_help_and_version(self):
        """ST-01 --help and --version work and exit with code 0"""
        code, out, _ = self.cli("--help")
        self.assertEqual(code, 0)
        self.assertIn("usage", out.lower())
        code, out, _ = self.cli("--version")
        self.assertEqual((code, out.strip()), (0, "1.1.0"))

    def test_st02_missing_command(self):
        """ST-02 Running with no command prints usage and exits non-zero"""
        code, _, err = self.cli()
        self.assertNotEqual(code, 0)
        self.assertIn("usage", err.lower())

    def test_st03_data_persists_between_runs(self):
        """ST-03 Data saved by one process is visible to the next process"""
        self.cli("add", "7.25", "food", "-d", "2026-10-01", "-n", "snack")
        code, out, _ = self.cli("list")
        self.assertEqual(code, 0)
        self.assertIn("7.25", out)
        self.assertIn("snack", out)
        self.assertTrue(os.path.exists(self.db))

    def test_st04_end_to_end_with_csv_export(self):
        """ST-04 Add expenses, export to CSV, and verify the CSV file"""
        self.cli("add", "10", "food", "-d", "2026-10-01")
        self.cli("add", "20", "travel", "-d", "2026-10-02")
        path = os.path.join(self.tmp.name, "out.csv")
        code, out, _ = self.cli("export", path)
        self.assertEqual(code, 0)
        self.assertIn("Exported 2", out)
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().strip().splitlines()
        self.assertEqual(lines[0], "id,date,category,amount,description")
        self.assertEqual(len(lines), 3)

    def test_st05_errors_go_to_stderr(self):
        """ST-05 Errors are written to stderr, nothing on stdout, exit code 1"""
        code, out, err = self.cli("add", "abc", "food")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("Error: Invalid amount", err)

    def test_st06_two_databases_are_independent(self):
        """ST-06 Different --db files do not share data"""
        self.cli("add", "5", "food", "-d", "2026-10-01")
        other = os.path.join(self.tmp.name, "other.db")
        p = subprocess.run([sys.executable, "-m", "expense_tracker", "--db", other, "list"],
                           capture_output=True, text=True, env=ENV, cwd=ROOT)
        self.assertIn("No expenses found", p.stdout)


if __name__ == "__main__":
    unittest.main()
