import random
from datetime import datetime, timedelta

import pandas as pd
import pytest

from app import generator

T0 = datetime(2026, 10, 1, 14, 5, 0)
COLS = generator.COLUMNS


def as_frame(rows):
    return pd.DataFrame(rows, columns=COLS)


@pytest.fixture(autouse=True)
def seeded():
    random.seed(1234)


def test_normal_request_walks_the_whole_service_chain():
    rows = generator.normal_request(T0)
    base = [r for r in rows if r[2] == "INFO"]
    assert [r[1] for r in base] == generator.CHAIN
    assert len({r[3] for r in rows}) == 1             # one request id
    assert all(len(r) == len(COLS) for r in rows)
    assert all(r[5] is None for r in base)             # healthy lines carry no error type
    assert [r[0] for r in base] == sorted(r[0] for r in base)


def test_normal_requests_have_unique_request_ids():
    ids = {generator.normal_request(T0)[0][3] for _ in range(200)}
    assert len(ids) == 200


def test_normal_requests_only_ever_add_background_warnings():
    extra = [r for _ in range(3000) for r in generator.normal_request(T0) if r[2] != "INFO"]
    assert extra, "expected at least a few background warnings in 3000 requests"
    assert {(r[1], r[2], r[5]) for r in extra} == {("auth-service", "WARN", "BAD_PASSWORD")}


def test_db_failure_request_shape():
    rows = generator.incident_request(T0, "db_failure")
    df = as_frame(rows)
    assert len(df) == 6
    assert df["request_id"].nunique() == 1
    errors = df[df["level"] == "ERROR"]
    assert list(errors["error_type"]) == ["DB_CONNECTION_FAILED", "DEPENDENCY_FAILURE", "TIMEOUT"]
    assert list(errors["service"]) == ["db-service", "order-service", "api-gateway"]
    assert df["ts"].is_monotonic_increasing


def test_auth_failure_request_shape():
    df = as_frame(generator.incident_request(T0, "auth_failure"))
    assert len(df) == 3
    assert set(df["error_type"].dropna()) == {"AUTH_FAILED"}
    assert df.loc[df["service"] == "auth-service", "level"].iloc[0] == "ERROR"


def test_high_latency_request_shape():
    df = as_frame(generator.incident_request(T0, "high_latency"))
    assert list(df["service"]) == generator.CHAIN
    slow = df[df["service"] == "db-service"].iloc[0]
    assert slow["level"] == "WARN"
    assert slow["error_type"] == "SLOW_QUERY"
    assert 2000 <= slow["latency_ms"] <= 5000
    assert (df[df["service"] != "db-service"]["latency_ms"] <= 80).all()


def test_unknown_incident_kind_raises():
    with pytest.raises(ValueError, match="unknown incident kind"):
        generator.incident_request(T0, "meteor_strike")


def test_flush_with_no_rows_is_a_noop(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not write")
    monkeypatch.setattr(pd.DataFrame, "to_sql", boom)
    generator.flush([])


def test_flush_writes_to_logs_table(monkeypatch):
    captured = {}

    def fake_to_sql(self, name, con, **kwargs):
        captured["name"], captured["df"], captured["kwargs"] = name, self.copy(), kwargs

    monkeypatch.setattr(pd.DataFrame, "to_sql", fake_to_sql)
    rows = generator.normal_request(T0)
    generator.flush(rows)

    assert captured["name"] == "logs"
    assert list(captured["df"].columns) == COLS
    assert len(captured["df"]) == len(rows)
    assert captured["kwargs"]["if_exists"] == "append"


@pytest.fixture
def captured_rows(monkeypatch):
    sink = []
    monkeypatch.setattr(generator, "flush", lambda rows: sink.extend(rows))
    return sink


def test_generate_confines_incident_to_its_window(captured_rows):
    day = datetime(2026, 10, 1)
    inc_start = day + timedelta(minutes=14 * 60 + 5)
    inc_end = inc_start + timedelta(minutes=120)

    generator.generate(3000, day, "db_failure", inc_start_min=14 * 60 + 5, inc_len_min=120)

    df = as_frame(captured_rows)
    errors = df[df["level"] == "ERROR"]
    assert len(errors) > 0
    # an incident request that starts just before the end can spill a few seconds over
    assert errors["ts"].min() >= inc_start
    assert errors["ts"].max() <= inc_end + timedelta(seconds=5)
    # outside the window the only non-INFO lines are background warnings
    outside = df[(df["ts"] < inc_start) | (df["ts"] >= inc_end + timedelta(seconds=5))]
    assert set(outside[outside["level"] != "INFO"]["error_type"]) <= {"BAD_PASSWORD"}


def test_generate_produces_complete_requests(captured_rows):
    generator.generate(500, datetime(2026, 10, 1), "auth_failure", 14 * 60 + 5, 30)
    df = as_frame(captured_rows)
    assert df["request_id"].nunique() == 500
    assert set(df["service"]) <= set(generator.CHAIN)


def test_generate_is_reproducible_with_a_seed(monkeypatch):
    def run():
        random.seed(99)
        sink = []
        monkeypatch.setattr(generator, "flush", lambda rows: sink.extend(rows))
        generator.generate(50, datetime(2026, 10, 1), "high_latency", 14 * 60, 60)
        # request ids and usernames come from uuid4 / faker; compare the stable columns
        return [(r[0], r[1], r[2], r[5], r[6]) for r in sink]

    assert run() == run()
