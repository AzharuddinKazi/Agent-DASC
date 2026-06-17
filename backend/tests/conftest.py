import pytest
import json
import os
from datetime import datetime
from pathlib import Path


LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def pytest_configure(config):
    config._test_results = []
    config._session_start = datetime.now()


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.failed):
        result = {
            "test_id":   report.nodeid,
            "outcome":   report.outcome,
            "duration":  round(report.duration, 4),
            "when":      report.when,
        }
        if report.failed and report.longrepr:
            result["failure"] = str(report.longrepr)
        pytest.config_holder._test_results.append(result)


def pytest_sessionstart(session):
    pytest.config_holder = session.config
    session.config._test_results = []
    session.config._session_start = datetime.now()


def pytest_sessionfinish(session, exitstatus):
    results = getattr(session.config, "_test_results", [])
    start   = getattr(session.config, "_session_start", datetime.now())

    passed  = [r for r in results if r["outcome"] == "passed"]
    failed  = [r for r in results if r["outcome"] == "failed"]
    total   = len(results)

    timestamp = start.strftime("%Y%m%d_%H%M%S")
    log_file  = LOGS_DIR / f"test_run_{timestamp}.json"

    report = {
        "run_id":       timestamp,
        "started_at":   start.isoformat(),
        "finished_at":  datetime.now().isoformat(),
        "summary": {
            "total":   total,
            "passed":  len(passed),
            "failed":  len(failed),
            "exit_status": exitstatus,
        },
        "passed_tests": [r["test_id"] for r in passed],
        "failed_tests": [
            {"test_id": r["test_id"], "reason": r.get("failure", "")}
            for r in failed
        ],
        "all_results":  results,
    }

    log_file.write_text(json.dumps(report, indent=2))
    print(f"\n── Test report saved: {log_file}")