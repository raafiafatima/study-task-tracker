"""Smoke test for Study Task Tracker. Standard library only.

Usage:
    python scripts/smoke_test.py                       # uses BASE_URL or http://localhost:8080
    python scripts/smoke_test.py http://localhost:8080

Every request goes through the given base URL (Nginx), like a browser would.
It creates a few tasks, so do not point it at a database you care about.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BASE_URL", "http://localhost:8080")).rstrip("/")
failures = []


def call(method, path, body=None, raw=None, content_type="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE_URL + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.headers, err.read()


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name + ("" if condition else f"  ({detail})"))
    if not condition:
        failures.append(name)


def wait_until_ready(timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if call("GET", "/health")[0] == 200:
                return True
        except OSError:
            pass
        time.sleep(2)
    return False


def main():
    print(f"Testing {BASE_URL}")
    if not wait_until_ready():
        print("FAIL  /health never returned 200 (is the stack running?)")
        return 1

    status, headers, body = call("GET", "/")
    check("GET / serves the page", status == 200 and b"<h1" in body and "text/html" in headers.get("Content-Type", ""), status)

    status, _, body = call("GET", "/health")
    check("GET /health through Nginx is 200", status == 200, status)

    marker = uuid.uuid4().hex[:8]
    title = f"  smoke test {marker}  "
    status, _, body = call("POST", "/api/tasks", {"title": title})
    created = json.loads(body) if status == 201 else {}
    check("POST /api/tasks with a valid title returns 201", status == 201, status)
    check("Created title is trimmed", created.get("title") == title.strip(), created)
    check("Created task has id and created_at", "id" in created and "created_at" in created, created)

    status, _, body = call("GET", "/api/tasks")
    tasks = json.loads(body) if status == 200 else []
    check("GET /api/tasks returns 200 and a list", status == 200 and isinstance(tasks, list), status)
    check("New task is listed", any(t.get("id") == created.get("id") for t in tasks))
    check("Newest task is first", bool(tasks) and tasks[0].get("id") == created.get("id"))

    status, _, body = call("POST", "/api/tasks", {"title": "x" * 120})
    check("120-character title is accepted", status == 201, status)

    bad_cases = [
        ("empty title", {"title": ""}),
        ("whitespace-only title", {"title": "   "}),
        ("121-character title", {"title": "x" * 121}),
        ("missing title", {}),
        ("non-string title", {"title": 123}),
    ]
    for label, payload in bad_cases:
        status, _, body = call("POST", "/api/tasks", payload)
        try:
            has_error = bool(json.loads(body).get("error"))
        except ValueError:
            has_error = False
        check(f"Rejected with 400 JSON error: {label}", status == 400 and has_error, status)

    status, _, _ = call("POST", "/api/tasks", raw=b"not json")
    check("Rejected with 400: body is not JSON", status == 400, status)

    status, _, _ = call("GET", "/api/does-not-exist")
    check("Unknown API path returns 404 from Flask", status == 404, status)

    if failures:
        print(f"\n{len(failures)} check(s) failed.")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
