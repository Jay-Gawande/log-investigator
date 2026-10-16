import pandas as pd

from ..db import query_df
from .timeline import build_timeline


def verify(hypothesis, start, end):
    """Check the claim against the logs themselves."""
    svc = hypothesis.get("root_cause_service")
    et = hypothesis.get("root_cause_error_type")
    s = pd.Timestamp(start).to_pydatetime()
    e = pd.Timestamp(end).to_pydatetime()

    tl = build_timeline(s, e)
    if tl.empty:
        return {"verified": False, "reason": "no errors in window"}
    # ignore low-volume background noise
    tl = tl[tl["occurrences"] >= 0.1 * tl["occurrences"].max()]

    claimed = tl[(tl["service"] == svc) & (tl["error_type"] == et)]

    # Check 1: the claimed error really occurs in the window
    check_exists = not claimed.empty

    # Check 2: it appeared first (within 1 second) among significant groups
    check_first = bool(
        check_exists
        and claimed["first_seen"].min() <= tl["first_seen"].min() + pd.Timedelta(seconds=1)
    )

    # Check 3: it is present in most failing requests
    lines = query_df("""
        SELECT request_id, service, error_type
        FROM logs
        WHERE level IN ('ERROR', 'WARN') AND ts >= :s AND ts < :e
    """, s=s, e=e)
    sig = tl[["service", "error_type"]].drop_duplicates()
    lines = lines.merge(sig, on=["service", "error_type"])
    total = lines["request_id"].nunique()
    hit = lines[(lines["service"] == svc) & (lines["error_type"] == et)]["request_id"].nunique()
    coverage = hit / total if total else 0.0
    check_coverage = coverage >= 0.5

    return {
        "error_exists_in_window": bool(check_exists),
        "appeared_first": check_first,
        "coverage_of_failing_requests": round(float(coverage), 3),
        "coverage_ok": bool(check_coverage),
        "verified": bool(check_exists and check_first and check_coverage),
    }
