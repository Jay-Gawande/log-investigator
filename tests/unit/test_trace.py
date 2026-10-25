import pandas as pd

from app.investigator import trace


def request_logs(spec, ts):
    """spec: {request_id: [(service, level), ...]} -> frame like fetch_request_logs returns."""
    rows = []
    for rid, steps in spec.items():
        for i, (svc, level) in enumerate(steps):
            rows.append({
                "request_id": rid, "ts": ts("14:05:00") + pd.Timedelta(milliseconds=20 * i),
                "service": svc, "level": level,
                "error_type": "E" if level == "ERROR" else None,
                "message": f"{svc} {level}",
            })
    return pd.DataFrame(rows)


DB_PATH = [("api-gateway", "INFO"), ("db-service", "ERROR"), ("api-gateway", "ERROR")]
AUTH_PATH = [("api-gateway", "INFO"), ("auth-service", "ERROR")]


def test_fetch_request_logs_with_no_ids_skips_the_database():
    out = trace.fetch_request_logs([])
    assert out.empty


def test_trace_summary_with_no_failing_requests(monkeypatch):
    monkeypatch.setattr(trace, "sample_error_request_ids", lambda s, e, n: [])
    monkeypatch.setattr(trace, "fetch_request_logs", lambda ids: pd.DataFrame())
    assert trace.trace_summary("a", "b") == {
        "requests_sampled": 0, "common_paths": [], "sample_traces": [],
    }


def test_trace_summary_counts_common_paths(monkeypatch, ts):
    spec = {"r1": DB_PATH, "r2": DB_PATH, "r3": AUTH_PATH}
    monkeypatch.setattr(trace, "sample_error_request_ids", lambda s, e, n: list(spec))
    monkeypatch.setattr(trace, "fetch_request_logs", lambda ids: request_logs(spec, ts))

    out = trace.trace_summary("a", "b")

    assert out["requests_sampled"] == 3
    assert out["common_paths"][0] == {
        "path": "api-gateway:INFO > db-service:ERROR > api-gateway:ERROR", "count": 2,
    }
    assert out["common_paths"][1] == {
        "path": "api-gateway:INFO > auth-service:ERROR", "count": 1,
    }


def test_trace_summary_limits_sample_traces(monkeypatch, ts):
    spec = {f"r{i}": DB_PATH for i in range(6)}
    monkeypatch.setattr(trace, "sample_error_request_ids", lambda s, e, n: list(spec))
    monkeypatch.setattr(trace, "fetch_request_logs", lambda ids: request_logs(spec, ts))

    out = trace.trace_summary("a", "b", show=2)

    assert [t["request_id"] for t in out["sample_traces"]] == ["r0", "r1"]
    first_event = out["sample_traces"][0]["events"][0]
    assert set(first_event) == {"ts", "service", "level", "error_type", "message"}
    assert isinstance(first_event["ts"], str)


def test_trace_summary_passes_sample_size(monkeypatch):
    seen = {}

    def spy(s, e, n):
        seen["n"] = n
        return []

    monkeypatch.setattr(trace, "sample_error_request_ids", spy)
    monkeypatch.setattr(trace, "fetch_request_logs", lambda ids: pd.DataFrame())
    trace.trace_summary("a", "b", sample_size=42)
    assert seen["n"] == 42
