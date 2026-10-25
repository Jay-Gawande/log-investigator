"""Shared test setup.

The app reads its configuration and builds the DB engine and the LLM client at
import time, so the environment has to be fixed before any `app.*` import.
Unit tests never touch a real database or LLM: the DB helper and the LLM client
are replaced with fakes inside each test.

Integration tests (tests/integration) talk to a real MariaDB and only run when
INTEGRATION_DB_URL is set.
"""
import os

INTEGRATION_DB_URL = os.environ.get("INTEGRATION_DB_URL")

# Force test values so a developer's real .env (and real API key) is never used.
os.environ["DB_URL"] = INTEGRATION_DB_URL or "mysql+pymysql://test:test@127.0.0.1:3306/testdb"
os.environ["LLM_BASE_URL"] = "http://localhost:9/v1"
os.environ["LLM_API_KEY"] = "test-key"
os.environ["LLM_MODEL"] = "test-model"

import pandas as pd  # noqa: E402
import pytest  # noqa: E402


def pytest_collection_modifyitems(config, items):
    if INTEGRATION_DB_URL:
        return
    skip = pytest.mark.skip(reason="set INTEGRATION_DB_URL to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def ts():
    """Shorthand for building timestamps on the incident day."""
    def _ts(hms, day="2026-10-01"):
        return pd.Timestamp(f"{day} {hms}")
    return _ts


@pytest.fixture
def timeline_rows(ts):
    """Timeline of a database outage: db-service broke first, the rest are symptoms,
    and auth-service has a tiny amount of harmless background noise."""
    return [
        {"service": "auth-service", "level": "WARN", "error_type": "BAD_PASSWORD",
         "first_seen": ts("14:04:10"), "last_seen": ts("14:10:00"), "occurrences": 2},
        {"service": "db-service", "level": "ERROR", "error_type": "DB_CONNECTION_FAILED",
         "first_seen": ts("14:05:00.060"), "last_seen": ts("14:16:50"), "occurrences": 100},
        {"service": "order-service", "level": "ERROR", "error_type": "DEPENDENCY_FAILURE",
         "first_seen": ts("14:05:03.100"), "last_seen": ts("14:16:53"), "occurrences": 100},
        {"service": "api-gateway", "level": "ERROR", "error_type": "TIMEOUT",
         "first_seen": ts("14:05:03.150"), "last_seen": ts("14:16:54"), "occurrences": 100},
    ]


@pytest.fixture
def evidence(timeline_rows, ts):
    """Evidence dict shaped like app.investigator.evidence.collect_evidence output."""
    return {
        "period": {
            "start": ts("14:05:00"), "end": ts("14:17:00"),
            "bad_lines_in_window": 300, "peak_bad_per_minute": 30,
            "baseline_bad_per_minute": 0.0, "other_windows_found": 0,
        },
        "services": [
            {"service": "db-service", "errors": 100, "warns": 0, "total_lines": 160,
             "first_error": ts("14:05:00.060"), "avg_latency_ms": 1800.0},
            {"service": "auth-service", "errors": 0, "warns": 0, "total_lines": 160,
             "first_error": pd.NaT, "avg_latency_ms": 27.0},
        ],
        "error_groups": [
            {"service": "db-service", "level": "ERROR", "error_type": "DB_CONNECTION_FAILED",
             "pattern": "Connection refused after <n> retries", "count": 100,
             "first_seen": ts("14:05:00.060"), "last_seen": ts("14:16:50")},
        ],
        "traces": {
            "requests_sampled": 100,
            "common_paths": [{"path": "api-gateway:INFO > db-service:ERROR", "count": 100}],
            "sample_traces": [],
        },
        "timeline": timeline_rows,
    }
