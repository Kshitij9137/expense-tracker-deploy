#!/usr/bin/env python3
"""Post-deployment smoke test. Safe to run against staging or production: the record it
creates is deleted again.

Usage:  python scripts/smoke_test.py https://my-app.onrender.com --api-key KEY [--wait 90] [--expect-version 2.0.0]
Exit code 0 = all checks passed, 1 = a check failed (the pipeline should stop / roll back).
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def call(base, path, method="GET", key=None, body=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method)
    if key:
        req.add_header("X-API-Key", key)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw and "json" in resp.headers.get("Content-Type", "") else raw)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def wait_for_health(base, seconds, expect_version=None):
    """Wait until /health is ok AND (if given) reports the expected version, so the test never
    passes against the OLD release while the new one is still building."""
    deadline, last = time.time() + seconds, "no response"
    while time.time() < deadline:
        try:
            status, body = call(base, "/health", timeout=10)
            if status == 200 and isinstance(body, dict) and body.get("status") == "ok":
                if expect_version is None or body.get("version") == expect_version:
                    return body
                last = f"healthy but running version {body.get('version')}, waiting for {expect_version}"
            else:
                last = f"HTTP {status}"
        except Exception as exc:  # connection refused while the service is starting
            last = str(exc)
        time.sleep(3)
    raise AssertionError(f"/health did not become healthy within {seconds}s ({last})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--wait", type=int, default=60, help="seconds to wait for the service to start")
    ap.add_argument("--expect-version", default=None, help="wait until /health reports this version (e.g. 2.0.0)")
    args = ap.parse_args()
    base, key, failures = args.base_url, args.api_key, 0

    def check(name, ok, detail=""):
        nonlocal failures
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))
        failures += 0 if ok else 1
        return ok

    try:
        health = wait_for_health(base, args.wait, args.expect_version or None)
        check("health endpoint is healthy", True)
        print(f"       version={health['version']} environment={health['environment']}")
    except AssertionError as exc:
        check("health endpoint is healthy", False, str(exc))
        return 1

    status, page = call(base, "/")
    check("dashboard page is served without a key", status == 200 and "<title>Expense Tracker</title>" in str(page), f"got {status}")
    status, _ = call(base, "/static/app.js")
    check("dashboard script is served", status == 200)

    status, _ = call(base, "/api/expenses")
    check("unauthenticated request is rejected (401)", status == 401 or key == "", f"got {status}")
    status, _ = call(base, "/api/expenses", key="wrong-key-wrong-key")
    check("wrong API key is rejected (401)", status == 401 or key == "", f"got {status}")

    status, created = call(base, "/api/expenses", "POST", key, {"amount": "1.23", "category": "smoke-test", "note": "deployment check"})
    ok = check("create an expense (201)", status == 201 and isinstance(created, dict), f"got {status}: {created}")
    if ok:
        new_id = created["id"]
        status, listing = call(base, "/api/expenses?category=smoke-test", key=key)
        check("created expense appears in list", status == 200 and any(e["id"] == new_id for e in listing["expenses"]))
        check("list is paginated (reports total, limit, offset)", status == 200 and {"total", "limit", "offset"} <= set(listing))
        status, summary = call(base, "/api/summary", key=key)
        check("summary endpoint works", status == 200 and "total" in summary)
        status, insights = call(base, "/api/insights", key=key)
        check("insights endpoint works", status == 200 and "total" in insights, f"got {status}")
        status, monthly = call(base, "/api/monthly", key=key)
        check("monthly endpoint returns 12 months", status == 200 and len(monthly.get("months", [])) == 12, f"got {status}")
        status, csv_text = call(base, "/api/export.csv", key=key)
        check("CSV export works", status == 200 and str(csv_text).startswith("id,date,category"), f"got {status}")
        status, _ = call(base, f"/api/expenses/{new_id}", "DELETE", key)
        check("delete the test expense (204)", status == 204, f"got {status}")
    status, _ = call(base, "/api/expenses", "POST", key, {"amount": "abc", "category": "x"})
    check("invalid input returns 400, not 500", status == 400, f"got {status}")
    status, text = call(base, "/metrics", key=key)
    check("metrics endpoint works", status == 200 and "expense_tracker_requests_total" in str(text))

    print("RESULT:", "ALL CHECKS PASSED" if failures == 0 else f"{failures} CHECK(S) FAILED")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
