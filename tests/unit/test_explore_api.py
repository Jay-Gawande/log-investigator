import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.explore import queries

RANGE = {"start": "2026-10-01T00:00:00", "end": "2026-10-01T23:59:59"}
UUID = "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture
def client():
    return TestClient(main.app)


# ---------------------------------------------------------------- /meta

def test_meta_returns_query_result(client, monkeypatch):
    payload = {"min_ts": "2026-10-01T00:00:01.120", "max_ts": "2026-10-01T23:59:58.410",
               "total_rows": 10, "services": ["a"], "levels": ["INFO"], "error_types": []}
    monkeypatch.setattr(queries, "get_meta", lambda: payload)
    r = client.get("/meta")
    assert r.status_code == 200
    assert r.json() == payload


def test_meta_with_empty_table(client, monkeypatch):
    monkeypatch.setattr(queries, "get_meta", lambda: {
        "min_ts": None, "max_ts": None, "total_rows": 0,
        "services": [], "levels": [], "error_types": []})
    body = client.get("/meta").json()
    assert body["min_ts"] is None and body["total_rows"] == 0


# ---------------------------------------------------------------- /logs/overview

def test_overview_passes_parsed_parameters(client, monkeypatch):
    seen = {}

    def fake(start, end, bucket_minutes, service):
        seen.update(start=start, end=end, bucket=bucket_minutes, service=service)
        return {"bucket_minutes": 5, "points": [{"ts": "2026-10-01T00:00:00.000", "errors": 1, "warns": 2, "total": 3}]}

    monkeypatch.setattr(queries, "get_overview", fake)
    r = client.get("/logs/overview", params={**RANGE, "bucket_minutes": 5, "service": "db-service"})

    assert r.status_code == 200
    assert r.json()["points"][0]["errors"] == 1
    assert seen["bucket"] == 5 and seen["service"] == "db-service"
    assert seen["start"].hour == 0 and seen["end"].minute == 59


def test_overview_defaults_are_none(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(queries, "get_overview", lambda s, e, b, svc: seen.update(b=b, svc=svc) or
                        {"bucket_minutes": 1, "points": []})
    assert client.get("/logs/overview", params=RANGE).status_code == 200
    assert seen == {"b": None, "svc": None}


def test_overview_rejects_end_before_start(client):
    r = client.get("/logs/overview", params={"start": "2026-10-02T00:00:00", "end": "2026-10-01T00:00:00"})
    assert r.status_code == 422
    assert "end must be after start" in r.json()["detail"]


def test_overview_rejects_huge_range(client):
    r = client.get("/logs/overview", params={"start": "2026-01-01T00:00:00", "end": "2026-10-01T00:00:00"})
    assert r.status_code == 422
    assert "range too large" in r.json()["detail"]


def test_overview_query_errors_become_422(client, monkeypatch):
    def boom(*a, **k):
        raise ValueError("bucket_minutes must be one of [1, 5, 15, 30, 60]")

    monkeypatch.setattr(queries, "get_overview", boom)
    r = client.get("/logs/overview", params={**RANGE, "bucket_minutes": 7})
    assert r.status_code == 422
    assert "bucket_minutes" in r.json()["detail"]


def test_overview_requires_start_and_end(client):
    assert client.get("/logs/overview").status_code == 422


# ---------------------------------------------------------------- /logs

def _logs_result():
    return {
        "items": [{"id": 1, "ts": "2026-10-01T14:05:00.060", "service": "db-service", "level": "ERROR",
                   "request_id": UUID, "message": "refused", "error_type": "DB_CONNECTION_FAILED",
                   "latency_ms": 1800}],
        "limit": 100, "offset": 0, "has_more": False,
    }


def test_logs_defaults_and_filters_reach_the_query(client, monkeypatch):
    seen = {}

    def fake(start, end, **kw):
        seen.update(kw)
        return _logs_result()

    monkeypatch.setattr(queries, "search_logs", fake)
    r = client.get("/logs", params={**RANGE, "service": "db-service", "level": "ERROR", "q": "refused"})

    assert r.status_code == 200
    assert r.json()["items"][0]["service"] == "db-service"
    assert seen["service"] == "db-service" and seen["level"] == "ERROR" and seen["q"] == "refused"
    assert seen["order"] == "asc" and seen["limit"] == 100 and seen["offset"] == 0


@pytest.mark.parametrize("params", [
    {"limit": 501}, {"limit": 0}, {"offset": -1}, {"order": "sideways"}, {"q": "x" * 201},
])
def test_logs_rejects_bad_parameters(client, monkeypatch, params):
    monkeypatch.setattr(queries, "search_logs", lambda *a, **k: _logs_result())
    assert client.get("/logs", params={**RANGE, **params}).status_code == 422


def test_logs_rejects_bad_range(client):
    r = client.get("/logs", params={"start": "2026-10-02T00:00:00", "end": "2026-10-01T00:00:00"})
    assert r.status_code == 422


def test_logs_filters_response_through_the_model(client, monkeypatch):
    leaky = _logs_result()
    leaky["items"][0]["secret"] = "do not leak"
    monkeypatch.setattr(queries, "search_logs", lambda *a, **k: leaky)
    item = client.get("/logs", params=RANGE).json()["items"][0]
    assert "secret" not in item


# ---------------------------------------------------------------- /requests/{id}

def test_request_trace_ok(client, monkeypatch):
    trace = {
        "request_id": UUID, "start": "2026-10-01T14:05:00.000", "end": "2026-10-01T14:05:03.150",
        "duration_ms": 3150, "services": ["api-gateway"], "has_errors": True,
        "events": [{"id": 1, "ts": "2026-10-01T14:05:00.000", "offset_ms": 0, "service": "api-gateway",
                    "level": "INFO", "message": "start", "error_type": None, "latency_ms": 20}],
    }
    monkeypatch.setattr(queries, "request_trace", lambda rid: trace)
    r = client.get(f"/requests/{UUID}")
    assert r.status_code == 200
    assert r.json()["duration_ms"] == 3150
    assert r.json()["events"][0]["error_type"] is None


def test_request_trace_not_found(client, monkeypatch):
    monkeypatch.setattr(queries, "request_trace", lambda rid: None)
    r = client.get(f"/requests/{UUID}")
    assert r.status_code == 404


def test_request_trace_rejects_non_uuid_without_querying(client, monkeypatch):
    def boom(rid):
        raise AssertionError("must not query for an invalid id")

    monkeypatch.setattr(queries, "request_trace", boom)
    assert client.get("/requests/not-a-uuid").status_code == 422
    assert client.get("/requests/1%27%20OR%20%271%27=%271").status_code == 422
