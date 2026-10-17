from datetime import datetime

from .evidence import collect_evidence
from .verify import verify

ev = collect_evidence(datetime(2026, 10, 1), datetime(2026, 10, 1, 23, 59, 59))
s, e = ev["period"]["start"], ev["period"]["end"]
wrong = {"root_cause_service": "api-gateway", "root_cause_error_type": "TIMEOUT"}
print(verify(wrong, s, e))
