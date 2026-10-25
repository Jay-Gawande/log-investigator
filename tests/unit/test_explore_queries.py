from datetime import datetime
from decimal import Decimal

import pandas as pd
import pytest

from app.explore import queries


@pytest.fixture(autouse=True)
def fresh_cache():
    queries.clear_meta_cache()
    yield
    queries.clear_meta_cache()


class Spy:
    """Callable stand-in for query_df that records the SQL and parameters."""

    def __init__(self, df):
        self.df = df
        self.calls = []

    def __call__(self, sql, **params):
        self.calls.append((sql, params))
        return self.df.copy()

    @property
    def sql(self):
        return self.calls[-1][0]

    @property
    def params(self):
        return self.calls[-1][1]


# ---------------------------------------------------------------- helpers

def test_escape_like_escapes_wildcards_and_backslashes():
    assert queries.escape_like("50%_x") == "50\\%\\_x"
    assert queries.escape_like("a\\b") == "a\\\\b"
    assert queries.escape_like("plain") == "plain"


def test_choose_bucket_scales_with_range():
    d = datetime(2026, 10, 1)
    assert queries.choose_bucket(d, datetime(2026, 10, 1, 1)) == 1        # 1 hour -> 60 points
    assert queries.choose_bucket(d, datetime(2026, 10, 2)) == 5           # 1 day -> 288 points
    assert queries.choose_bucket(d, datetime(2026, 10, 15)) == 60         # 14 days -> largest bucket


# ---------------------------------------------------------------- meta

def _meta_fake(calls):
    def fake(sql, **params):
        calls.append(sql)
        if "MIN(ts)" in sql:
            return pd.DataFrame({
                "min_ts": [pd.Timestamp("2026-10-01 00:00:01.120")],
                "max_ts": [pd.Timestamp("2026-10-01 23:59:58.410")],
                "total_rows": [80412],
            })
        for column, values in {
            "service": ["api-gateway", "db-service"],
            "level": ["ERROR", "INFO"],
            "error_type": ["TIMEOUT"],
        }.items():
            if f"DISTINCT {column} " in sql:
                return pd.DataFrame({"v": values})
        raise AssertionError(sql)
    return fake


def test_get_meta_shape(monkeypatch):
    monkeypatch.setattr(queries, "query_df", _meta_fake([]))
    meta = queries.get_meta()
    assert meta == {
        "min_ts": "2026-10-01T00:00:01.120",
        "max_ts": "2026-10-01T23:59:58.410",
        "total_rows": 80412,
        "services": ["api-gateway", "db-service"],
        "levels": ["ERROR", "INFO"],
        "error_types": ["TIMEOUT"],
    }


def test_get_meta_is_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(queries, "query_df", _meta_fake(calls))
    queries.get_meta()
    first = len(calls)
    queries.get_meta()
    assert len(calls) == first          # second call served from the cache


def test_get_meta_empty_table(monkeypatch):
    def fake(sql, **params):
        if "MIN(ts)" in sql:
            return pd.DataFrame({"min_ts": [pd.NaT], "max_ts": [pd.NaT], "total_rows": [0]})
        return pd.DataFrame({"v": []})

    monkeypatch.setattr(queries, "query_df", fake)
    meta = queries.get_meta()
    assert meta["min_ts"] is None and meta["max_ts"] is None
    assert meta["total_rows"] == 0
    assert meta["services"] == []


def test_distinct_rejects_unknown_column():
    with pytest.raises(ValueError):
        queries._distinct("message; DROP TABLE logs")


# ---------------------------------------------------------------- overview

def test_overview_fills_empty_buckets_with_zeros(monkeypatch):
    df = pd.DataFrame({
        "bucket": [pd.Timestamp("2026-10-01 14:05:00"), pd.Timestamp("2026-10-01 14:07:00")],
        "errors": [Decimal(31), Decimal(4)],     # SUM() returns Decimal in MariaDB
        "warns": [Decimal(0), Decimal(2)],
        "total": [52, 20],
    })
    spy = Spy(df)
    monkeypatch.setattr(queries, "query_df", spy)

    out = queries.get_overview(datetime(2026, 10, 1, 14, 4, 30), datetime(2026, 10, 1, 14, 8, 10), 1)

    assert out["bucket_minutes"] == 1
    assert [p["ts"] for p in out["points"]] == [
        "2026-10-01T14:04:00.000", "2026-10-01T14:05:00.000", "2026-10-01T14:06:00.000",
        "2026-10-01T14:07:00.000", "2026-10-01T14:08:00.000",
    ]
    assert [p["errors"] for p in out["points"]] == [0, 31, 0, 4, 0]
    assert [p["warns"] for p in out["points"]] == [0, 0, 0, 2, 0]
    assert all(isinstance(p["errors"], int) for p in out["points"])
    assert spy.params["sec"] == 60


def test_overview_with_no_rows_returns_zero_points(monkeypatch):
    empty = pd.DataFrame({"bucket": [], "errors": [], "warns": [], "total": []})
    monkeypatch.setattr(queries, "query_df", Spy(empty))
    out = queries.get_overview(datetime(2026, 10, 1, 14, 0), datetime(2026, 10, 1, 14, 2), 1)
    assert [p["total"] for p in out["points"]] == [0, 0, 0]


def test_overview_service_filter_is_a_bound_parameter(monkeypatch):
    spy = Spy(pd.DataFrame({"bucket": [], "errors": [], "warns": [], "total": []}))
    monkeypatch.setattr(queries, "query_df", spy)
    queries.get_overview(datetime(2026, 10, 1), datetime(2026, 10, 1, 1), 5, "db-service")
    assert "service = :service" in spy.sql
    assert spy.params["service"] == "db-service"
    assert "db-service" not in spy.sql
    assert spy.params["sec"] == 300


def test_overview_without_service_has_no_service_clause(monkeypatch):
    spy = Spy(pd.DataFrame({"bucket": [], "errors": [], "warns": [], "total": []}))
    monkeypatch.setattr(queries, "query_df", spy)
    queries.get_overview(datetime(2026, 10, 1), datetime(2026, 10, 1, 1))
    assert "service = :service" not in spy.sql
    assert "service" not in spy.params


def test_overview_auto_bucket_is_used_when_not_given(monkeypatch):
    spy = Spy(pd.DataFrame({"bucket": [], "errors": [], "warns": [], "total": []}))
    monkeypatch.setattr(queries, "query_df", spy)
    out = queries.get_overview(datetime(2026, 10, 1), datetime(2026, 10, 2))
    assert out["bucket_minutes"] == 5


def test_overview_rejects_unsupported_bucket():
    with pytest.raises(ValueError, match="bucket_minutes"):
        queries.get_overview(datetime(2026, 10, 1), datetime(2026, 10, 2), 7)


def test_overview_rejects_too_many_buckets():
    with pytest.raises(ValueError, match="too many buckets"):
        queries.get_overview(datetime(2026, 10, 1), datetime(2026, 10, 31), 1)


# ---------------------------------------------------------------- log search

def _log_frame(n, with_nulls=False):
    rows = []
    for i in range(n):
        rows.append({
            "id": i + 1,
            "ts": pd.Timestamp("2026-10-01 14:05:00") + pd.Timedelta(seconds=i),
            "service": "db-service",
            "level": "ERROR",
            "request_id": f"123e4567-e89b-12d3-a456-42661417400{i % 10}",
            "message": f"boom {i}",
            "error_type": None if with_nulls else "DB_CONNECTION_FAILED",
            "latency_ms": float("nan") if with_nulls else 1800,
        })
    return pd.DataFrame(rows)


START, END = datetime(2026, 10, 1), datetime(2026, 10, 2)


def test_search_logs_has_more_and_trims_extra_row(monkeypatch):
    spy = Spy(_log_frame(4))                   # limit 3 -> the 4th row only signals "more"
    monkeypatch.setattr(queries, "query_df", spy)
    out = queries.search_logs(START, END, limit=3, offset=6)
    assert out["has_more"] is True
    assert len(out["items"]) == 3
    assert out["limit"] == 3 and out["offset"] == 6
    assert spy.params["lim"] == 4 and spy.params["off"] == 6


def test_search_logs_last_page(monkeypatch):
    monkeypatch.setattr(queries, "query_df", Spy(_log_frame(3)))
    out = queries.search_logs(START, END, limit=3)
    assert out["has_more"] is False
    assert len(out["items"]) == 3


def test_search_logs_item_shape_and_null_handling(monkeypatch):
    monkeypatch.setattr(queries, "query_df", Spy(_log_frame(1, with_nulls=True)))
    item = queries.search_logs(START, END)["items"][0]
    assert item["error_type"] is None
    assert item["latency_ms"] is None
    assert item["ts"] == "2026-10-01T14:05:00.000"
    assert isinstance(item["id"], int)


def test_search_logs_filters_become_bound_parameters(monkeypatch):
    spy = Spy(_log_frame(0))
    monkeypatch.setattr(queries, "query_df", spy)
    queries.search_logs(
        START, END, service="db-service", level="ERROR", error_type="TIMEOUT",
        request_id="123e4567-e89b-12d3-a456-426614174000", q="50%_x",
    )
    for fragment in ("service = :service", "level = :level", "error_type = :error_type",
                     "request_id = :request_id", "message LIKE :q"):
        assert fragment in spy.sql
    assert spy.params["q"] == "%50\\%\\_x%"
    assert spy.params["service"] == "db-service"
    assert "db-service" not in spy.sql and "TIMEOUT" not in spy.sql


def test_search_logs_without_filters_only_filters_by_time(monkeypatch):
    spy = Spy(_log_frame(0))
    monkeypatch.setattr(queries, "query_df", spy)
    queries.search_logs(START, END)
    assert "ts BETWEEN :s AND :e" in spy.sql
    for fragment in (":service", ":level", ":error_type", ":request_id", ":q"):
        assert fragment not in spy.sql


@pytest.mark.parametrize("order,expected", [("asc", "ORDER BY ts ASC, id ASC"),
                                            ("desc", "ORDER BY ts DESC, id DESC")])
def test_search_logs_order(monkeypatch, order, expected):
    spy = Spy(_log_frame(0))
    monkeypatch.setattr(queries, "query_df", spy)
    queries.search_logs(START, END, order=order)
    assert expected in spy.sql


def test_search_logs_rejects_unknown_order():
    with pytest.raises(ValueError):
        queries.search_logs(START, END, order="sideways; DROP TABLE logs")


# ---------------------------------------------------------------- request trace

def test_request_trace_unknown_id_returns_none(monkeypatch):
    empty = pd.DataFrame(columns=["id", "ts", "service", "level", "message", "error_type", "latency_ms"])
    monkeypatch.setattr(queries, "query_df", Spy(empty))
    assert queries.request_trace("123e4567-e89b-12d3-a456-426614174000") is None


def test_request_trace_offsets_services_and_errors(monkeypatch):
    t0 = pd.Timestamp("2026-10-01 14:05:00")
    df = pd.DataFrame({
        "id": [1, 2, 3, 4],
        "ts": [t0, t0 + pd.Timedelta(milliseconds=20), t0 + pd.Timedelta(milliseconds=3100),
               t0 + pd.Timedelta(milliseconds=3150)],
        "service": ["api-gateway", "db-service", "order-service", "api-gateway"],
        "level": ["INFO", "ERROR", "ERROR", "ERROR"],
        "message": ["start", "refused", "dependency", "timeout"],
        "error_type": [None, "DB_CONNECTION_FAILED", "DEPENDENCY_FAILURE", "TIMEOUT"],
        "latency_ms": [20, 1800, float("nan"), 3000],
    })
    spy = Spy(df)
    monkeypatch.setattr(queries, "query_df", spy)

    out = queries.request_trace("123e4567-e89b-12d3-a456-426614174000")

    assert spy.params == {"rid": "123e4567-e89b-12d3-a456-426614174000"}
    assert out["duration_ms"] == 3150
    assert out["services"] == ["api-gateway", "db-service", "order-service"]   # first-seen order
    assert out["has_errors"] is True
    assert out["start"] == "2026-10-01T14:05:00.000"
    assert out["end"] == "2026-10-01T14:05:03.150"
    assert [e["offset_ms"] for e in out["events"]] == [0, 20, 3100, 3150]
    assert out["events"][0]["error_type"] is None
    assert out["events"][2]["latency_ms"] is None
    assert out["events"][1]["latency_ms"] == 1800


def test_request_trace_healthy_request_has_no_errors(monkeypatch):
    t0 = pd.Timestamp("2026-10-01 14:05:00")
    df = pd.DataFrame({
        "id": [1], "ts": [t0], "service": ["api-gateway"], "level": ["INFO"],
        "message": ["ok"], "error_type": [None], "latency_ms": [10],
    })
    monkeypatch.setattr(queries, "query_df", Spy(df))
    out = queries.request_trace("123e4567-e89b-12d3-a456-426614174000")
    assert out["has_errors"] is False
    assert out["duration_ms"] == 0
