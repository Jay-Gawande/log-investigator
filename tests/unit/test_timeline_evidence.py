import pandas as pd

from app.investigator import evidence as evidence_mod
from app.investigator import timeline


def test_build_timeline_returns_query_result_and_uses_datetimes(monkeypatch, ts):
    expected = pd.DataFrame({"service": ["db-service"], "occurrences": [3]})
    seen = {}

    def fake(sql, **params):
        seen.update(params)
        return expected

    monkeypatch.setattr(timeline, "query_df", fake)
    out = timeline.build_timeline(ts("14:05:00"), ts("14:17:00"))

    assert out is expected
    assert type(seen["s"]).__name__ == "datetime"
    assert type(seen["e"]).__name__ == "datetime"


def test_collect_evidence_returns_none_without_anomaly(monkeypatch):
    monkeypatch.setattr(evidence_mod, "find_anomalous_period", lambda s, e: None)
    assert evidence_mod.collect_evidence("a", "b") is None


def test_collect_evidence_assembles_all_sections(monkeypatch, ts):
    period = {"start": ts("14:05:00"), "end": ts("14:17:00")}
    calls = {}

    def record(name, df):
        def _f(s, e, *a, **k):
            calls[name] = (s, e)
            return df
        return _f

    monkeypatch.setattr(evidence_mod, "find_anomalous_period", lambda s, e: period)
    monkeypatch.setattr(evidence_mod, "service_summary", record("services", pd.DataFrame({"service": ["x"]})))
    monkeypatch.setattr(evidence_mod, "error_groups", record("groups", pd.DataFrame({"count": [1]})))
    monkeypatch.setattr(evidence_mod, "build_timeline", record("timeline", pd.DataFrame({"occurrences": [2]})))
    monkeypatch.setattr(evidence_mod, "trace_summary", lambda s, e: {"requests_sampled": 7})

    out = evidence_mod.collect_evidence("a", "b")

    assert set(out) == {"period", "services", "error_groups", "traces", "timeline"}
    assert out["services"] == [{"service": "x"}]
    assert out["error_groups"] == [{"count": 1}]
    assert out["timeline"] == [{"occurrences": 2}]
    assert out["traces"] == {"requests_sampled": 7}
    # every stage is queried over the detected period, not the requested range
    for start_end in calls.values():
        assert start_end == (period["start"], period["end"])
