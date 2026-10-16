import pandas as pd

from ..db import query_df


def minute_counts(start, end):
    """Number of ERROR/WARN lines per minute in [start, end]."""
    df = query_df("""
        SELECT TIMESTAMP(DATE(ts), SEC_TO_TIME(FLOOR(TIME_TO_SEC(ts) / 60) * 60)) AS minute,
               SUM(level IN ('ERROR', 'WARN')) AS bad,
               COUNT(*) AS total
        FROM logs
        WHERE ts BETWEEN :s AND :e
        GROUP BY minute
        ORDER BY minute
    """, s=start, e=end)
    df["minute"] = pd.to_datetime(df["minute"])
    df["bad"] = df["bad"].astype(float)
    return df


def find_anomalous_period(start, end, threshold=3.0, max_gap_minutes=2):
    df = minute_counts(start, end)
    if df.empty:
        return None

    median = df["bad"].median()
    mad = (df["bad"] - median).abs().median()
    mad = max(mad, 1.0)  # floor, so a perfectly quiet baseline does not divide by zero
    df["score"] = (df["bad"] - median) / (1.4826 * mad)

    flagged = df[df["score"] > threshold]
    if flagged.empty:
        return None

    # merge flagged minutes that are close together into windows
    windows = []
    w_start = w_end = flagged.iloc[0]["minute"]
    for m in flagged["minute"].iloc[1:]:
        if (m - w_end) <= pd.Timedelta(minutes=max_gap_minutes):
            w_end = m
        else:
            windows.append((w_start, w_end))
            w_start = w_end = m
    windows.append((w_start, w_end))

    # choose the window with the most bad lines
    def weight(w):
        mask = (flagged["minute"] >= w[0]) & (flagged["minute"] <= w[1])
        return flagged.loc[mask, "bad"].sum()

    best = max(windows, key=weight)
    mask = (df["minute"] >= best[0]) & (df["minute"] <= best[1])

    return {
        "start": best[0],
        "end": best[1] + pd.Timedelta(minutes=1),
        "bad_lines_in_window": int(df.loc[mask, "bad"].sum()),
        "peak_bad_per_minute": int(df.loc[mask, "bad"].max()),
        "baseline_bad_per_minute": float(median),
        "other_windows_found": len(windows) - 1,
    }
