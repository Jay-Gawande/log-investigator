import json
from datetime import datetime

from app.investigator.evidence import collect_evidence
from app.investigator.reasoning import find_root_cause

DESCRIPTION = "Users reported checkout failures and slow responses around 2 PM."

ev = collect_evidence(datetime(2026, 10, 1), datetime(2026, 10, 1, 23, 59, 59))
if ev is None:
    raise SystemExit("No anomaly found. Rerun the generator.")

hyp, ver, log = find_root_cause(DESCRIPTION, ev)

print("=== ATTEMPTS ===")
for a in log:
    print(a["attempt"], "->",
          a.get("error") or ("verified=" + str(a["verification"]["verified"])))

print("\n=== FINAL HYPOTHESIS ===")
print(json.dumps(hyp, indent=2, default=str))
print("\n=== VERIFICATION ===")
print(json.dumps(ver, indent=2))
