import pandas as pd

from app.investigator import correlate


def fake_query(df):
    return lambda sql, **params: df.copy()


def test_template_collapses_numbers():
    a = correlate._template("could not connect to mysql primary after 3 retries")
    b = correlate._template("could not connect to mysql primary after 5 retries")
    assert a == b == "could not connect to mysql primary after <n> retries"


def test_template_masks_usernames_and_uuids():
    t = correlate._template("Invalid password attempt for user john_doe42")
    assert t == "Invalid password attempt for user <user>"
    t = correlate._template("request 123e4567-e89b-12d3-a456-426614174000 failed")
    assert t == "request <uuid> failed"


def test_error_groups_empty_returns_empty_frame(monkeypatch):
    empty = pd.DataFrame(columns=["ts", "service", "level", "error_type", "message"])
    monkeypatch.setattr(correlate, "query_df", fake_query(empty))
    assert correlate.error_groups("2026-10-01", "2026-10-02").empty


def test_error_groups_groups_similar_messages(monkeypatch, ts):
    rows = [
        (ts("14:05:01"), "db-service", "ERROR", "DB_CONNECTION_FAILED", "refused after 3 retries"),
        (ts("14:05:09"), "db-service", "ERROR", "DB_CONNECTION_FAILED", "refused after 5 retries"),
        (ts("14:06:00"), "db-service", "ERROR", "DB_CONNECTION_FAILED", "refused after 4 retries"),
        (ts("14:05:30"), "auth-service", "WARN", "BAD_PASSWORD", "Invalid password attempt for user bob"),
        (ts("14:07:30"), "auth-service", "WARN", "BAD_PASSWORD", "Invalid password attempt for user amy"),
    ]
    df = pd.DataFrame(rows, columns=["ts", "service", "level", "error_type", "message"])
    monkeypatch.setattr(correlate, "query_df", fake_query(df))

    g = correlate.error_groups("2026-10-01", "2026-10-02")

    assert len(g) == 2
    top = g.iloc[0]  # sorted by count descending
    assert top["service"] == "db-service"
    assert top["count"] == 3
    assert top["pattern"] == "refused after <n> retries"
    assert top["first_seen"] == ts("14:05:01")
    assert top["last_seen"] == ts("14:06:00")
    assert g.iloc[1]["count"] == 2


def test_error_groups_respects_top(monkeypatch, ts):
    rows = [(ts("14:05:00"), f"svc-{i}", "ERROR", f"E{i}", f"message {i}x") for i in range(5)]
    df = pd.DataFrame(rows, columns=["ts", "service", "level", "error_type", "message"])
    monkeypatch.setattr(correlate, "query_df", fake_query(df))
    assert len(correlate.error_groups("2026-10-01", "2026-10-02", top=3)) == 3


def test_service_summary_orders_by_first_error_and_puts_clean_services_last(monkeypatch, ts):
    df = pd.DataFrame({
        "service": ["auth-service", "api-gateway", "db-service"],
        "errors": [0, 100, 100],
        "warns": [0, 0, 0],
        "total_lines": [160, 260, 160],
        "first_error": [pd.NaT, ts("14:05:03"), ts("14:05:00")],
        "avg_latency_ms": [27.0, 1200.0, 1800.0],
    })
    monkeypatch.setattr(correlate, "query_df", fake_query(df))

    out = correlate.service_summary(ts("14:05:00"), ts("14:17:00"))

    assert list(out["service"]) == ["db-service", "api-gateway", "auth-service"]
    assert list(out.index) == [0, 1, 2]


def test_service_summary_passes_python_datetimes(monkeypatch, ts):
    seen = {}

    def spy(sql, **params):
        seen.update(params)
        return pd.DataFrame({"service": [], "first_error": pd.Series([], dtype="datetime64[ns]")})

    monkeypatch.setattr(correlate, "query_df", spy)
    correlate.service_summary(ts("14:05:00"), ts("14:17:00"))
    assert type(seen["s"]).__name__ == "datetime"
    assert type(seen["e"]).__name__ == "datetime"
