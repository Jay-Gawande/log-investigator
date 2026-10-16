import pandas as pd

from .evidence import collect_evidence
from .reasoning import find_root_cause


def to_jsonable(o):
    """Make any result JSON-safe: NaN/NaT -> None, numpy -> python, timestamps -> str."""
    if isinstance(o, dict):
        return {str(k): to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_jsonable(v) for v in o]
    if o is None or isinstance(o, (str, bool)):
        return o
    try:
        if pd.isna(o):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(o, "item") and not isinstance(o, pd.Timestamp):
        return o.item()
    if isinstance(o, (int, float)):
        return o
    return str(o)


def investigate(description, start, end):
    """Run the full investigation: incident -> report data."""
    evidence = collect_evidence(start, end)
    if evidence is None:
        return {
            "status": "no_anomaly_found",
            "incident": description,
            "requested_range": {"start": str(start), "end": str(end)},
        }

    hypothesis, verification, attempts = find_root_cause(description, evidence)

    result = {
        "status": "ok",
        "incident": description,
        "requested_range": {"start": str(start), "end": str(end)},
        **evidence,  # period, services, error_groups, traces, timeline
        "hypothesis": hypothesis,
        "verification": verification,
        "attempts": attempts,
    }
    return to_jsonable(result)
