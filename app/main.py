from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .investigator.pipeline import investigate
from .investigator.report import to_markdown

app = FastAPI(
    title="Agentic Log Investigation System",
    description="Investigates incidents in application logs and returns a verified root-cause report.",
)


class InvestigationRequest(BaseModel):
    description: str = Field(examples=["Users reported checkout failures around 2 PM"])
    start: datetime = Field(examples=["2026-10-01T00:00:00"])
    end: datetime = Field(examples=["2026-10-01T23:59:59"])


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
