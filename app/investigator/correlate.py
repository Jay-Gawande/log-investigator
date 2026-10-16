import re

import pandas as pd

from ..db import query_df


def _dt(x):
    return pd.Timestamp(x).to_pydatetime()


def service_summary(start, end):
    """Per-service error/warn counts in the window, ordered by who failed first."""
    df = query_df("""
        SELECT service,
               CAST(SUM(level = 'ERROR') AS SIGNED) AS errors,
               CAST(SUM(level = 'WARN') AS SIGNED) AS warns,
               COUNT(*) AS total_lines,
               MIN(CASE WHEN level = 'ERROR' THEN ts END) AS first_error,
               ROUND(AVG(latency_ms)) AS avg_latency_ms
        FROM logs
        WHERE ts >= :s AND ts < :e
        GROUP BY service
    """, s=_dt(start), e=_dt(end))
    # services with no errors (NaT) go last
    return df.sort_values("first_error", na_position="last").reset_index(drop=True)


def _template(msg: str) -> str:
    """Turn a message into a pattern so similar errors group together."""
    msg = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", "<uuid>", msg)
    msg = re.sub(r"for user \S+", "for user <user>", msg)
    msg = re.sub(r"\d+", "<n>", msg)
    return msg


def error_groups(start, end, top=10):
    """Group ERROR/WARN lines by (service, level, error_type, message pattern)."""
    df = query_df("""
        SELECT ts, service, level, error_type, message
        FROM logs
        WHERE level IN ('ERROR', 'WARN') AND ts >= :s AND ts < :e
    """, s=_dt(start), e=_dt(end))
    if df.empty:
        return df
    df["pattern"] = df["message"].map(_template)
    groups = (
        df.groupby(["service", "level", "error_type", "pattern"], dropna=False)
        .agg(count=("ts", "size"), first_seen=("ts", "min"), last_seen=("ts", "max"))
        .reset_index()
        .sort_values("count", ascending=False)
        .head(top)
    )
    return groups
