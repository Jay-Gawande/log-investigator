import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.investigator.report import to_markdown

GOOD = {
    "description": "Users reported checkout failures around 2 PM",
    "start": "2026-10-01T00:00:00",
    "end": "2026-10-01T23:59:59",
}


@pytest.fixture
def client(monkeypatch):
    # never run a real investigation from these tests
    monkeypatch.setattr(main, "investigate",
                        lambda d, s, e: {"status": "no_anomaly_found", "incident": d})
    return TestClient(main.app)


def field_locs(response):
    return [tuple(err["loc"]) for err in response.json()["detail"]]


# ---------------------------------------------------------------- request validation

def test_valid_request_still_works(client):
    r = client.post("/investigate", json=GOOD)
    assert r.status_code == 200
    assert r.json()["status"] == "no_anomaly_found"


def test_end_before_start_is_rejected_on_the_end_field(client):
    r = client.post("/investigate", json={**GOOD, "start": "2026-10-02T00:00:00", "end": "2026-10-01T00:00:00"})
    assert r.status_code == 422
    assert ("body", "end") in field_locs(r)
    assert "end must be after start" in r.text


def test_equal_start_and_end_is_rejected(client):
    r = client.post("/investigate", json={**GOOD, "end": GOOD["start"]})
    assert r.status_code == 422


def test_range_over_31_days_is_rejected(client):
    r = client.post("/investigate", json={**GOOD, "start": "2026-01-01T00:00:00", "end": "2026-10-01T00:00:00"})
    assert r.status_code == 422
    assert "range too large" in r.text


@pytest.mark.parametrize("description", ["", "   "])
def test_blank_description_is_rejected(client, description):
    r = client.post("/investigate", json={**GOOD, "description": description})
    assert r.status_code == 422
    assert ("body", "description") in field_locs(r)


def test_description_is_trimmed(monkeypatch):
    seen = {}
    monkeypatch.setattr(main, "investigate",
                        lambda d, s, e: seen.update(d=d) or {"status": "no_anomaly_found", "incident": d})
    TestClient(main.app).post("/investigate", json={**GOOD, "description": "  checkout down  "})
    assert seen["d"] == "checkout down"


def test_report_endpoint_uses_the_same_validation(client):
    r = client.post("/investigate/report", json={**GOOD, "end": GOOD["start"]})
    assert r.status_code == 422


def test_bad_start_does_not_crash_the_end_validator(client):
    r = client.post("/investigate", json={**GOOD, "start": "not-a-date"})
    assert r.status_code == 422


# ---------------------------------------------------------------- /report/render

def test_render_no_anomaly(client):
    r = client.post("/report/render", json={"status": "no_anomaly_found", "incident": "slow checkout"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "No anomalous period was found" in r.text


def test_render_matches_to_markdown_for_a_full_result(client, evidence):
    result = {
        "status": "ok",
        "incident": "Users reported checkout failures",
        "requested_range": {"start": "2026-10-01 00:00:00", "end": "2026-10-01 23:59:59"},
        **evidence,
        "hypothesis": {"root_cause_service": "db-service", "root_cause_error_type": "DB_CONNECTION_FAILED",
                       "propagation_path": ["db-service", "order-service"], "confidence": 0.9,
                       "source": "llm", "explanation": "The database refused connections first."},
        "verification": {"error_exists_in_window": True, "appeared_first": True,
                         "coverage_of_failing_requests": 1.0, "verified": True},
        "attempts": [{"attempt": 1, "hypothesis": {}, "verification": {"verified": True}}],
    }
    # make the result JSON-safe the way /investigate does (timestamps as strings, NaT as null)
    from app.investigator.pipeline import to_jsonable
    safe = to_jsonable(result)

    r = client.post("/report/render", json=safe)

    assert r.status_code == 200
    assert r.text == to_markdown(safe)
    assert "# Incident Investigation Report" in r.text
    assert "db-service" in r.text


def test_render_rejects_unrelated_json(client):
    assert client.post("/report/render", json={"hello": "world"}).status_code == 422


def test_render_rejects_incomplete_ok_result(client):
    r = client.post("/report/render", json={"status": "ok", "incident": "x"})
    assert r.status_code == 422
    assert "incomplete investigation result" in r.json()["detail"]


def test_render_rejects_non_object_body(client):
    assert client.post("/report/render", json=[1, 2, 3]).status_code == 422
