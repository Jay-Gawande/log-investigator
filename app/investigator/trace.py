import pandas as pd
from sqlalchemy import bindparam, text

from ..db import engine, query_df


def _dt(x):
    return pd.Timestamp(x).to_pydatetime()


def sample_error_request_ids(start, end, n=200):
    df = query_df("""
        SELECT request_id
        FROM logs
        WHERE level = 'ERROR' AND ts >= :s AND ts < :e
        GROUP BY request_id
        LIMIT :n
    """, s=_dt(start), e=_dt(end), n=n)
    return df["request_id"].tolist()


def fetch_request_logs(request_ids):
    """All log lines (any service, any time) for the given request IDs."""
    if not request_ids:
        return pd.DataFrame()
    stmt = text("""
        SELECT request_id, ts, service, level, error_type, message
        FROM logs
        WHERE request_id IN :ids
        ORDER BY request_id, ts
    """).bindparams(bindparam("ids", expanding=True))
    with engine.connect() as c:
        return pd.read_sql(stmt, c, params={"ids": list(request_ids)})


def trace_summary(start, end, sample_size=200, show=3):
    """Common request paths among failing requests + a few full traces."""
    ids = sample_error_request_ids(start, end, sample_size)
    df = fetch_request_logs(ids)
    if df.empty:
        return {"requests_sampled": 0, "common_paths": [], "sample_traces": []}

    paths = (
        df.groupby("request_id")
        .apply(lambda g: " > ".join(f"{s}:{l}" for s, l in zip(g["service"], g["level"])),
               include_groups=False)
    )
    common = paths.value_counts().head(5)

    samples = []
    for rid in ids[:show]:
        g = df[df["request_id"] == rid]
        samples.append({
            "request_id": rid,
            "events": [
                {"ts": str(r.ts), "service": r.service, "level": r.level,
                 "error_type": r.error_type, "message": r.message}
                for r in g.itertuples()
            ],
        })

    return {
        "requests_sampled": len(ids),
        "common_paths": [{"path": p, "count": int(c)} for p, c in common.items()],
        "sample_traces": samples,
    }
