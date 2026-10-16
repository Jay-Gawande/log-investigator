import pandas as pd

from ..db import query_df


def build_timeline(start, end):
    """One row per (service, level, error_type): when it first/last appeared, how often.
    Ordered by first appearance, which shows how the failure propagated."""
    df = query_df("""
        SELECT service, level, COALESCE(error_type, '-') AS error_type,
               MIN(ts) AS first_seen, MAX(ts) AS last_seen, COUNT(*) AS occurrences
        FROM logs
        WHERE level IN ('ERROR', 'WARN') AND ts >= :s AND ts < :e
        GROUP BY service, level, error_type
        ORDER BY first_seen
    """, s=pd.Timestamp(start).to_pydatetime(), e=pd.Timestamp(end).to_pydatetime())
    return df
