#!/usr/bin/env python3
"""Post-deployment smoke test. Safe to run against staging or production: the record it
creates is deleted again.

Usage:  python scripts/smoke_test.py https://my-app.onrender.com --api-key KEY [--wait 90]
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


def wait_for_health(base, seconds):
    deadline, last = time.time() + seconds, "no response"
    while time.time() < deadline:
        try:
            status, body = call(base, "/health", timeout=10)
            if status == 200 and isinstance(body, dict) and body.get("status") == "ok":
                return body
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
    args = ap.parse_args()
    base, key, failures = args.base_url, args.api_key, 0

    def check(name, ok, detail=""):
        nonlocal failures
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))
        failures += 0 if ok else 1
        return ok

    try:
        health = wait_for_health(base, args.wait)
        check("health endpoint is healthy", True)
        print(f"       version={health['version']} environment={health['environment']}")
    except AssertionError as exc:
        check("health endpoint is healthy", False, str(exc))
        return 1

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
        status, summary = call(base, "/api/summary", key=key)
        check("summary endpoint works", status == 200 and "total" in summary)
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
