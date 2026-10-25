"""End-to-end checks against a real MariaDB.

Enable with:
    INTEGRATION_DB_URL=mysql+pymysql://loguser:logpass@127.0.0.1:3306/logsdb uv run pytest -m integration

The tests write synthetic rows dated 2001-01-01 (far from any real data), run the real
SQL queries over that day, and delete exactly those rows afterwards. They refuse to run
if that day already contains rows, so existing data is never touched.
"""
import random
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

DAY = datetime(2001, 1, 1)
DAY_END = DAY + timedelta(days=1)
INC_START_MIN = 14 * 60 + 5
INC_LEN_MIN = 30

EXPECTED_ROOT = {
    "db_failure": ("db-service", "DB_CONNECTION_FAILED"),
    "auth_failure": ("auth-service", "AUTH_FAILED"),
    "high_latency": ("db-service", "SLOW_QUERY"),
}


def _clear(engine):
    with engine.begin() as c:
        c.execute(text("DELETE FROM logs WHERE ts >= :a AND ts < :b"), {"a": DAY, "b": DAY_END})


@pytest.fixture(scope="module")
def engine():
    from app.db import engine as eng
    try:
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as ex:  # pragma: no cover
        pytest.skip(f"database not reachable: {ex}")
    return eng


@pytest.fixture
def seed(engine):
    """Factory that fills 2001-01-01 with one kind of incident, then cleans up."""
    from app import generator

    with engine.connect() as c:
        existing = c.execute(
            text("SELECT COUNT(*) FROM logs WHERE ts >= :a AND ts < :b"), {"a": DAY, "b": DAY_END}
        ).scalar()
    if existing:
        pytest.fail("logs already has rows dated 2001-01-01; refusing to touch them")

    def _seed(kind, n=20000):
        random.seed(2024)
        generator.generate(n, DAY, kind, INC_START_MIN, INC_LEN_MIN)

    yield _seed
    _clear(engine)


@pytest.mark.parametrize("kind", list(EXPECTED_ROOT))
def test_anomaly_window_overlaps_the_injected_incident(seed, kind):
    from app.investigator.anomaly import find_anomalous_period

    seed(kind)
    p = find_anomalous_period(DAY, DAY_END - timedelta(seconds=1))

    assert p is not None
    inc_start = DAY + timedelta(minutes=INC_START_MIN)
    inc_end = inc_start + timedelta(minutes=INC_LEN_MIN)
    tolerance = timedelta(minutes=3)
    assert inc_start - tolerance <= p["start"] <= inc_end
    assert inc_start <= p["end"] <= inc_end + tolerance
    assert p["baseline_bad_per_minute"] == 0.0


def test_quiet_day_has_no_anomaly(seed):
    from app.investigator.anomaly import find_anomalous_period
    from app.investigator import evidence

    seed("db_failure", n=0)  # nothing written for the day
    assert find_anomalous_period(DAY, DAY_END - timedelta(seconds=1)) is None
    assert evidence.collect_evidence(DAY, DAY_END - timedelta(seconds=1)) is None


def test_evidence_matches_a_database_outage(seed):
    from app.investigator.evidence import collect_evidence

    seed("db_failure")
    ev = collect_evidence(DAY, DAY_END - timedelta(seconds=1))

    assert ev is not None
    first = ev["services"][0]
    assert first["service"] == "db-service"          # failed first
    assert ev["services"][-1]["errors"] == 0         # auth-service stayed healthy
    groups = {(g["service"], g["error_type"]) for g in ev["error_groups"]}
    assert ("db-service", "DB_CONNECTION_FAILED") in groups
    assert ev["traces"]["requests_sampled"] > 0
    assert "db-service:ERROR" in ev["traces"]["common_paths"][0]["path"]
    assert ev["timeline"][0]["service"] in {"db-service", "auth-service"}


@pytest.mark.parametrize("kind", list(EXPECTED_ROOT))
def test_verify_accepts_truth_and_rejects_a_symptom(seed, kind):
    from app.investigator.evidence import collect_evidence
    from app.investigator.verify import verify

    seed(kind)
    ev = collect_evidence(DAY, DAY_END - timedelta(seconds=1))
    s, e = ev["period"]["start"], ev["period"]["end"]
    svc, et = EXPECTED_ROOT[kind]

    good = verify({"root_cause_service": svc, "root_cause_error_type": et}, s, e)
    assert good["verified"] is True

    bogus = verify({"root_cause_service": "cache-service", "root_cause_error_type": "NOPE"}, s, e)
    assert bogus["verified"] is False


def test_db_outage_symptom_is_rejected(seed):
    from app.investigator.evidence import collect_evidence
    from app.investigator.verify import verify

    seed("db_failure")
    ev = collect_evidence(DAY, DAY_END - timedelta(seconds=1))
    s, e = ev["period"]["start"], ev["period"]["end"]
    v = verify({"root_cause_service": "api-gateway", "root_cause_error_type": "TIMEOUT"}, s, e)
    assert v["error_exists_in_window"] is True
    assert v["appeared_first"] is False
    assert v["verified"] is False


@pytest.mark.parametrize("kind", list(EXPECTED_ROOT))
def test_full_investigation_without_llm_uses_verified_fallback(seed, monkeypatch, kind):
    """With the LLM unavailable the pipeline must still find the true root cause."""
    from app.investigator import pipeline, reasoning
    from app.investigator.report import to_markdown

    def llm_down(*a, **k):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(reasoning, "generate_hypothesis", llm_down)
    seed(kind)

    result = pipeline.investigate("Users reported failures around 2 PM", DAY, DAY_END - timedelta(seconds=1))

    svc, et = EXPECTED_ROOT[kind]
    assert result["status"] == "ok"
    assert result["hypothesis"]["source"] == "rule_based_fallback"
    assert result["hypothesis"]["root_cause_service"] == svc
    assert result["hypothesis"]["root_cause_error_type"] == et
    assert result["verification"]["verified"] is True
    assert "LLM unavailable" in result["attempts"][0]["error"]
    assert "Incident Investigation Report" in to_markdown(result)
