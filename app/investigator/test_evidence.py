import json
from datetime import datetime

from .evidence import collect_evidence

start = datetime(2026, 10, 1, 0, 0, 0)
end = datetime(2026, 10, 1, 23, 59, 59)

ev = collect_evidence(start, end)
if ev is None:
    raise SystemExit("No anomaly found. Rerun the generator.")

print("=== PERIOD ===")
print(ev["period"])

print("\n=== SERVICES (ordered by first error) ===")
for r in ev["services"]:
    print(r)

print("\n=== ERROR GROUPS ===")
for r in ev["error_groups"]:
    print(r)

print("\n=== COMMON REQUEST PATHS ===")
print("requests sampled:", ev["traces"]["requests_sampled"])
for r in ev["traces"]["common_paths"]:
    print(r)

print("\n=== ONE SAMPLE TRACE ===")
for r in ev["traces"]["sample_traces"][0]["events"]:
    print(r)

print("\n=== TIMELINE ===")
for r in ev["timeline"]:
    print(r)

text = json.dumps(ev, default=str)
print(f"\nEvidence JSON size: {len(text)} characters")
