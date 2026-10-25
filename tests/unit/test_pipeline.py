import json
from datetime import datetime

import numpy as np
import pandas as pd

from app.investigator import pipeline


# ---- to_jsonable ---------------------------------------------------------

def test_to_jsonable_converts_nan_nat_numpy_and_timestamps():
    raw = {
        "nan": float("nan"),
        "nat": pd.NaT,
        "np_int": np.int64(5),
        "np_float": np.float64(1.5),
        "ts": pd.Timestamp("2026-10-01 14:05:00"),
        "nested": [{"x": np.int32(2)}, (1, 2)],
        1: "int key",
    }
    out = pipeline.to_jsonable(raw)

    assert out["nan"] is None
    assert out["nat"] is None
    assert out["np_int"] == 5 and type(out["np_int"]) is int
    assert out["np_float"] == 1.5 and type(out["np_float"]) is float
    assert out["ts"] == "2026-10-01 14:05:00"
    assert out["nested"] == [{"x": 2}, [1, 2]]
    assert out["1"] == "int key"
    json.dumps(out)  # must be serialisable


def test_to_jsonable_keeps_plain_values():
    assert pipeline.to_jsonable({"a": "s", "b": True, "c": None, "d": 3, "e": 2.5}) == {
        "a": "s", "b": True, "c": None, "d": 3, "e": 2.5,
    }


# ---- investigate ---------------------------------------------------------

START, END = datetime(2026, 10, 1), datetime(2026, 10, 1, 23, 59, 59)


def test_investigate_reports_no_anomaly(monkeypatch):
    monkeypatch.setattr(pipeline, "collect_evidence", lambda s, e: None)

    def boom(*a, **k):
        raise AssertionError("reasoning must not run without evidence")

    monkeypatch.setattr(pipeline, "find_root_cause", boom)

    out = pipeline.investigate("slow checkout", START, END)

    assert out["status"] == "no_anomaly_found"
    assert out["incident"] == "slow checkout"
    assert out["requested_range"] == {"start": str(START), "end": str(END)}


def test_investigate_returns_full_json_safe_result(monkeypatch, evidence):
    hyp = {"root_cause_service": "db-service", "root_cause_error_type": "DB_CONNECTION_FAILED",
           "confidence": 0.9, "source": "llm"}
    ver = {"verified": True}
    attempts = [{"attempt": 1, "hypothesis": hyp, "verification": ver}]
    monkeypatch.setattr(pipeline, "collect_evidence", lambda s, e: evidence)
    monkeypatch.setattr(pipeline, "find_root_cause", lambda d, ev: (hyp, ver, attempts))

    out = pipeline.investigate("slow checkout", START, END)

    assert out["status"] == "ok"
    assert out["hypothesis"] == hyp
    assert out["verification"] == ver
    assert out["attempts"] == attempts
    for key in ("period", "services", "error_groups", "traces", "timeline"):
        assert key in out
    assert out["services"][1]["first_error"] is None  # NaT became null
    json.dumps(out)
