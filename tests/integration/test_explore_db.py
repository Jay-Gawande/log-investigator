"""Explorer endpoints against a real MariaDB (opt-in).

    INTEGRATION_DB_URL=mysql+pymysql://loguser:logpass@127.0.0.1:3306/logsdb uv run pytest -m integration

Same safety rules as test_pipeline_db.py: rows are written for 2001-01-01 only, removed afterwards,
and the tests refuse to run if that day already contains data.
"""
import random
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration

DAY = datetime(2001, 1, 1)
DAY_END = DAY + timedelta(days=1)
RANGE = {"start": "2001-01-01T00:00:00", "end": "2001-01-01T23:59:59"}
INC_START_MIN = 14 * 60 + 5
INC_LEN_MIN = 30


@pytest.fixture(scope="module")
def db_engine():
    from app.db import engine
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"database not reachable: {exc}")
    return engine


@pytest.fixture
def seeded_day(db_engine):
    """Fill 2001-01-01 with a db_failure incident, then clean up."""
    from app import generator
    from app.explore import queries

    with db_engine.connect() as c:
        existing = c.execute(
            text("SELECT COUNT(*) FROM logs WHERE ts >= :a AND ts < :b"), {"a": DAY, "b": DAY_END}
        ).scalar()
    if existing:
        pytest.fail("logs already has rows dated 2001-01-01; refusing to touch them")

    random.seed(2024)
    generator.generate(20000, DAY, "db_failure", INC_START_MIN, INC_LEN_MIN)
    queries.clear_meta_cache()
    yield
    with db_engine.begin() as c:
        c.execute(text("DELETE FROM logs WHERE ts >= :a AND ts < :b"), {"a": DAY, "b": DAY_END})
    queries.clear_meta_cache()


@pytest.fixture
def client():
    import app.main as main
    return TestClient(main.app)


def test_meta_reports_the_seeded_data(seeded_day, client):
    body = client.get("/meta").json()
    assert body["min_ts"].startswith("2001-01-01")
    assert {"api-gateway", "auth-service", "order-service", "db-service"} <= set(body["services"])
    assert {"ERROR", "INFO", "WARN"} <= set(body["levels"])
    assert "DB_CONNECTION_FAILED" in body["error_types"]
    assert body["total_rows"] > 0


def test_overview_peaks_inside_the_incident_window(seeded_day, client, db_engine):
    body = client.get("/logs/overview", params=RANGE).json()
    points = body["points"]
    assert body["bucket_minutes"] == 5
    assert len(points) == 288                       # a full day of 5-minute buckets, gaps filled

    peak = max(points, key=lambda p: p["errors"] + p["warns"])
    peak_ts = datetime.fromisoformat(peak["ts"])
    incident_start = DAY + timedelta(minutes=INC_START_MIN)
    incident_end = incident_start + timedelta(minutes=INC_LEN_MIN)
    assert incident_start - timedelta(minutes=5) <= peak_ts <= incident_end

    with db_engine.connect() as c:
        in_db = c.execute(
            text("SELECT COUNT(*) FROM logs WHERE ts BETWEEN :a AND :b"),
            {"a": "2001-01-01 00:00:00", "b": "2001-01-01 23:59:59"},
        ).scalar()
    assert sum(p["total"] for p in points) == in_db


def test_overview_service_filter_and_explicit_bucket(seeded_day, client):
    body = client.get("/logs/overview", params={**RANGE, "service": "db-service", "bucket_minutes": 15}).json()
    assert body["bucket_minutes"] == 15
    assert len(body["points"]) == 96
    assert sum(p["errors"] for p in body["points"]) > 0
    auth = client.get("/logs/overview", params={**RANGE, "service": "auth-service"}).json()
    assert sum(p["errors"] for p in auth["points"]) == 0   # auth-service stays healthy


def test_logs_filters_return_only_matching_rows(seeded_day, client):
    body = client.get("/logs", params={**RANGE, "service": "db-service", "level": "ERROR", "limit": 50}).json()
    assert 0 < len(body["items"]) <= 50
    assert all(i["service"] == "db-service" and i["level"] == "ERROR" for i in body["items"])
    assert all(i["error_type"] == "DB_CONNECTION_FAILED" for i in body["items"])


def test_logs_paging_is_consistent(seeded_day, client):
    params = {**RANGE, "level": "ERROR", "limit": 10}
    first = client.get("/logs", params=params).json()
    second = client.get("/logs", params={**params, "offset": 10}).json()
    assert first["has_more"] is True
    assert {i["id"] for i in first["items"]}.isdisjoint({i["id"] for i in second["items"]})
    timestamps = [i["ts"] for i in first["items"]]
    assert timestamps == sorted(timestamps)


def test_logs_order_desc_and_text_search(seeded_day, client):
    desc = client.get("/logs", params={**RANGE, "order": "desc", "limit": 20}).json()["items"]
    stamps = [i["ts"] for i in desc]
    assert stamps == sorted(stamps, reverse=True)

    sample = client.get("/logs", params={**RANGE, "level": "ERROR", "limit": 1}).json()["items"][0]
    word = sample["message"].split()[0]
    hits = client.get("/logs", params={**RANGE, "q": word, "limit": 20}).json()["items"]
    assert hits and all(word.lower() in i["message"].lower() for i in hits)


def test_logs_literal_percent_does_not_match_everything(seeded_day, client):
    body = client.get("/logs", params={**RANGE, "q": "%", "limit": 5}).json()
    assert all("%" in i["message"] for i in body["items"])   # empty list is fine too


def test_request_trace_for_a_failing_request(seeded_day, client):
    errors = client.get("/logs", params={**RANGE, "level": "ERROR", "limit": 1}).json()["items"]
    rid = errors[0]["request_id"]

    trace = client.get(f"/requests/{rid}").json()

    assert trace["request_id"] == rid
    assert trace["has_errors"] is True
    assert "db-service" in trace["services"]
    offsets = [e["offset_ms"] for e in trace["events"]]
    assert offsets == sorted(offsets) and offsets[0] == 0
    assert trace["duration_ms"] == offsets[-1]
    assert all(e["service"] for e in trace["events"])


def test_request_trace_unknown_id_is_404(seeded_day, client):
    r = client.get("/requests/00000000-0000-4000-8000-000000000000")
    assert r.status_code == 404


def test_logs_request_id_filter_matches_trace(seeded_day, client):
    rid = client.get("/logs", params={**RANGE, "limit": 1}).json()["items"][0]["request_id"]
    rows = client.get("/logs", params={**RANGE, "request_id": rid, "limit": 100}).json()["items"]
    trace = client.get(f"/requests/{rid}").json()
    assert {r["id"] for r in rows} == {e["id"] for e in trace["events"]}
