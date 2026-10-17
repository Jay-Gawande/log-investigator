from datetime import datetime

from .anomaly import find_anomalous_period, minute_counts

start = datetime(2026, 10, 1, 0, 0, 0)
end = datetime(2026, 10, 1, 23, 59, 59)

print("--- busiest 5 minutes (errors+warns per minute) ---")
counts = minute_counts(start, end)
print(counts.sort_values("bad", ascending=False).head(5).to_string(index=False))

print("\n--- detected anomalous period ---")
result = find_anomalous_period(start, end)
if result is None:
    print("No anomaly found")
else:
    for k, v in result.items():
        print(f"{k}: {v}")
