"""Capstone tests: new service features (SV), API endpoints (WT), rate limiting (RL),
dashboard assets and security (SC), and regression tests (REG)."""
import csv
import io
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from expense_tracker.config import ConfigError, Settings
from expense_tracker.database import connect
from expense_tracker.models import ValidationError
from expense_tracker.service import ExpenseService, csv_safe
from expense_tracker.web import CSP, RateLimiter, client_address, create_app

ROOT = os.path.join(os.path.dirname(__file__), "..", "src", "expense_tracker", "static")
KEY = "capstone-test-key-1234567890"


# ------------------------------------------------------------------ service
class ServiceFeatureTests(unittest.TestCase):
    def setUp(self):
        self.svc = ExpenseService(connect(":memory:"))

    def seed(self):
        self.svc.add_many([("100", "rent", "2026-09-01"), ("40", "food", "2026-09-10"),
                           ("60", "food", "2026-10-05", "groceries"), ("20", "fun", "2026-10-20"),
                           ("120", "rent", "2026-10-01"), ("5", "food", "2025-12-31")])

    def test_sv01_pagination_and_count(self):
        """SV-01 list_expenses supports limit/offset and count_expenses gives the full total"""
        self.seed()
        page1 = self.svc.list_expenses(limit=2)
        page2 = self.svc.list_expenses(limit=2, offset=2)
        self.assertEqual(len(page1), 2)
        self.assertTrue(set(e.id for e in page1).isdisjoint(e.id for e in page2))
        self.assertEqual(self.svc.count_expenses(), 6)
        self.assertEqual(self.svc.count_expenses(category="food"), 3)
        with self.assertRaises(ValidationError):
            self.svc.list_expenses(limit=0)
        with self.assertRaises(ValidationError):
            self.svc.list_expenses(limit=5, offset=-1)

    def test_sv02_monthly_totals(self):
        """SV-02 monthly_totals returns 12 values for a year in one query"""
        self.seed()
        totals = self.svc.monthly_totals(2026)
        self.assertEqual(len(totals), 12)
        self.assertEqual((totals[8], totals[9], totals[0]), (14000, 20000, 0))
        self.assertEqual(self.svc.monthly_totals(2025)[11], 500)
        self.assertEqual(sum(self.svc.monthly_totals(2030)), 0)

    def test_sv03_month_boundaries_exact(self):
        """SV-03 Month queries include the first and last day and exclude neighbours (incl. December)"""
        self.svc.add_many([("1", "a", "2026-12-31"), ("2", "a", "2027-01-01"), ("4", "a", "2026-12-01"),
                           ("8", "a", "2026-11-30")])
        self.assertEqual(self.svc.monthly_total(2026, 12), 500)
        self.assertEqual(self.svc.monthly_total(2027, 1), 200)
        self.assertEqual(self.svc.monthly_total(2026, 11), 800)

    def test_sv04_insights(self):
        """SV-04 insights: total, change vs previous month, top category, largest, daily average"""
        self.seed()
        i = self.svc.insights(2026, 10)
        self.assertEqual((i["total_cents"], i["previous_total_cents"]), (20000, 14000))
        self.assertEqual(i["change_percent"], 42.9)
        self.assertEqual(i["top_category"], {"category": "rent", "total_cents": 12000})
        self.assertEqual(i["largest_expense"].amount_cents, 12000)
        self.assertEqual((i["expense_count"], i["daily_average_cents"]), (3, round(20000 / 31)))

    def test_sv05_insights_edge_cases(self):
        """SV-05 insights handle an empty month, no previous month, and January -> previous December"""
        i = self.svc.insights(2026, 3)
        self.assertEqual((i["total_cents"], i["change_percent"], i["top_category"], i["largest_expense"]),
                         (0, None, None, None))
        self.svc.add_many([("10", "a", "2025-12-15"), ("15", "a", "2026-01-15")])
        j = self.svc.insights(2026, 1)
        self.assertEqual((j["previous_total_cents"], j["change_percent"]), (1000, 50.0))
        self.assertEqual(self.svc.insights(2026, 2)["change_percent"], -100.0)

    def test_sv06_budget_list_and_delete(self):
        """SV-06 Budgets can be deleted; deleting or reading a missing budget raises KeyError"""
        self.svc.set_budget("Food", "50")
        self.assertEqual(self.svc.budget_limit_cents("food"), 5000)
        self.svc.delete_budget("food")
        with self.assertRaises(KeyError):
            self.svc.delete_budget("food")
        with self.assertRaises(KeyError):
            self.svc.budget_limit_cents("food")

    def test_sv07_csv_formula_injection_neutralised(self):
        """SV-07 CSV cells that start with = + - @ are prefixed so spreadsheets treat them as text"""
        for evil in ("=1+1", "+cmd", "-2+3", "@SUM(A1)", "\tTAB"):
            self.assertTrue(csv_safe(evil).startswith("'"), evil)
        for fine in ("lunch", "", "a=b", "12.50"):
            self.assertEqual(csv_safe(fine), fine)

    def test_sv08_csv_quoting_and_roundtrip(self):
        """SV-08 CSV export quotes commas, quotes and newlines correctly and round-trips"""
        self.svc.add_expense("5", "food", "2026-10-01", 'a, "quoted"\nline')
        rows = list(csv.reader(io.StringIO(self.svc.export_csv_text(), newline="")))
        self.assertEqual(rows[0], ["id", "date", "category", "amount", "description"])
        self.assertEqual(rows[1][4], 'a, "quoted"\nline')

    def test_sv09_shared_date_filter(self):
        """SV-09 One shared date filter behaves identically for list, count and totals"""
        self.seed()
        args = dict(start="2026-10-01", end="2026-10-31")
        self.assertEqual(len(self.svc.list_expenses(**args)), 3)
        self.assertEqual(self.svc.count_expenses(**args), 3)
        self.assertEqual(sum(self.svc.total_by_category(**args).values()), 20000)
        with self.assertRaises(ValidationError):
            self.svc.count_expenses(start="2026-12-01", end="2026-01-01")


# ------------------------------------------------------------------ API
class ApiBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "cap.db")
        self.settings = Settings("staging", self.db, "ERROR", KEY, 1000, 100000, 60)
        self.app = create_app(self.settings)

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, method, path, body=None, key=KEY, headers=None, app=None):
        data = json.dumps(body).encode() if body is not None else b""
        path, _, query = path.partition("?")
        environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query,
                   "CONTENT_LENGTH": str(len(data)), "wsgi.input": io.BytesIO(data), "REMOTE_ADDR": "10.0.0.1"}
        if key:
            environ["HTTP_X_API_KEY"] = key
        environ.update(headers or {})
        cap = {}

        def start_response(status, hdrs):
            cap["status"], cap["headers"] = int(status.split()[0]), dict(hdrs)

        out = b"".join((app or self.app)(environ, start_response))
        ctype = cap["headers"].get("Content-Type", "")
        payload = json.loads(out) if out and "json" in ctype else out
        return cap["status"], payload, cap["headers"]

    def add(self, amount, category, day, note=""):
        return self.call("POST", "/api/expenses", {"amount": amount, "category": category, "date": day, "note": note})[1]


class ApiFeatureTests(ApiBase):
    def test_wt16_pagination(self):
        """WT-16 GET /api/expenses paginates and reports total, limit and offset"""
        for i in range(7):
            self.add("1", "a", f"2026-10-{i + 1:02d}")
        _, body, _ = self.call("GET", "/api/expenses?limit=3&offset=3")
        self.assertEqual((body["count"], body["total"], body["limit"], body["offset"]), (3, 7, 3, 3))
        _, body, _ = self.call("GET", "/api/expenses")
        self.assertEqual((body["count"], body["limit"]), (7, 100))

    def test_wt17_bad_pagination_params(self):
        """WT-17 Invalid limit/offset values return 400"""
        for q in ("limit=0", "limit=501", "limit=abc", "offset=-1", "offset=x"):
            self.assertEqual(self.call("GET", f"/api/expenses?{q}")[0], 400, msg=q)

    def test_wt18_update_expense(self):
        """WT-18 PUT /api/expenses/<id> updates fields; empty body and bad values are rejected"""
        e = self.add("10", "food", "2026-10-01", "lunch")
        status, body, _ = self.call("PUT", f"/api/expenses/{e['id']}", {"amount": "12.34", "note": "dinner"})
        self.assertEqual((status, body["amount"], body["description"], body["category"]), (200, "12.34", "dinner", "food"))
        self.assertEqual(self.call("PUT", f"/api/expenses/{e['id']}", {})[0], 400)
        self.assertEqual(self.call("PUT", f"/api/expenses/{e['id']}", {"amount": "-1"})[0], 400)
        self.assertEqual(self.call("PUT", "/api/expenses/9999", {"amount": "1"})[0], 404)

    def test_wt19_budgets_api(self):
        """WT-19 Budgets: set, list with progress, over-budget flag, delete"""
        self.add("30", "food", "2026-10-01")
        self.add("30", "food", "2026-10-02")
        status, body, _ = self.call("PUT", "/api/budgets/Food", {"limit": "50"})
        self.assertEqual((status, body), (200, {"category": "food", "limit": "50.00"}))
        self.call("PUT", "/api/budgets/travel", {"limit": "100"})
        _, body, _ = self.call("GET", "/api/budgets?month=2026-10")
        by = {b["category"]: b for b in body["budgets"]}
        self.assertEqual((by["food"]["spent"], by["food"]["percent"], by["food"]["over"]), ("60.00", 120.0, True))
        self.assertEqual((by["travel"]["spent"], by["travel"]["over"]), ("0.00", False))
        self.assertEqual(self.call("DELETE", "/api/budgets/food")[0], 204)
        self.assertEqual(self.call("DELETE", "/api/budgets/food")[0], 404)

    def test_wt20_budget_validation(self):
        """WT-20 Budget limit and month are validated"""
        self.assertEqual(self.call("PUT", "/api/budgets/food", {"limit": "abc"})[0], 400)
        self.assertEqual(self.call("PUT", "/api/budgets/food", {})[0], 400)
        self.assertEqual(self.call("GET", "/api/budgets?month=2026-13")[0], 400)
        self.assertEqual(self.call("GET", "/api/budgets?month=abc")[0], 400)

    def test_wt21_monthly_endpoint(self):
        """WT-21 GET /api/monthly returns 12 months and a yearly total"""
        self.add("10", "a", "2026-02-01")
        self.add("5.50", "a", "2026-12-31")
        _, body, _ = self.call("GET", "/api/monthly?year=2026")
        self.assertEqual((len(body["months"]), body["total"]), (12, "15.50"))
        self.assertEqual((body["months"][1], body["months"][11]["total"]), ({"month": "2026-02", "total": "10.00"}, "5.50"))
        self.assertEqual(self.call("GET", "/api/monthly?year=1800")[0], 400)

    def test_wt22_insights_endpoint(self):
        """WT-22 GET /api/insights formats money and includes the top category and largest expense"""
        self.add("20", "food", "2026-09-10")
        self.add("30", "food", "2026-10-10")
        self.add("45.50", "rent", "2026-10-11")
        _, body, _ = self.call("GET", "/api/insights?month=2026-10")
        self.assertEqual((body["total"], body["previous_total"], body["change_percent"]), ("75.50", "20.00", 277.5))
        self.assertEqual(body["top_category"], {"category": "rent", "total": "45.50"})
        self.assertEqual(body["largest_expense"]["amount"], "45.50")
        empty = self.call("GET", "/api/insights?month=2020-01")[1]
        self.assertEqual((empty["total"], empty["top_category"], empty["largest_expense"]), ("0.00", None, None))

    def test_wt23_export_csv_endpoint(self):
        """WT-23 GET /api/export.csv downloads a CSV file with safe cells"""
        self.add("5", "food", "2026-10-01", "=HYPERLINK(\"http://evil\")")
        status, body, h = self.call("GET", "/api/export.csv")
        self.assertEqual(status, 200)
        self.assertTrue(h["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment", h["Content-Disposition"])
        self.assertIn(b"'=HYPERLINK", body)
        self.assertEqual(self.call("GET", "/api/export.csv", key=None)[0], 401)

    def test_wt24_method_not_allowed_has_allow_header(self):
        """WT-24 Wrong methods return 405 with an Allow header"""
        status, _, h = self.call("POST", "/api/summary", {})
        self.assertEqual(status, 405)
        self.assertEqual(h["Allow"], "GET")
        self.assertEqual(self.call("POST", "/", {}, key=None)[0], 405)

    def test_wt25_new_endpoints_need_key(self):
        """WT-25 Every new API endpoint requires the key"""
        for method, path in (("GET", "/api/monthly"), ("GET", "/api/insights"), ("GET", "/api/budgets"),
                             ("PUT", "/api/budgets/x"), ("DELETE", "/api/budgets/x"), ("PUT", "/api/expenses/1"),
                             ("GET", "/api/export.csv")):
            self.assertEqual(self.call(method, path, {}, key=None)[0], 401, msg=f"{method} {path}")


# ------------------------------------------------------------------ rate limiting
class RateLimitTests(ApiBase):
    def make_app(self, fails=3, window=60):
        self.now = [1000.0]
        s = Settings("staging", self.db, "ERROR", KEY, 1000, fails, window)
        return create_app(s, clock=lambda: self.now[0])

    def test_rl01_blocks_after_repeated_failures(self):
        """RL-01 After N failed key attempts further requests get 429 with Retry-After"""
        app = self.make_app(fails=3)
        for _ in range(3):
            self.assertEqual(self.call("GET", "/api/expenses", key="wrong-wrong-wrong-1", app=app)[0], 401)
        status, body, h = self.call("GET", "/api/expenses", key="wrong-wrong-wrong-1", app=app)
        self.assertEqual(status, 429)
        self.assertIn("Too many", body["error"])
        self.assertTrue(int(h["Retry-After"]) >= 1)

    def test_rl02_correct_key_also_blocked_during_lockout_then_recovers(self):
        """RL-02 While locked out even the right key is refused; after the window it works again"""
        app = self.make_app(fails=2, window=60)
        for _ in range(2):
            self.call("GET", "/api/expenses", key="nope-nope-nope-nope", app=app)
        self.assertEqual(self.call("GET", "/api/expenses", app=app)[0], 429)
        self.now[0] += 61
        self.assertEqual(self.call("GET", "/api/expenses", app=app)[0], 200)

    def test_rl03_per_client_and_public_endpoints_unaffected(self):
        """RL-03 Limit is per client address; /health and the dashboard are never rate limited"""
        app = self.make_app(fails=2)
        for _ in range(2):
            self.call("GET", "/api/expenses", key="bad-bad-bad-bad-bad", app=app)
        self.assertEqual(self.call("GET", "/api/expenses", app=app)[0], 429)
        other = {"REMOTE_ADDR": "10.9.9.9"}
        self.assertEqual(self.call("GET", "/api/expenses", headers=other, app=app)[0], 200)
        self.assertEqual(self.call("GET", "/health", key=None, app=app)[0], 200)
        self.assertEqual(self.call("GET", "/", key=None, app=app)[0], 200)

    def test_rl04_successful_requests_do_not_count(self):
        """RL-04 Successful requests never trigger the limiter"""
        app = self.make_app(fails=2)
        for _ in range(20):
            self.assertEqual(self.call("GET", "/api/expenses", app=app)[0], 200)

    def test_rl05_limiter_unit_and_memory_bound(self):
        """RL-05 RateLimiter sliding window works and forgets old clients"""
        t = [0.0]
        lim = RateLimiter(2, 10, clock=lambda: t[0])
        lim.record_failure("a")
        self.assertEqual(lim.retry_after("a"), 0)
        lim.record_failure("a")
        self.assertGreaterEqual(lim.retry_after("a"), 1)
        t[0] = 11
        self.assertEqual(lim.retry_after("a"), 0)
        self.assertNotIn("a", lim.hits)

    def test_rl06_client_address_uses_rightmost_forwarded_entry(self):
        """RL-06 Client address is the rightmost X-Forwarded-For entry (cannot be spoofed by the client)"""
        self.assertEqual(client_address({"HTTP_X_FORWARDED_FOR": "1.1.1.1, 2.2.2.2, 3.3.3.3", "REMOTE_ADDR": "9.9.9.9"}), "3.3.3.3")
        self.assertEqual(client_address({"REMOTE_ADDR": "9.9.9.9"}), "9.9.9.9")
        self.assertEqual(client_address({}), "unknown")

    def test_rl07_settings_validation(self):
        """RL-07 Rate limit settings are read from the environment and validated"""
        s = Settings.from_env({"RATE_LIMIT_FAILS": "5", "RATE_LIMIT_WINDOW": "30"})
        self.assertEqual((s.rate_limit_fails, s.rate_limit_window), (5, 30))
        for bad in ({"RATE_LIMIT_FAILS": "0"}, {"RATE_LIMIT_WINDOW": "abc"}):
            with self.assertRaises(ConfigError):
                Settings.from_env(bad)


# ------------------------------------------------------------------ dashboard assets and security
class DashboardTests(ApiBase):
    def test_sc01_dashboard_is_public_with_security_headers(self):
        """SC-01 GET / serves the dashboard without a key, with a strict Content-Security-Policy"""
        status, body, h = self.call("GET", "/", key=None)
        self.assertEqual(status, 200)
        self.assertTrue(h["Content-Type"].startswith("text/html"))
        self.assertEqual(h["Content-Security-Policy"], CSP)
        self.assertNotIn("unsafe-inline", h["Content-Security-Policy"])
        self.assertNotIn("unsafe-eval", h["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", h["Content-Security-Policy"])
        self.assertEqual((h["X-Frame-Options"], h["Referrer-Policy"]), ("DENY", "no-referrer"))
        self.assertIn(b"<title>", body)

    def test_sc02_static_files_served_with_correct_types(self):
        """SC-02 app.js and app.css are served publicly with the right content types"""
        s1, js, h1 = self.call("GET", "/static/app.js", key=None)
        s2, css, h2 = self.call("GET", "/static/app.css", key=None)
        self.assertEqual((s1, s2), (200, 200))
        self.assertTrue(h1["Content-Type"].startswith("text/javascript"))
        self.assertTrue(h2["Content-Type"].startswith("text/css"))
        self.assertEqual(h1["X-Content-Type-Options"], "nosniff")
        self.assertGreater(len(js), 1000)

    def test_sc03_path_traversal_impossible(self):
        """SC-03 Only whitelisted static paths exist; traversal and unknown files return 404"""
        for path in ("/static/../web.py", "/static/../../config.py", "/static/%2e%2e/web.py",
                     "/static/app.js/../../web.py", "/static/secret.txt", "/static/", "/index.html",
                     "/..%2fweb.py"):
            self.assertEqual(self.call("GET", path)[0], 404, msg=path)

    def test_sc04_html_has_no_inline_script_or_style(self):
        """SC-04 index.html has no inline scripts, inline styles or inline event handlers (CSP-safe)"""
        html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
        for tag in re.findall(r"<script\b[^>]*>", html):
            self.assertIn("src=", tag)
        bodies = [x for x in re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.S | re.I) if x.strip()]
        self.assertEqual(bodies, [], "inline script bodies are not allowed")
        self.assertNotRegex(html, r"<style\b")
        self.assertNotRegex(html, r"\sstyle=")
        self.assertNotRegex(html, r"\son[a-z]+\s*=")
        self.assertNotRegex(html, r"https?://")  # no external resources

    def test_sc05_javascript_has_no_dangerous_apis(self):
        """SC-05 app.js never uses innerHTML, eval, document.write or localStorage (XSS and key-storage lint)"""
        js = open(os.path.join(ROOT, "app.js"), encoding="utf-8").read()
        for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function", "document.write",
                       "localStorage", "setTimeout(\"", "javascript:"):
            self.assertFalse(banned in js, msg=f"app.js must not contain {banned!r}")

    def test_sc06_dashboard_has_accessibility_basics(self):
        """SC-06 Dashboard declares language, viewport, labelled inputs and a live status region"""
        html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
        self.assertIn('lang="en"', html)
        self.assertIn('name="viewport"', html)
        self.assertIn('aria-live', html)
        inputs = re.findall(r'<input\b[^>]*\bid="([^"]+)"', html) + re.findall(r'<select\b[^>]*\bid="([^"]+)"', html)
        self.assertGreater(len(inputs), 5)
        for i in inputs:
            self.assertIn(f'for="{i}"', html, msg=f"input {i} has no <label for>")

    def test_sc07_api_responses_are_not_cacheable(self):
        """SC-07 API responses are no-store; static files use no-cache so deployments show immediately"""
        self.assertEqual(self.call("GET", "/api/summary")[2]["Cache-Control"], "no-store")
        self.assertEqual(self.call("GET", "/static/app.js", key=None)[2]["Cache-Control"], "no-cache")


class RegressionTests(ApiBase):
    def test_reg08_csv_formula_injection(self):
        """REG-08 BUG-008: CSV export wrote =formulas as live spreadsheet formulas (found in final security audit)"""
        svc = ExpenseService(connect(":memory:"))
        svc.add_expense("5", "food", "2026-10-01", "=cmd|' /C calc'!A0")
        text = svc.export_csv_text()
        self.assertNotIn(",=cmd", text)
        self.assertIn("'=cmd", text)

    def test_reg09_list_endpoint_unbounded(self):
        """REG-09 BUG-009: GET /api/expenses returned every row (unbounded response); now capped at 500 per page"""
        self.assertEqual(self.call("GET", "/api/expenses?limit=100000")[0], 400)


if __name__ == "__main__":
    unittest.main()
