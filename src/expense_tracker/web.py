"""HTTP layer (WSGI application): JSON API plus the single-page dashboard.

Public (no key)   GET /  GET /static/app.js  GET /static/app.css  GET /health
API (X-API-Key)   GET/POST /api/expenses      GET/PUT/DELETE /api/expenses/<id>
                  GET /api/summary            GET /api/monthly?year=      GET /api/insights?month=
                  GET /api/budgets?month=     PUT/DELETE /api/budgets/<category>
                  GET /api/export.csv         GET /metrics
Failed authentication attempts are rate limited per client address.
"""
import hmac
import json
import logging
import re
import sys
import threading
import time
import uuid
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

from . import __version__
from .config import Settings
from .database import connect
from .models import ValidationError, format_money, parse_month
from .service import ExpenseService

log = logging.getLogger("expense_tracker")

STATIC_DIR = Path(__file__).parent / "static"
# Only these exact paths are ever served from disk, so path traversal is impossible by construction.
STATIC_FILES = {"/": ("index.html", "text/html; charset=utf-8"),
                "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/static/app.css": ("app.css", "text/css; charset=utf-8")}
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE = 100, 500


class JsonFormatter(logging.Formatter):
    """One JSON object per line: easy for log tools to parse and search."""

    def format(self, record):
        entry = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
                 "msg": record.getMessage()}
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, separators=(",", ":"))


def configure_logging(level: str) -> None:
    log.setLevel(level)
    if not any(getattr(h, "_expense_json", False) for h in log.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler._expense_json = True
        log.addHandler(handler)
    log.propagate = False


class HttpError(Exception):
    def __init__(self, status: int, message: str, headers: dict = None):
        super().__init__(message)
        self.status, self.message, self.headers = status, message, headers or {}


STATUS_TEXT = {200: "OK", 201: "Created", 204: "No Content", 400: "Bad Request", 401: "Unauthorized",
               404: "Not Found", 405: "Method Not Allowed", 413: "Payload Too Large",
               429: "Too Many Requests", 500: "Internal Server Error", 503: "Service Unavailable"}


class Metrics:
    """Simple in-process counters (per worker process)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.started = time.time()
        self.by_status = {}
        self.duration_sum = 0.0
        self.count = 0

    def record(self, status: int, seconds: float):
        with self.lock:
            self.by_status[status] = self.by_status.get(status, 0) + 1
            self.duration_sum += seconds
            self.count += 1


class RateLimiter:
    """Sliding-window limiter for FAILED authentication attempts (brute-force protection).

    State is per worker process, so the effective limit is max_fails x workers.
    """

    def __init__(self, max_fails: int, window_seconds: int, clock=time.monotonic):
        self.max_fails, self.window, self.clock = max_fails, window_seconds, clock
        self.hits, self.lock = {}, threading.Lock()

    def _recent(self, key, now):
        recent = [t for t in self.hits.get(key, ()) if t > now - self.window]
        if recent:
            self.hits[key] = recent
        else:
            self.hits.pop(key, None)
        return recent

    def retry_after(self, key: str) -> int:
        """Seconds the client must wait (0 = allowed)."""
        with self.lock:
            now = self.clock()
            recent = self._recent(key, now)
            if len(recent) < self.max_fails:
                return 0
            return max(1, int(recent[0] + self.window - now) + 1)

    def record_failure(self, key: str) -> None:
        with self.lock:
            now = self.clock()
            if len(self.hits) > 10_000:  # bound memory: drop clients with no recent failures
                for k in list(self.hits):
                    self._recent(k, now)
            self.hits.setdefault(key, []).append(now)


def client_address(environ) -> str:
    """Rightmost X-Forwarded-For entry (added by the platform's own proxy), else the socket address."""
    forwarded = environ.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()[:64] or "unknown"
    return environ.get("REMOTE_ADDR", "unknown")


def load_static() -> dict:
    return {path: (name, ctype, (STATIC_DIR / name).read_bytes()) for path, (name, ctype) in STATIC_FILES.items()}


def create_app(settings: Settings = None, clock=time.monotonic):
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    metrics = Metrics()
    limiter = RateLimiter(settings.rate_limit_fails, settings.rate_limit_window, clock)
    assets = load_static()
    if not settings.auth_enabled:
        log.warning("API_KEY is not set: authentication is DISABLED (allowed in development only)")
    log.info("application starting", extra={"fields": {
        "version": __version__, "environment": settings.environment, "db": settings.db_path}})
    connect(settings.db_path).close()  # create the database file and schema once at start-up

    def authorised(environ) -> bool:
        if not settings.auth_enabled:
            return True
        supplied = environ.get("HTTP_X_API_KEY", "")
        return hmac.compare_digest(supplied.encode(), settings.api_key.encode())

    def read_json(environ) -> dict:
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            raise HttpError(400, "Invalid Content-Length")
        if length > settings.max_body_bytes:
            raise HttpError(413, f"Request body too large (maximum {settings.max_body_bytes} bytes)")
        raw = environ["wsgi.input"].read(length) if length else b""
        try:
            data = json.loads(raw.decode("utf-8") or "null")
        except (ValueError, UnicodeDecodeError):
            raise HttpError(400, "Body must be valid JSON")
        if not isinstance(data, dict):
            raise HttpError(400, "Body must be a JSON object")
        return data

    def int_param(query, name, default, low, high):
        raw = query.get(name)
        if raw is None or raw == "":
            return default
        try:
            value = int(raw)
        except ValueError:
            raise HttpError(400, f"{name} must be a whole number")
        if not low <= value <= high:
            raise HttpError(400, f"{name} must be between {low} and {high}")
        return value

    def month_param(query):
        year, month = parse_month(query.get("month") or date.today().strftime("%Y-%m"))
        return year, month

    def expense_json(e) -> dict:
        return {"id": e.id, "amount": f"{e.amount_cents / 100:.2f}", "category": e.category,
                "description": e.description, "date": e.spent_on}

    def need(method, allowed):
        if method not in allowed:
            raise HttpError(405, "Method not allowed", {"Allow": ", ".join(allowed)})

    def route(environ, svc):
        method, path = environ["REQUEST_METHOD"], environ.get("PATH_INFO", "/").rstrip("/") or "/"
        query = {k: v[0] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items()}

        if path in assets:                                   # public: the dashboard files
            need(method, ("GET",))
            _, ctype, body = assets[path]
            return 200, body, {"Content-Type": ctype, "Cache-Control": "no-cache",
                               **({"Content-Security-Policy": CSP} if path == "/" else {})}
        if path == "/health":                                # public: liveness + database check
            need(method, ("GET",))
            svc.conn.execute("SELECT 1").fetchone()
            return 200, {"status": "ok", "version": __version__, "environment": settings.environment,
                         "uptime_seconds": int(time.time() - metrics.started)}

        who = client_address(environ)
        wait = limiter.retry_after(who)
        if wait:
            raise HttpError(429, f"Too many failed attempts. Try again in {wait} seconds.",
                            {"Retry-After": str(wait)})
        if not authorised(environ):
            limiter.record_failure(who)
            raise HttpError(401, "Missing or invalid API key")

        if path == "/metrics":
            need(method, ("GET",))
            return 200, _prometheus(metrics, svc)
        if path == "/api/expenses":
            need(method, ("GET", "POST"))
            if method == "GET":
                category, start, end = query.get("category"), query.get("start"), query.get("end")
                limit = int_param(query, "limit", DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
                offset = int_param(query, "offset", 0, 0, 10**9)
                items = svc.list_expenses(category, start, end, limit=limit, offset=offset)
                return 200, {"count": len(items), "total": svc.count_expenses(category, start, end),
                             "limit": limit, "offset": offset, "expenses": [expense_json(e) for e in items]}
            body = read_json(environ)
            e = svc.add_expense(body.get("amount"), body.get("category"),
                                body.get("date") or date.today().isoformat(), str(body.get("note", "")))
            return 201, expense_json(e)
        m = re.fullmatch(r"/api/expenses/(\d+)", path)
        if m:
            need(method, ("GET", "PUT", "DELETE"))
            expense_id = int(m.group(1))
            if method == "DELETE":
                svc.delete_expense(expense_id)
                return 204, None
            if method == "PUT":
                body = read_json(environ)
                note = body.get("note")
                e = svc.update_expense(expense_id, amount=body.get("amount"), category=body.get("category"),
                                       spent_on=body.get("date"), description=None if note is None else str(note))
                return 200, expense_json(e)
            return 200, expense_json(svc.get_expense(expense_id))
        if path == "/api/summary":
            need(method, ("GET",))
            totals = svc.total_by_category(query.get("start"), query.get("end"))
            return 200, {"total": format_money(sum(totals.values())),
                         "categories": {k: format_money(v) for k, v in totals.items()}}
        if path == "/api/monthly":
            need(method, ("GET",))
            year = int_param(query, "year", date.today().year, 1970, 2100)
            totals = svc.monthly_totals(year)
            return 200, {"year": year, "total": format_money(sum(totals)),
                         "months": [{"month": f"{year:04d}-{i + 1:02d}", "total": format_money(t)}
                                    for i, t in enumerate(totals)]}
        if path == "/api/insights":
            need(method, ("GET",))
            year, month = month_param(query)
            data = svc.insights(year, month)
            top, big = data["top_category"], data["largest_expense"]
            return 200, {"month": data["month"], "total": format_money(data["total_cents"]),
                         "previous_total": format_money(data["previous_total_cents"]),
                         "change_percent": data["change_percent"], "expense_count": data["expense_count"],
                         "daily_average": format_money(data["daily_average_cents"]),
                         "top_category": None if top is None else {"category": top["category"],
                                                                   "total": format_money(top["total_cents"])},
                         "largest_expense": None if big is None else expense_json(big)}
        if path == "/api/budgets":
            need(method, ("GET",))
            year, month = month_param(query)
            rows = svc.budget_status(year, month)
            return 200, {"month": f"{year:04d}-{month:02d}", "budgets": [
                {"category": r["category"], "limit": format_money(r["limit"]), "spent": format_money(r["spent"]),
                 "percent": round(r["spent"] * 100 / r["limit"], 1), "over": r["over"]} for r in rows]}
        m = re.fullmatch(r"/api/budgets/([^/]+)", path)
        if m:
            need(method, ("PUT", "DELETE"))
            if method == "DELETE":
                svc.delete_budget(m.group(1))
                return 204, None
            body = read_json(environ)
            svc.set_budget(m.group(1), body.get("limit"))
            return 200, {"category": m.group(1).strip().lower(), "limit": format_money(
                svc.budget_limit_cents(m.group(1)))}
        if path == "/api/export.csv":
            need(method, ("GET",))
            return 200, svc.export_csv_text(), {"Content-Type": "text/csv; charset=utf-8",
                                                "Content-Disposition": 'attachment; filename="expenses.csv"'}
        raise HttpError(404, "Not found")

    def app(environ, start_response):
        began = time.perf_counter()
        request_id = environ.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex[:12]
        request_id = re.sub(r"[^A-Za-z0-9_.-]", "", request_id)[:64] or uuid.uuid4().hex[:12]
        conn, extra = None, {}
        try:
            conn = connect(settings.db_path)
            result = route(environ, ExpenseService(conn))
            status, payload = result[0], result[1]
            extra = result[2] if len(result) > 2 else {}
        except HttpError as exc:
            status, payload, extra = exc.status, {"error": exc.message}, exc.headers
        except ValidationError as exc:
            status, payload = 400, {"error": exc.args[0]}
        except KeyError as exc:
            status, payload = 404, {"error": exc.args[0]}
        except Exception:  # never leak internals to the client
            log.exception("unhandled error", extra={"fields": {"request_id": request_id}})
            status, payload = 500, {"error": "Internal server error", "request_id": request_id}
        finally:
            if conn is not None:
                conn.close()

        if isinstance(payload, bytes):
            body, ctype = payload, "application/octet-stream"
        elif isinstance(payload, str):
            body, ctype = payload.encode("utf-8"), "text/plain; version=0.0.4; charset=utf-8"
        elif payload is None:
            body, ctype = b"", "application/json"
        else:
            body, ctype = json.dumps(payload).encode(), "application/json"
        headers = {"Content-Type": ctype, "X-Request-ID": request_id, "X-Content-Type-Options": "nosniff",
                   "Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"}
        headers.update(extra)
        headers["Content-Length"] = str(len(body))
        start_response(f"{status} {STATUS_TEXT.get(status, '')}".strip(), list(headers.items()))

        elapsed = time.perf_counter() - began
        metrics.record(status, elapsed)
        level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
        log.log(level, "request", extra={"fields": {
            "request_id": request_id, "method": environ["REQUEST_METHOD"],
            "path": environ.get("PATH_INFO", "/"), "status": status,
            "duration_ms": round(elapsed * 1000, 1)}})
        return [body]

    return app


def _prometheus(metrics: Metrics, svc: ExpenseService) -> str:
    rows = svc.conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()["n"]
    lines = ["# HELP expense_tracker_requests_total HTTP requests handled by this worker.",
             "# TYPE expense_tracker_requests_total counter"]
    with metrics.lock:
        for status, n in sorted(metrics.by_status.items()):
            lines.append(f'expense_tracker_requests_total{{status="{status}"}} {n}')
        lines += ["# TYPE expense_tracker_request_seconds_sum counter",
                  f"expense_tracker_request_seconds_sum {metrics.duration_sum:.6f}",
                  "# TYPE expense_tracker_request_seconds_count counter",
                  f"expense_tracker_request_seconds_count {metrics.count}"]
    lines += ["# TYPE expense_tracker_uptime_seconds gauge",
              f"expense_tracker_uptime_seconds {int(time.time() - metrics.started)}",
              "# TYPE expense_tracker_expenses gauge", f"expense_tracker_expenses {rows}"]
    return "\n".join(lines) + "\n"


def main():
    """Development server only. Production uses gunicorn (see Dockerfile)."""
    import os
    from wsgiref.simple_server import make_server
    port = int(os.environ.get("PORT", "8000"))
    with make_server("127.0.0.1", port, create_app()) as server:
        print(f"Dashboard and API on http://127.0.0.1:{port}  (Ctrl+C to stop)")
        server.serve_forever()


if __name__ == "__main__":
    main()
