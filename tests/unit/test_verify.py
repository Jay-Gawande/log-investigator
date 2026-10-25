import pandas as pd
import pytest

from app.investigator import verify as verify_mod


@pytest.fixture
def patch_db(monkeypatch):
    """Replace the timeline and the per-line query used by verify()."""
    def _patch(timeline_rows, lines):
        tl = pd.DataFrame(timeline_rows)
        monkeypatch.setattr(verify_mod, "build_timeline", lambda s, e: tl)
        monkeypatch.setattr(
            verify_mod, "query_df",
            lambda sql, **p: pd.DataFrame(lines, columns=["request_id", "service", "error_type"]),
        )
    return _patch


def outage_lines(n=100):
    """Every failing request carries all three outage errors."""
    lines = []
    for i in range(n):
        rid = f"r{i}"
        lines += [
            (rid, "db-service", "DB_CONNECTION_FAILED"),
            (rid, "order-service", "DEPENDENCY_FAILURE"),
            (rid, "api-gateway", "TIMEOUT"),
        ]
    return lines


def hyp(service, error_type):
    return {"root_cause_service": service, "root_cause_error_type": error_type}


def test_correct_root_cause_is_verified(patch_db, timeline_rows, ts):
    patch_db(timeline_rows, outage_lines())
    v = verify_mod.verify(hyp("db-service", "DB_CONNECTION_FAILED"), ts("14:05:00"), ts("14:17:00"))
    assert v["verified"] is True
    assert v["error_exists_in_window"] is True
    assert v["appeared_first"] is True
    assert v["coverage_ok"] is True
    assert v["coverage_of_failing_requests"] == 1.0


def test_downstream_symptom_is_rejected_because_it_did_not_appear_first(patch_db, timeline_rows, ts):
    patch_db(timeline_rows, outage_lines())
    v = verify_mod.verify(hyp("order-service", "DEPENDENCY_FAILURE"), ts("14:05:00"), ts("14:17:00"))
    assert v["error_exists_in_window"] is True
    assert v["appeared_first"] is False
    assert v["verified"] is False


def test_invented_error_is_rejected(patch_db, timeline_rows, ts):
    patch_db(timeline_rows, outage_lines())
    v = verify_mod.verify(hyp("cache-service", "CACHE_MISS"), ts("14:05:00"), ts("14:17:00"))
    assert v["error_exists_in_window"] is False
    assert v["appeared_first"] is False
    assert v["coverage_of_failing_requests"] == 0.0
    assert v["verified"] is False


def test_low_coverage_is_rejected_even_if_it_appeared_first(patch_db, timeline_rows, ts):
    # db-service errors appear in only 30 of 100 failing requests
    lines = []
    for i in range(100):
        rid = f"r{i}"
        lines.append((rid, "api-gateway", "TIMEOUT"))
        if i < 30:
            lines.append((rid, "db-service", "DB_CONNECTION_FAILED"))
    patch_db(timeline_rows, lines)
    v = verify_mod.verify(hyp("db-service", "DB_CONNECTION_FAILED"), ts("14:05:00"), ts("14:17:00"))
    assert v["appeared_first"] is True
    assert v["coverage_of_failing_requests"] == 0.3
    assert v["coverage_ok"] is False
    assert v["verified"] is False


def test_background_noise_does_not_hide_the_real_root_cause(patch_db, timeline_rows, ts):
    # auth-service BAD_PASSWORD (2 lines) has the earliest timestamp in the fixture,
    # but is under 10% of the biggest group, so it is ignored
    patch_db(timeline_rows, outage_lines())
    v = verify_mod.verify(hyp("db-service", "DB_CONNECTION_FAILED"), ts("14:05:00"), ts("14:17:00"))
    assert v["verified"] is True


def test_noise_cannot_be_verified_as_root_cause(patch_db, timeline_rows, ts):
    patch_db(timeline_rows, outage_lines())
    v = verify_mod.verify(hyp("auth-service", "BAD_PASSWORD"), ts("14:05:00"), ts("14:17:00"))
    assert v["error_exists_in_window"] is False
    assert v["verified"] is False


def test_empty_window_is_not_verified(patch_db, ts):
    patch_db(
        [], [],
    )
    # build_timeline returns an empty frame with no columns
    v = verify_mod.verify(hyp("db-service", "X"), ts("14:05:00"), ts("14:17:00"))
    assert v == {"verified": False, "reason": "no errors in window"}


def test_missing_keys_in_hypothesis_do_not_crash(patch_db, timeline_rows, ts):
    patch_db(timeline_rows, outage_lines())
    v = verify_mod.verify({}, ts("14:05:00"), ts("14:17:00"))
    assert v["verified"] is False
