"""Run every test and write docs/TEST_RESULTS.md (test id, description, PASS/FAIL).

Usage:  PYTHONPATH=src python tools/generate_test_report.py
"""
import io
import os
import sys
import time
import unittest
from datetime import date

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main() -> int:
    suite = unittest.defaultTestLoader.discover(os.path.join(ROOT, "tests"))
    tests = [t for t in flatten(suite) if t is not None]
    results, started = [], time.perf_counter()
    for test in tests:
        result = unittest.TestResult()
        test.run(result)
        status = "PASS" if result.wasSuccessful() else "FAIL"
        doc = (test.shortDescription() or test.id()).strip()
        test_id, _, text = doc.partition(" ")
        results.append((test_id, text, status, test.id().split(".")[0]))
    elapsed = time.perf_counter() - started
    results.sort(key=lambda r: (r[0].split("-")[0], int(r[0].split("-")[1]) if "-" in r[0] and r[0].split("-")[1].isdigit() else 0))
    passed = sum(1 for r in results if r[2] == "PASS")
    lines = [f"# Test Results", "", f"Generated: {date.today().isoformat()}  ",
             f"Total: {len(results)}  |  Passed: {passed}  |  Failed: {len(results) - passed}  |  Time: {elapsed:.2f}s", "",
             "| ID | Test case | Result | File |", "|---|---|---|---|"]
    lines += [f"| {i} | {d} | {s} | {f}.py |" for i, d, s, f in results]
    out = os.path.join(ROOT, "docs", "TEST_RESULTS.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"{passed}/{len(results)} passed; wrote {out}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
