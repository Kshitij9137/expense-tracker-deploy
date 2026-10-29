#!/usr/bin/env python3
"""Tiny load test using only the standard library.

Usage: python scripts/loadtest.py http://127.0.0.1:8001 --api-key KEY --requests 2000 --threads 8
Mix: 50% GET /health, 30% GET /api/expenses?category=load, 20% POST /api/expenses.
Created rows are deleted afterwards. Prints requests/second and latency percentiles.
"""
import argparse
import json
import statistics
import threading
import time
import urllib.error
import urllib.request


def request(base, path, method="GET", key=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    if key:
        req.add_header("X-API-Key", key)
    if data:
        req.add_header("Content-Type", "application/json")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = resp.read()
            code = resp.status
    except urllib.error.HTTPError as exc:
        payload, code = exc.read(), exc.code
    return code, time.perf_counter() - started, payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--requests", type=int, default=2000)
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()
    base, key = args.base_url.rstrip("/"), args.api_key
    lock, latencies, codes, created = threading.Lock(), [], {}, []
    counter = {"n": 0}

    def worker():
        while True:
            with lock:
                i = counter["n"]
                counter["n"] += 1
            if i >= args.requests:
                return
            kind = i % 10
            if kind < 5:
                code, secs, _ = request(base, "/health")
            elif kind < 8:
                code, secs, _ = request(base, "/api/expenses?category=load", key=key)
            else:
                code, secs, payload = request(base, "/api/expenses", "POST", key,
                                              {"amount": "1.00", "category": "load", "date": "2026-10-01"})
                if code == 201:
                    with lock:
                        created.append(json.loads(payload)["id"])
            with lock:
                latencies.append(secs)
                codes[code] = codes.get(code, 0) + 1

    start = time.perf_counter()
    threads = [threading.Thread(target=worker) for _ in range(args.threads)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    total = time.perf_counter() - start
    for row_id in created:
        request(base, f"/api/expenses/{row_id}", "DELETE", key)
    ms = sorted(x * 1000 for x in latencies)
    pct = lambda p: ms[min(len(ms) - 1, int(len(ms) * p))]
    errors = sum(n for c, n in codes.items() if c >= 500 or c == 0)
    print(f"requests={len(ms)} threads={args.threads} time={total:.2f}s throughput={len(ms) / total:.0f} req/s")
    print(f"latency ms: mean={statistics.mean(ms):.1f} p50={pct(.5):.1f} p95={pct(.95):.1f} p99={pct(.99):.1f} max={ms[-1]:.1f}")
    print(f"status codes: {dict(sorted(codes.items()))}  server errors: {errors}")


if __name__ == "__main__":
    main()
