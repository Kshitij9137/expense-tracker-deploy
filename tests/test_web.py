"""Web/API tests (WT), configuration tests (CF) and operations tests (OP) for the deployable release."""
import io
import json
import logging
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from expense_tracker import ops
from expense_tracker.config import ConfigError, Settings
from expense_tracker.web import create_app

KEY = "test-api-key-1234567890"


class WebBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "web.db")
        self.app = create_app(Settings("staging", self.db, "ERROR", KEY, 1000))

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, method, path, body=None, key=KEY, raw=None, headers=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else b"")
        path, _, query = path.partition("?")
        environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query,
                   "CONTENT_LENGTH": str(len(data)), "wsgi.input": io.BytesIO(data)}
        if key:
            environ["HTTP_X_API_KEY"] = key
        environ.update(headers or {})
        captured = {}

        def start_response(status, hdrs):
            captured["status"], captured["headers"] = int(status.split()[0]), dict(hdrs)

        out = b"".join(self.app(environ, start_response))
        ctype = captured["headers"].get("Content-Type", "")
        payload = json.loads(out) if out and "json" in ctype else out.decode()
        return captured["status"], payload, captured["headers"]


class WebTests(WebBase):
    def test_wt01_health_is_public_and_ok(self):
        """WT-01 /health is public and reports status, version and environment"""
        status, body, _ = self.call("GET", "/health", key=None)
        self.assertEqual(status, 200)
        self.assertEqual((body["status"], body["environment"]), ("ok", "staging"))
        self.assertIn("version", body)

    def test_wt02_api_requires_key(self):
        """WT-02 API endpoints return 401 without a key or with a wrong key"""
        for key in (None, "", "wrong-key-wrong-key-1"):
            for method, path in (("GET", "/api/expenses"), ("POST", "/api/expenses"),
                                 ("GET", "/api/summary"), ("DELETE", "/api/expenses/1"), ("GET", "/metrics")):
                status, _, _ = self.call(method, path, {"amount": "1"}, key=key)
                self.assertEqual(status, 401, msg=f"{method} {path} key={key!r}")

    def test_wt03_create_list_get_delete(self):
        """WT-03 Create, list, fetch and delete an expense through the API"""
        status, created, _ = self.call("POST", "/api/expenses",
                                       {"amount": "12.50", "category": "Food", "date": "2026-10-01", "note": "lunch"})
        self.assertEqual(status, 201)
        self.assertEqual((created["amount"], created["category"]), ("12.50", "food"))
        status, listing, _ = self.call("GET", "/api/expenses?category=food")
        self.assertEqual((status, listing["count"]), (200, 1))
        status, one, _ = self.call("GET", f"/api/expenses/{created['id']}")
        self.assertEqual((status, one["description"]), (200, "lunch"))
        self.assertEqual(self.call("DELETE", f"/api/expenses/{created['id']}")[0], 204)
        self.assertEqual(self.call("GET", f"/api/expenses/{created['id']}")[0], 404)

    def test_wt04_validation_errors_are_400(self):
        """WT-04 Invalid amount, date or category returns 400 with a clear message"""
        for body in ({"amount": "abc", "category": "x"}, {"amount": "-5", "category": "x"},
                     {"amount": "1e400", "category": "x"}, {"amount": "5", "category": ""},
                     {"amount": "5", "category": "x", "date": "2026-13-45"}, {}):
            status, payload, _ = self.call("POST", "/api/expenses", body)
            self.assertEqual(status, 400, msg=str(body))
            self.assertIn("error", payload)

    def test_wt05_bad_json_and_non_object(self):
        """WT-05 Malformed JSON and non-object JSON return 400"""
        self.assertEqual(self.call("POST", "/api/expenses", raw=b"not json")[0], 400)
        self.assertEqual(self.call("POST", "/api/expenses", raw=b"[1,2,3]")[0], 400)
        self.assertEqual(self.call("POST", "/api/expenses", raw=b"\xff\xfe")[0], 400)

    def test_wt06_body_size_limit(self):
        """WT-06 A request body above the limit is refused with 413"""
        status, _, _ = self.call("POST", "/api/expenses", raw=b'{"note":"' + b"x" * 2000 + b'"}')
        self.assertEqual(status, 413)

    def test_wt07_not_found_and_method_not_allowed(self):
        """WT-07 Unknown paths return 404 and wrong methods return 405"""
        self.assertEqual(self.call("GET", "/nope")[0], 404)
        self.assertEqual(self.call("PUT", "/api/expenses")[0], 405)
        self.assertEqual(self.call("POST", "/health", key=None)[0], 405)
        self.assertEqual(self.call("DELETE", "/api/expenses/999")[0], 404)

    def test_wt08_summary_and_filters(self):
        """WT-08 Summary and date filters work through the API"""
        for amount, cat, day in (("10", "food", "2026-10-01"), ("20", "food", "2026-10-20"), ("5", "fun", "2026-09-01")):
            self.call("POST", "/api/expenses", {"amount": amount, "category": cat, "date": day})
        _, summary, _ = self.call("GET", "/api/summary")
        self.assertEqual((summary["total"], summary["categories"]["food"]), ("35.00", "30.00"))
        _, listing, _ = self.call("GET", "/api/expenses?start=2026-10-01&end=2026-10-31")
        self.assertEqual(listing["count"], 2)
        self.assertEqual(self.call("GET", "/api/expenses?start=2026-12-01&end=2026-01-01")[0], 400)

    def test_wt09_security_headers_and_request_id(self):
        """WT-09 Responses carry security headers and a request id (echoed if supplied)"""
        _, _, h = self.call("GET", "/health", key=None, headers={"HTTP_X_REQUEST_ID": "abc-123"})
        self.assertEqual(h["X-Request-ID"], "abc-123")
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertEqual(h["Cache-Control"], "no-store")
        self.assertEqual(h["X-Frame-Options"], "DENY")
        _, _, h2 = self.call("GET", "/health", key=None, headers={"HTTP_X_REQUEST_ID": "bad id\r\nInjected: 1"})
        self.assertNotIn("\n", h2["X-Request-ID"])
        self.assertNotIn(" ", h2["X-Request-ID"])

    def test_wt10_internal_errors_do_not_leak_details(self):
        """WT-10 An unexpected server error returns a generic 500 and logs the details"""
        import expense_tracker.web as web
        original = web.ExpenseService.list_expenses
        web.ExpenseService.list_expenses = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("secret internals /etc/passwd"))
        try:
            with self.assertLogs("expense_tracker", level="ERROR") as logs:
                status, body, _ = self.call("GET", "/api/expenses")
        finally:
            web.ExpenseService.list_expenses = original
        self.assertEqual(status, 500)
        self.assertEqual(body["error"], "Internal server error")
        self.assertIn("request_id", body)
        self.assertNotIn("secret", json.dumps(body))
        self.assertTrue(any("secret internals" in (l.get("exc", "") + l.get("msg", ""))
                            for l in [{"exc": logging.Formatter().formatException(r.exc_info) if r.exc_info else "", "msg": r.getMessage()}
                                      for r in logs.records]))

    def test_wt11_metrics(self):
        """WT-11 /metrics exposes request counters and the expense count"""
        self.call("POST", "/api/expenses", {"amount": "1", "category": "a"})
        self.call("GET", "/api/expenses", key=None)
        status, text, _ = self.call("GET", "/metrics")
        self.assertEqual(status, 200)
        self.assertIn('expense_tracker_requests_total{status="201"} 1', text)
        self.assertIn('expense_tracker_requests_total{status="401"} 1', text)
        self.assertIn("expense_tracker_expenses 1", text)

    def test_wt12_sql_injection_via_api(self):
        """WT-12 SQL injection text sent through the API is stored harmlessly"""
        evil = "x'; DROP TABLE expenses;--"
        self.assertEqual(self.call("POST", "/api/expenses", {"amount": "1", "category": evil})[0], 201)
        self.assertEqual(self.call("GET", "/api/expenses")[1]["count"], 1)

    def test_wt13_data_persists_across_app_instances(self):
        """WT-13 Data survives an application restart (new app instance, same database file)"""
        self.call("POST", "/api/expenses", {"amount": "9.99", "category": "keep"})
        restarted = create_app(Settings("staging", self.db, "ERROR", KEY, 1000))
        self.app = restarted
        self.assertEqual(self.call("GET", "/api/expenses")[1]["count"], 1)

    def test_wt14_request_log_is_json(self):
        """WT-14 Each request is logged as one JSON line with request id, status and duration"""
        from expense_tracker.web import JsonFormatter
        with self.assertLogs("expense_tracker", level="INFO") as logs:
            self.call("GET", "/health", key=None)
        record = [r for r in logs.records if r.getMessage() == "request"][-1]
        line = json.loads(JsonFormatter().format(record))
        for field in ("ts", "level", "request_id", "method", "path", "status", "duration_ms"):
            self.assertIn(field, line)
        self.assertNotIn(KEY, json.dumps(line))

    def test_wt15_auth_disabled_only_in_development(self):
        """WT-15 In development without a key the API is open (with a logged warning)"""
        dev = create_app(Settings("development", self.db, "ERROR", "", 1000))
        self.app = dev
        self.assertEqual(self.call("GET", "/api/expenses", key=None)[0], 200)


class ConfigTests(unittest.TestCase):
    def test_cf01_defaults_for_development(self):
        """CF-01 Defaults are valid for development"""
        s = Settings.from_env({})
        self.assertEqual((s.environment, s.db_path, s.auth_enabled), ("development", "expenses.db", False))

    def test_cf02_production_requires_strong_key(self):
        """CF-02 Staging and production refuse to start without a strong API key"""
        for env in ("staging", "production"):
            for key in ("", "short", "x" * 15):
                with self.assertRaises(ConfigError, msg=f"{env}:{key!r}"):
                    Settings.from_env({"APP_ENV": env, "API_KEY": key})
            Settings.from_env({"APP_ENV": env, "API_KEY": "x" * 16})

    def test_cf03_invalid_values_rejected(self):
        """CF-03 Invalid APP_ENV, LOG_LEVEL, DB_PATH and MAX_BODY_BYTES are rejected"""
        for env in ({"APP_ENV": "prod"}, {"LOG_LEVEL": "LOUD"}, {"DB_PATH": " "},
                    {"MAX_BODY_BYTES": "abc"}, {"MAX_BODY_BYTES": "5"}):
            with self.assertRaises(ConfigError, msg=str(env)):
                Settings.from_env(env)

    def test_cf04_environment_values_are_normalised(self):
        """CF-04 Environment values are trimmed and case-normalised"""
        s = Settings.from_env({"APP_ENV": " Production ", "API_KEY": " " + "k" * 20 + " ", "LOG_LEVEL": "debug"})
        self.assertEqual((s.environment, s.log_level, len(s.api_key)), ("production", "DEBUG", 20))

    def test_cf05_wsgi_module_fails_fast(self):
        """CF-05 The production entry point exits with code 3 and a clear message when misconfigured"""
        import subprocess
        root = os.path.join(os.path.dirname(__file__), "..")
        env = dict(os.environ, PYTHONPATH=os.path.join(root, "src"), APP_ENV="production", API_KEY="")
        p = subprocess.run([sys.executable, "-c", "import expense_tracker.wsgi"], env=env,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 3)
        self.assertIn("CONFIGURATION ERROR", p.stderr)
        self.assertNotIn("Traceback", p.stderr)


class OpsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "live.db")
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE t (v INTEGER)")
        conn.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
        conn.commit()
        conn.close()
        self.dest = os.path.join(self.tmp.name, "backups")

    def tearDown(self):
        self.tmp.cleanup()

    def count(self, path):
        conn = sqlite3.connect(path)
        try:
            return conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        finally:
            conn.close()

    def test_op01_backup_is_complete_and_valid(self):
        """OP-01 Backup creates a complete, integrity-checked copy"""
        path = ops.backup(self.db, self.dest)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(self.count(path), 3)
        self.assertTrue(ops.integrity_ok(path))

    def test_op02_retention_keeps_newest(self):
        """OP-02 Backup retention keeps only the newest N files"""
        for minute in range(5):
            ops.backup(self.db, self.dest, keep=3, now=datetime(2026, 10, 1, 12, minute, 0))
        names = sorted(os.listdir(self.dest))
        self.assertEqual(len(names), 3)
        self.assertEqual(names[0], "expenses-20261001-120200.db")

    def test_op03_restore_recovers_data_and_keeps_safety_copy(self):
        """OP-03 Restore brings back deleted data and saves the previous database"""
        backup_path = ops.backup(self.db, self.dest)
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM t")
        conn.commit()
        conn.close()
        safety = ops.restore(self.db, backup_path)
        self.assertEqual(self.count(self.db), 3)
        self.assertEqual(self.count(safety), 0)

    def test_op04_missing_and_corrupt_files(self):
        """OP-04 Backup of a missing database and restore of a corrupt backup fail safely"""
        with self.assertRaises(FileNotFoundError):
            ops.backup(os.path.join(self.tmp.name, "nope.db"), self.dest)
        bad = os.path.join(self.tmp.name, "bad.db")
        with open(bad, "wb") as fh:
            fh.write(b"this is not a database" * 100)
        with self.assertRaises(Exception):
            ops.restore(self.db, bad)
        self.assertEqual(self.count(self.db), 3)

    def test_op05_command_line_interface(self):
        """OP-05 The ops command line backs up, checks and restores, with exit codes"""
        self.assertEqual(ops.main(["backup", "--db", self.db, "--dest", self.dest, "--keep", "2"]), 0)
        self.assertEqual(ops.main(["check", "--db", self.db]), 0)
        latest = os.path.join(self.dest, sorted(os.listdir(self.dest))[-1])
        self.assertEqual(ops.main(["restore", "--db", self.db, "--from", latest]), 0)
        self.assertEqual(ops.main(["backup", "--db", "/nonexistent/x.db", "--dest", self.dest]), 1)


if __name__ == "__main__":
    unittest.main()
