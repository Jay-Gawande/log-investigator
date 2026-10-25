"""The generate -> verify -> retry -> fallback loop, with the LLM and verifier faked."""
import pytest

from app.investigator import reasoning

LLM_HYP = {"root_cause_service": "db-service", "root_cause_error_type": "DB_CONNECTION_FAILED",
           "explanation": "x", "propagation_path": ["db-service"], "confidence": 0.9}
WRONG_HYP = {"root_cause_service": "api-gateway", "root_cause_error_type": "TIMEOUT",
             "explanation": "y", "propagation_path": ["api-gateway"], "confidence": 0.8}

OK = {"verified": True}
BAD = {"verified": False, "appeared_first": False}


@pytest.fixture
def stub(monkeypatch):
    """Install fake generate_hypothesis / verify. Returns a recorder."""
    class Recorder:
        feedbacks = []
        verify_calls = []

    def install(replies, verdicts):
        rec = Recorder()
        rec.feedbacks, rec.verify_calls = [], []
        replies, verdicts = list(replies), list(verdicts)

        def fake_generate(description, evidence, feedback=None):
            rec.feedbacks.append(feedback)
            r = replies.pop(0)
            if isinstance(r, Exception):
                raise r
            return dict(r)

        def fake_verify(hyp, s, e):
            rec.verify_calls.append(hyp)
            return verdicts.pop(0)

        monkeypatch.setattr(reasoning, "generate_hypothesis", fake_generate)
        monkeypatch.setattr(reasoning, "verify", fake_verify)
        return rec

    return install


def test_first_attempt_verified(stub, evidence):
    rec = stub([LLM_HYP], [OK])
    hyp, ver, log = reasoning.find_root_cause("desc", evidence)

    assert hyp["source"] == "llm"
    assert hyp["root_cause_service"] == "db-service"
    assert ver == OK
    assert [a["attempt"] for a in log] == [1]
    assert rec.feedbacks == [None]


def test_second_attempt_gets_feedback_and_can_succeed(stub, evidence):
    rec = stub([WRONG_HYP, LLM_HYP], [BAD, OK])
    hyp, ver, log = reasoning.find_root_cause("desc", evidence)

    assert hyp["source"] == "llm"
    assert hyp["root_cause_service"] == "db-service"
    assert [a["attempt"] for a in log] == [1, 2]
    assert rec.feedbacks[0] is None
    assert rec.feedbacks[1]["hypothesis"]["root_cause_service"] == "api-gateway"
    assert rec.feedbacks[1]["verification"] == BAD


def test_falls_back_to_rules_after_two_failed_attempts(stub, evidence):
    rec = stub([WRONG_HYP, WRONG_HYP], [BAD, BAD, OK])  # third verdict is for the fallback
    hyp, ver, log = reasoning.find_root_cause("desc", evidence)

    assert hyp["source"] == "rule_based_fallback"
    assert hyp["root_cause_service"] == "db-service"
    assert [a["attempt"] for a in log] == [1, 2, "fallback"]
    assert ver == OK


def test_llm_exception_goes_straight_to_fallback(stub, evidence):
    rec = stub([RuntimeError("quota exceeded")], [OK])
    hyp, ver, log = reasoning.find_root_cause("desc", evidence)

    assert hyp["source"] == "rule_based_fallback"
    assert log[0]["attempt"] == 1
    assert "RuntimeError: quota exceeded" in log[0]["error"]
    assert log[-1]["attempt"] == "fallback"
    assert len(rec.feedbacks) == 1  # no second LLM attempt after an exception


def test_exception_on_retry_keeps_failed_first_attempt_in_log(stub, evidence):
    stub([WRONG_HYP, ValueError("bad json")], [BAD, OK])
    hyp, ver, log = reasoning.find_root_cause("desc", evidence)

    assert hyp["source"] == "rule_based_fallback"
    assert log[0]["verification"] == BAD
    assert "ValueError" in log[1]["error"]


def test_verification_runs_over_the_anomalous_period(monkeypatch, evidence):
    seen = []
    monkeypatch.setattr(reasoning, "generate_hypothesis", lambda d, e, f=None: dict(LLM_HYP))
    monkeypatch.setattr(reasoning, "verify", lambda h, s, e: seen.append((s, e)) or OK)

    reasoning.find_root_cause("desc", evidence)
    assert seen == [(evidence["period"]["start"], evidence["period"]["end"])]
