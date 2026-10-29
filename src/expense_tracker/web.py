"""HTTP API (WSGI application) so the Expense Tracker can run as a production web service.

Endpoints
  GET    /health                public  liveness + database check (used by monitors and load balancers)
  GET    /metrics               key     Prometheus-style text metrics
  GET    /api/expenses          key     list (query: category, start, end)
  POST   /api/expenses          key     create (JSON body: amount, category, date, note)
  DELETE /api/expenses/<id>     key     delete
  GET    /api/summary           key     totals per category (query: start, end)

Authentication is the X-API-Key header. Only /health is public.
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

from . import __version__
from .config import Settings
from .database import connect
from .models import ValidationError, format_money
from .service import ExpenseService

log = logging.getLogger("expense_tracker")


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
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


STATUS_TEXT = {200: "OK", 201: "Created", 204: "No Content", 400: "Bad Request", 401: "Unauthorized",
               404: "Not Found", 405: "Method Not Allowed", 413: "Payload Too Large",
               500: "Internal Server Error", 503: "Service Unavailable"}


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


def create_app(settings: Settings = None):
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    metrics = Metrics()
    if not settings.auth_enabled:
        log.warning("API_KEY is not set: authentication is DISABLED (allowed in development only)")
    log.info("application starting", extra={"fields": {
        "version": __version__, "environment": settings.environment, "db": settings.db_path}})
    # Create the database file and schema once at start-up.
    connect(settings.db_path).close()

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

    def expense_json(e) -> dict:
        return {"id": e.id, "amount": f"{e.amount_cents / 100:.2f}", "category": e.category,
                "description": e.description, "date": e.spent_on}

    def route(environ, svc):
        method, path = environ["REQUEST_METHOD"], environ.get("PATH_INFO", "/").rstrip("/") or "/"
        query = {k: v[0] for k, v in _parse_qs(environ.get("QUERY_STRING", "")).items()}

        if path == "/health":
            if method != "GET":
                raise HttpError(405, "Method not allowed")
            svc.conn.execute("SELECT 1").fetchone()
            return 200, {"status": "ok", "version": __version__, "environment": settings.environment,
                         "uptime_seconds": int(time.time() - metrics.started)}

        if not authorised(environ):
            raise HttpError(401, "Missing or invalid API key")

        if path == "/metrics":
            if method != "GET":
                raise HttpError(405, "Method not allowed")
            return 200, _prometheus(metrics, svc)
        if path == "/api/expenses":
            if method == "GET":
                items = svc.list_expenses(query.get("category"), query.get("start"), query.get("end"))
                return 200, {"count": len(items), "expenses": [expense_json(e) for e in items]}
            if method == "POST":
                body = read_json(environ)
                e = svc.add_expense(body.get("amount"), body.get("category"),
                                    body.get("date") or date.today().isoformat(), str(body.get("note", "")))
                return 201, expense_json(e)
            raise HttpError(405, "Method not allowed")
        m = re.fullmatch(r"/api/expenses/(\d+)", path)
        if m:
            if method == "DELETE":
                svc.delete_expense(int(m.group(1)))
                return 204, None
            if method == "GET":
                return 200, expense_json(svc.get_expense(int(m.group(1))))
            raise HttpError(405, "Method not allowed")
        if path == "/api/summary":
            if method != "GET":
                raise HttpError(405, "Method not allowed")
            totals = svc.total_by_category(query.get("start"), query.get("end"))
            return 200, {"total": format_money(sum(totals.values())),
                         "categories": {k: format_money(v) for k, v in totals.items()}}
        raise HttpError(404, "Not found")

    def app(environ, start_response):
        began = time.perf_counter()
        request_id = environ.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex[:12]
        request_id = re.sub(r"[^A-Za-z0-9_.-]", "", request_id)[:64] or uuid.uuid4().hex[:12]
        conn = None
        try:
            conn = connect(settings.db_path)
            status, payload = route(environ, ExpenseService(conn))
        except HttpError as exc:
            status, payload = exc.status, {"error": exc.message}
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

        if isinstance(payload, str):
            body, ctype = payload.encode(), "text/plain; version=0.0.4; charset=utf-8"
        elif payload is None:
            body, ctype = b"", "application/json"
        else:
            body, ctype = json.dumps(payload).encode(), "application/json"
        headers = [("Content-Type", ctype), ("Content-Length", str(len(body))),
                   ("X-Request-ID", request_id), ("X-Content-Type-Options", "nosniff"),
                   ("Cache-Control", "no-store"), ("X-Frame-Options", "DENY")]
        start_response(f"{status} {STATUS_TEXT.get(status, '')}".strip(), headers)

        elapsed = time.perf_counter() - began
        metrics.record(status, elapsed)
        level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
        log.log(level, "request", extra={"fields": {
            "request_id": request_id, "method": environ["REQUEST_METHOD"],
            "path": environ.get("PATH_INFO", "/"), "status": status,
            "duration_ms": round(elapsed * 1000, 1)}})
        return [body]

    return app


def _parse_qs(qs: str) -> dict:
    from urllib.parse import parse_qs
    return parse_qs(qs, keep_blank_values=False)


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
        print(f"Development server on http://127.0.0.1:{port}  (Ctrl+C to stop)")
        server.serve_forever()


if __name__ == "__main__":
    main()
