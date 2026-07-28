#!/usr/bin/env python3
"""Run the same query twice through the live API — once with the fraud-aml domain
pack's knowledge base fed to the Planner, once without — and print both results
side by side for comparison.

Usage:
    export DSSTAR_API_TEST_EMAIL=...
    export DSSTAR_API_TEST_PASSWORD=...
    uv run --project backend python scripts/compare_domain_knowledge.py \
        "Which merchant emirate has the highest fraud rate, and does that vary by channel?" \
        --task-type qa --pack fraud-aml

Auth: signs in to Supabase directly (same flow the frontend uses) to get a bearer
token — this exercises the API exactly as an external caller would, no service-key
shortcuts. Requires DSSTAR_API_TEST_EMAIL / DSSTAR_API_TEST_PASSWORD env vars.
"""

import argparse
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

API_BASE = os.getenv("DSSTAR_API_BASE", "http://localhost:8000")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

POLL_INTERVAL_S = 3
# Large multi-file datasets (e.g. the Medicare pack's 161MB outpatient claims CSV) push
# analyzer+finalizer well past 600s on free-tier models — 1200s gives real headroom
# without the client giving up while the backend is still legitimately working.
TIMEOUT_S = 1200


def sign_in(email: str, password: str) -> str:
    resp = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def submit_task(token: str, query: str, task_type: str, use_domain_knowledge: bool, pack_id: str | None) -> str:
    body = {
        "query": query,
        "task_type": task_type,
        "use_domain_knowledge": use_domain_knowledge,
        "domain_pack_id": pack_id,
    }
    resp = requests.post(
        f"{API_BASE}/api/v1/submit_task",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["task_id"]


def poll_task(token: str, task_id: str, label: str = "") -> dict:
    """Polls get_task until it finishes, printing live progress as it goes — every
    poll's status/current_agent, plus each new tasks.logs entry the instant it appears.
    Without this, output only appeared once at the very end (see summarize()), which
    looked indistinguishable from a hang during the ~1-4min a real pipeline run takes.
    flush=True on every print because stdout is block-buffered (not line-buffered) once
    it's redirected to a file/background task, not a tty — without it, prints still sit
    in the buffer and don't actually appear in the output file until the process exits.
    """
    prefix = f"[{label}] " if label else ""
    start = time.time()
    seen_logs = 0
    last_status = None

    while time.time() - start < TIMEOUT_S:
        resp = requests.get(
            f"{API_BASE}/api/v1/get_task/{task_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        row = resp.json()
        elapsed = round(time.time() - start, 1)

        for entry in (row.get("logs") or [])[seen_logs:]:
            print(f"  {prefix}+{elapsed:>6.1f}s  {entry.get('agent'):<12} {entry.get('message')}", flush=True)
        seen_logs = len(row.get("logs") or [])

        status_line = (row["status"], row.get("current_agent"))
        if status_line != last_status:
            print(f"  {prefix}+{elapsed:>6.1f}s  status={row['status']} current_agent={row.get('current_agent')}", flush=True)
            last_status = status_line

        if row["status"] in ("completed", "failed"):
            row["_elapsed_s"] = elapsed
            return row
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"Task {task_id} did not finish within {TIMEOUT_S}s")


def summarize(label: str, row: dict) -> None:
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    print(f"status:       {row['status']}")
    print(f"rounds_taken: {row.get('rounds_taken')}")
    print(f"elapsed:      {row.get('_elapsed_s')}s")
    result = row.get("final_result")
    try:
        parsed = json.loads(result) if isinstance(result, str) else result
        print(json.dumps(parsed, indent=2)[:3000])
    except Exception:
        print((result or "")[:3000])


def main():
    # stdout is block-buffered (not line-buffered) once redirected to a file or a
    # background task's output — without this, every print() below still sits in the
    # buffer and doesn't actually reach the output file until the process exits, which
    # is exactly what made a genuinely-running comparison look hung with zero output.
    sys.stdout.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", help="Query to run both with and without domain knowledge")
    parser.add_argument("--task-type", choices=["qa", "report"], default="qa")
    parser.add_argument("--pack", default="fraud-aml", help="Domain pack id to pin for the 'with' run")
    parser.add_argument("--out", default=None, help="Optional path to write both full results as JSON")
    args = parser.parse_args()

    email = os.getenv("DSSTAR_API_TEST_EMAIL")
    password = os.getenv("DSSTAR_API_TEST_PASSWORD")
    if not email or not password:
        sys.exit("Set DSSTAR_API_TEST_EMAIL and DSSTAR_API_TEST_PASSWORD env vars first.")

    print(f"Signing in as {email}...")
    token = sign_in(email, password)

    print(f"Submitting WITH domain knowledge (pack={args.pack})...")
    with_id = submit_task(token, args.query, args.task_type, True, args.pack)
    print(f"  task_id={with_id}, polling...")
    with_row = poll_task(token, with_id, label="WITH")
    summarize(f"WITH domain knowledge ({args.pack})", with_row)

    print(f"\nSubmitting WITHOUT domain knowledge...")
    without_id = submit_task(token, args.query, args.task_type, False, None)
    print(f"  task_id={without_id}, polling...")
    without_row = poll_task(token, without_id, label="WITHOUT")
    summarize("WITHOUT domain knowledge", without_row)

    if args.out:
        with open(args.out, "w") as f:
            json.dump({"query": args.query, "with_domain_knowledge": with_row, "without_domain_knowledge": without_row}, f, indent=2)
        print(f"\nSaved full results to {args.out}")


if __name__ == "__main__":
    main()
