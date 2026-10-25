"""Read-only queries behind the explorer endpoints: meta, overview, log search, request trace.

All user-supplied values go through bound parameters. The only text spliced into SQL comes from
fixed whitelists (column names, ASC/DESC, hard-coded condition strings).
"""
import re
import time
from datetime import datetime, timedelta

import pandas as pd

from ..db import query_df

BUCKET_CHOICES = (1, 5, 15, 30, 60)   # minutes; each divides a day evenly
MAX_POINTS = 600                      # target chart points when the bucket size is automatic
MAX_BUCKETS = 5000                    # hard cap when the caller chooses the bucket size
MAX_RANGE = timedelta(days=31)
META_TTL_SECONDS = 60

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_ORDER = {"asc": "ASC", "desc": "DESC"}
_DISTINCT_COLUMNS = ("service", "level", "error_type")

_meta_cache: dict = {"at": 0.0, "value": None}


# ---------------------------------------------------------------- helpers

def _iso(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat(timespec="milliseconds")


def _none(value):
    return None if value is None or pd.isna(value) else value


def _int_or_none(value) -> int | None:
    return None if value is None or pd.isna(value) else int(value)


def escape_like(text: str) -> str:
    """Escape LIKE wildcards so user text is matched literally (backslash is MariaDB's default escape)."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def clear_meta_cache() -> None:
    _meta_cache["at"] = 0.0
    _meta_cache["value"] = None


# ---------------------------------------------------------------- meta

def _distinct(column: str) -> list[str]:
    if column not in _DISTINCT_COLUMNS:
        raise ValueError(f"unsupported column: {column}")
    df = query_df(f"SELECT DISTINCT {column} AS v FROM logs WHERE {column} IS NOT NULL ORDER BY v")
    return [str(v) for v in df["v"].tolist()]


def get_meta() -> dict:
    now = time.monotonic()
    cached = _meta_cache["value"]
    if cached is not None and now - _meta_cache["at"] < META_TTL_SECONDS:
        return cached

    span = query_df("SELECT MIN(ts) AS min_ts, MAX(ts) AS max_ts, COUNT(*) AS total_rows FROM logs")
    row = span.iloc[0]
    value = {
        "min_ts": _iso(row["min_ts"]),
        "max_ts": _iso(row["max_ts"]),
        "total_rows": int(row["total_rows"]),
        "services": _distinct("service"),
        "levels": _distinct("level"),
        "error_types": _distinct("error_type"),
    }
    _meta_cache["value"] = value
    _meta_cache["at"] = now
    return value


# ---------------------------------------------------------------- overview

def choose_bucket(start: datetime, end: datetime) -> int:
    """Smallest bucket (minutes) that keeps the chart at or under MAX_POINTS points."""
    minutes = max((end - start).total_seconds() / 60, 1)
    for bucket in BUCKET_CHOICES:
        if minutes / bucket <= MAX_POINTS:
            return bucket
    return BUCKET_CHOICES[-1]


def get_overview(start: datetime, end: datetime, bucket_minutes: int | None = None,
                 service: str | None = None) -> dict:
    """Error / warning / total counts per time bucket, with empty buckets filled with zeros."""
    if bucket_minutes is None:
        bucket_minutes = choose_bucket(start, end)
    if bucket_minutes not in BUCKET_CHOICES:
        raise ValueError(f"bucket_minutes must be one of {list(BUCKET_CHOICES)}")

    freq = f"{bucket_minutes}min"
    first = pd.Timestamp(start).floor(freq)
    last = pd.Timestamp(end).floor(freq)
    n_buckets = int((last - first) / pd.Timedelta(freq)) + 1
    if n_buckets > MAX_BUCKETS:
        raise ValueError("too many buckets: use a larger bucket_minutes or a shorter range")

    service_clause = " AND service = :service" if service else ""
    params: dict = {"s": start, "e": end, "sec": bucket_minutes * 60}
    if service:
        params["service"] = service

    df = query_df(f"""
        SELECT TIMESTAMP(DATE(ts), SEC_TO_TIME(FLOOR(TIME_TO_SEC(ts) / :sec) * :sec)) AS bucket,
               SUM(level = 'ERROR') AS errors,
               SUM(level = 'WARN')  AS warns,
               COUNT(*)             AS total
        FROM logs
        WHERE ts BETWEEN :s AND :e{service_clause}
        GROUP BY bucket
        ORDER BY bucket
    """, **params)

    columns = ["errors", "warns", "total"]
    if df.empty:
        df = pd.DataFrame({c: [] for c in columns}, index=pd.DatetimeIndex([], name="bucket"))
    else:
        df = df.copy()
        df["bucket"] = pd.to_datetime(df["bucket"])
        df = df.set_index("bucket")
        for c in columns:
            df[c] = pd.to_numeric(df[c])

    index = pd.date_range(first, last, freq=freq)
    df = df[columns].reindex(index, fill_value=0).astype(int)

    points = [
        {"ts": _iso(ts), "errors": int(r["errors"]), "warns": int(r["warns"]), "total": int(r["total"])}
        for ts, r in df.iterrows()
    ]
    return {"bucket_minutes": bucket_minutes, "points": points}


# ---------------------------------------------------------------- log search

def _log_row(r: dict) -> dict:
    return {
        "id": int(r["id"]),
        "ts": _iso(r["ts"]),
        "service": r["service"],
        "level": r["level"],
        "request_id": r["request_id"],
        "message": r["message"],
        "error_type": _none(r["error_type"]),
        "latency_ms": _int_or_none(r["latency_ms"]),
    }


def search_logs(start: datetime, end: datetime, *, service: str | None = None,
                level: str | None = None, error_type: str | None = None,
                request_id: str | None = None, q: str | None = None,
                order: str = "asc", limit: int = 100, offset: int = 0) -> dict:
    if order not in _ORDER:
        raise ValueError("order must be 'asc' or 'desc'")
    direction = _ORDER[order]

    conditions = ["ts BETWEEN :s AND :e"]
    params: dict = {"s": start, "e": end}
    if service:
        conditions.append("service = :service")
        params["service"] = service
    if level:
        conditions.append("level = :level")
        params["level"] = level
    if error_type:
        conditions.append("error_type = :error_type")
        params["error_type"] = error_type
    if request_id:
        conditions.append("request_id = :request_id")
        params["request_id"] = request_id
    if q:
        conditions.append("message LIKE :q")
        params["q"] = f"%{escape_like(q)}%"

    # fetch one extra row to learn whether another page exists, without a slow COUNT(*)
    params["lim"] = limit + 1
    params["off"] = offset
    where = " AND ".join(conditions)
    df = query_df(f"""
        SELECT id, ts, service, level, request_id, message, error_type, latency_ms
        FROM logs
        WHERE {where}
        ORDER BY ts {direction}, id {direction}
        LIMIT :lim OFFSET :off
    """, **params)

    has_more = len(df) > limit
    rows = df.head(limit).to_dict("records")
    return {
        "items": [_log_row(r) for r in rows],
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


# ---------------------------------------------------------------- request trace

def request_trace(request_id: str) -> dict | None:
    """All lines of one request in time order, or None when the id is unknown."""
    df = query_df("""
        SELECT id, ts, service, level, message, error_type, latency_ms
        FROM logs
        WHERE request_id = :rid
        ORDER BY ts, id
    """, rid=request_id)
    if df.empty:
        return None

    df = df.copy()
    df["ts"] = pd.to_datetime(df["ts"])
    t0 = df["ts"].iloc[0]
    df["offset_ms"] = ((df["ts"] - t0).dt.total_seconds() * 1000).round().astype(int)

    events = [
        {
            "id": int(r["id"]),
            "ts": _iso(r["ts"]),
            "offset_ms": int(r["offset_ms"]),
            "service": r["service"],
            "level": r["level"],
            "message": r["message"],
            "error_type": _none(r["error_type"]),
            "latency_ms": _int_or_none(r["latency_ms"]),
        }
        for r in df.to_dict("records")
    ]
    return {
        "request_id": request_id,
        "start": _iso(df["ts"].iloc[0]),
        "end": _iso(df["ts"].iloc[-1]),
        "duration_ms": int(df["offset_ms"].max()),
        "services": list(dict.fromkeys(df["service"].tolist())),
        "has_errors": bool((df["level"] == "ERROR").any()),
        "events": events,
    }
