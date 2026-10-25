"""Response models for the explorer endpoints.

Timestamps are ISO strings without a timezone, for example 2026-10-01T14:05:00.060.
"""
from pydantic import BaseModel


class MetaResponse(BaseModel):
    min_ts: str | None
    max_ts: str | None
    total_rows: int
    services: list[str]
    levels: list[str]
    error_types: list[str]


class OverviewPoint(BaseModel):
    ts: str
    errors: int
    warns: int
    total: int


class OverviewResponse(BaseModel):
    bucket_minutes: int
    points: list[OverviewPoint]


class LogRow(BaseModel):
    id: int
    ts: str
    service: str
    level: str
    request_id: str
    message: str
    error_type: str | None = None
    latency_ms: int | None = None


class LogsResponse(BaseModel):
    items: list[LogRow]
    limit: int
    offset: int
    has_more: bool


class TraceEvent(BaseModel):
    id: int
    ts: str
    offset_ms: int
    service: str
    level: str
    message: str
    error_type: str | None = None
    latency_ms: int | None = None


class TraceResponse(BaseModel):
    request_id: str
    start: str
    end: str
    duration_ms: int
    services: list[str]
    has_errors: bool
    events: list[TraceEvent]
