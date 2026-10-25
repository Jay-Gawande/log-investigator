"""Read-only endpoints used by the frontend: /meta, /logs/overview, /logs, /requests/{id}."""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from .. import schemas
from . import queries

router = APIRouter(tags=["explore"])


def _check_range(start: datetime, end: datetime) -> None:
    try:
        if end <= start:
            raise HTTPException(status_code=422, detail="end must be after start")
        if end - start > queries.MAX_RANGE:
            raise HTTPException(
                status_code=422, detail=f"range too large (max {queries.MAX_RANGE.days} days)"
            )
    except TypeError:
        raise HTTPException(
            status_code=422, detail="start and end must both include, or both omit, a timezone"
        )


@router.get("/meta", response_model=schemas.MetaResponse)
def meta():
    """Data range, row count and the distinct services, levels and error types."""
    return queries.get_meta()


@router.get("/logs/overview", response_model=schemas.OverviewResponse)
def logs_overview(
    start: datetime,
    end: datetime,
    bucket_minutes: int | None = None,
    service: str | None = None,
):
    """Error, warning and total counts per time bucket (for the overview chart)."""
    _check_range(start, end)
    try:
        return queries.get_overview(start, end, bucket_minutes, service)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/logs", response_model=schemas.LogsResponse)
def logs(
    start: datetime,
    end: datetime,
    service: Annotated[str | None, Query(max_length=50)] = None,
    level: Annotated[str | None, Query(max_length=10)] = None,
    error_type: Annotated[str | None, Query(max_length=50)] = None,
    request_id: Annotated[str | None, Query(max_length=36)] = None,
    q: Annotated[str | None, Query(max_length=200, description="substring of the message")] = None,
    order: Literal["asc", "desc"] = "asc",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Filterable, paginated log lines. Fetches one extra row to compute has_more."""
    _check_range(start, end)
    try:
        return queries.search_logs(
            start, end, service=service, level=level, error_type=error_type,
            request_id=request_id, q=q, order=order, limit=limit, offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/requests/{request_id}", response_model=schemas.TraceResponse)
def request_trace(request_id: str):
    """Every log line of one request across services, in time order."""
    if not queries.UUID_RE.match(request_id):
        raise HTTPException(status_code=422, detail="request_id must be a UUID")
    trace = queries.request_trace(request_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="No request with this id")
    return trace
