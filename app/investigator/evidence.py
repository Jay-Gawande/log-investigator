from .anomaly import find_anomalous_period
from .correlate import error_groups, service_summary
from .timeline import build_timeline
from .trace import trace_summary


def collect_evidence(start, end):
    period = find_anomalous_period(start, end)
    if period is None:
        return None
    s, e = period["start"], period["end"]
    return {
        "period": period,
        "services": service_summary(s, e).to_dict("records"),
        "error_groups": error_groups(s, e).to_dict("records"),
        "traces": trace_summary(s, e),
        "timeline": build_timeline(s, e).to_dict("records"),
    }
