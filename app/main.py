import os
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from .explore.queries import MAX_RANGE
from .explore.router import router as explore_router
from .investigator.pipeline import investigate
from .investigator.report import to_markdown

app = FastAPI(
    title="Agentic Log Investigation System",
    description="Investigates incidents in application logs and returns a verified root-cause report.",
)

# Optional: let a browser app on another origin call the API directly (the Next.js dev proxy does
# not need this). Example: CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

app.include_router(explore_router)


class InvestigationRequest(BaseModel):
    description: str = Field(min_length=1, examples=["Users reported checkout failures around 2 PM"])
    start: datetime = Field(examples=["2026-10-01T00:00:00"])
    end: datetime = Field(examples=["2026-10-01T23:59:59"])

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("description must not be blank")
        return value

    @field_validator("end")
    @classmethod
    def end_after_start(cls, value: datetime, info: ValidationInfo) -> datetime:
        start = info.data.get("start")
        if start is None:
            return value  # start itself failed validation; that error is reported already
        try:
            if value <= start:
                raise ValueError("end must be after start")
            if value - start > MAX_RANGE:
                raise ValueError(f"range too large (max {MAX_RANGE.days} days)")
        except TypeError:
            raise ValueError("start and end must both include, or both omit, a timezone")
        return value


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/investigate")
def run_investigation(req: InvestigationRequest):
    """Full structured result as JSON."""
    return investigate(req.description, req.start, req.end)


@app.post("/investigate/report", response_class=PlainTextResponse)
def run_report(req: InvestigationRequest):
    """Same investigation, returned as a Markdown report."""
    return to_markdown(investigate(req.description, req.start, req.end))


@app.post("/report/render", response_class=PlainTextResponse)
def render_report(result: dict[str, Any]):
    """Render the Markdown report for a result you already have. Runs no new investigation."""
    if result.get("status") not in ("ok", "no_anomaly_found"):
        raise HTTPException(status_code=422, detail="body must be a result returned by /investigate")
    try:
        return to_markdown(result)
    except (KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail=f"incomplete investigation result: {exc}")
