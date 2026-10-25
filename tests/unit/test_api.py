import pytest
from fastapi.testclient import TestClient

import app.main as main

PAYLOAD = {
    "description": "Users reported checkout failures around 2 PM",
    "start": "2026-10-01T00:00:00",
    "end": "2026-10-01T23:59:59",
}


@pytest.fixture
def client():
    return TestClient(main.app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_investigate_returns_json_and_parses_dates(client, monkeypatch):
    seen = {}

    def fake(description, start, end):
        seen.update(description=description, start=start, end=end)
        return {"status": "ok", "incident": description}

    monkeypatch.setattr(main, "investigate", fake)
    r = client.post("/investigate", json=PAYLOAD)

    assert r.status_code == 200
    assert r.json() == {"status": "ok", "incident": PAYLOAD["description"]}
    assert seen["description"] == PAYLOAD["description"]
    assert seen["start"].year == 2026 and seen["start"].hour == 0
    assert seen["end"].hour == 23 and seen["end"].second == 59


def test_investigate_passes_through_no_anomaly(client, monkeypatch):
    monkeypatch.setattr(main, "investigate",
                        lambda d, s, e: {"status": "no_anomaly_found", "incident": d})
    r = client.post("/investigate", json=PAYLOAD)
    assert r.json()["status"] == "no_anomaly_found"


def test_report_endpoint_returns_markdown(client, monkeypatch, evidence):
    result = {
        "status": "no_anomaly_found", "incident": "slow checkout",
    }
    monkeypatch.setattr(main, "investigate", lambda d, s, e: result)
    r = client.post("/investigate/report", json=PAYLOAD)

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "# Investigation Report" in r.text
    assert "No anomalous period was found" in r.text


@pytest.mark.parametrize("missing", ["description", "start", "end"])
def test_missing_fields_are_rejected(client, missing):
    body = {k: v for k, v in PAYLOAD.items() if k != missing}
    assert client.post("/investigate", json=body).status_code == 422
    assert client.post("/investigate/report", json=body).status_code == 422


def test_invalid_date_is_rejected(client):
    body = {**PAYLOAD, "start": "not-a-date"}
    assert client.post("/investigate", json=body).status_code == 422


def test_unknown_route_and_wrong_method(client):
    assert client.get("/nope").status_code == 404
    assert client.get("/investigate").status_code == 405
