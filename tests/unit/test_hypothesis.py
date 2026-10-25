import json
from types import SimpleNamespace

import pandas as pd
import pytest

from app.investigator import hypothesis as hyp_mod

GOOD = {
    "root_cause_service": "db-service",
    "root_cause_error_type": "DB_CONNECTION_FAILED",
    "explanation": "db-service failed first.",
    "propagation_path": ["db-service", "order-service", "api-gateway"],
    "confidence": 0.9,
}


class FakeLLM:
    """Stands in for the OpenAI client; records the request and returns canned text."""

    def __init__(self, reply):
        self.reply = reply
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        message = SimpleNamespace(content=self.reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


# ---- _extract_json -------------------------------------------------------

def test_extract_json_plain():
    assert hyp_mod._extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_ignores_surrounding_prose_and_fences():
    text = 'Here you go:\n```json\n{"a": {"b": 2}}\n```\nHope that helps.'
    assert hyp_mod._extract_json(text) == {"a": {"b": 2}}


@pytest.mark.parametrize("text", ["", "no json here", "only { opening"])
def test_extract_json_without_object_raises(text):
    with pytest.raises(ValueError):
        hyp_mod._extract_json(text)


def test_extract_json_invalid_json_raises():
    with pytest.raises(json.JSONDecodeError):
        hyp_mod._extract_json("{not valid}")


# ---- _clean --------------------------------------------------------------

def test_clean_makes_evidence_json_safe(ts):
    raw = {"a": float("nan"), "t": ts("14:05:00"), "n": [1, (2, 3)], "s": "x", "none": None}
    cleaned = hyp_mod._clean(raw)
    assert cleaned["a"] is None
    assert cleaned["t"] == "2026-10-01 14:05:00"
    assert cleaned["n"] == [1, [2, 3]]
    json.dumps(cleaned)  # must not raise


def test_clean_output_for_nat_is_serialisable():
    json.dumps(hyp_mod._clean({"x": pd.NaT}))


# ---- generate_hypothesis -------------------------------------------------

def test_generate_hypothesis_returns_parsed_reply(monkeypatch, evidence):
    llm = FakeLLM(json.dumps(GOOD))
    monkeypatch.setattr(hyp_mod, "client", llm)

    out = hyp_mod.generate_hypothesis("checkout is failing", evidence)

    assert out == GOOD
    req = llm.requests[0]
    assert req["model"] == hyp_mod.LLM_MODEL
    assert req["response_format"] == {"type": "json_object"}
    prompt = req["messages"][0]["content"]
    assert "checkout is failing" in prompt
    assert "DB_CONNECTION_FAILED" in prompt
    assert "FAILED verification" not in prompt


def test_generate_hypothesis_includes_feedback_on_retry(monkeypatch, evidence):
    llm = FakeLLM(json.dumps(GOOD))
    monkeypatch.setattr(hyp_mod, "client", llm)
    feedback = {"hypothesis": {"root_cause_service": "api-gateway"},
                "verification": {"verified": False, "appeared_first": False}}

    hyp_mod.generate_hypothesis("checkout is failing", evidence, feedback)

    prompt = llm.requests[0]["messages"][0]["content"]
    assert "FAILED verification" in prompt
    assert "api-gateway" in prompt
    assert "appeared_first" in prompt


def test_generate_hypothesis_tolerates_chatty_reply(monkeypatch, evidence):
    llm = FakeLLM("Sure!\n```json\n" + json.dumps(GOOD) + "\n```")
    monkeypatch.setattr(hyp_mod, "client", llm)
    assert hyp_mod.generate_hypothesis("x", evidence) == GOOD


@pytest.mark.parametrize("reply", [None, "", "I cannot determine the cause."])
def test_generate_hypothesis_raises_on_unusable_reply(monkeypatch, evidence, reply):
    monkeypatch.setattr(hyp_mod, "client", FakeLLM(reply))
    with pytest.raises(ValueError):
        hyp_mod.generate_hypothesis("x", evidence)


# ---- rule_based_hypothesis -----------------------------------------------

def test_rule_based_picks_first_significant_error(evidence):
    out = hyp_mod.rule_based_hypothesis(evidence)
    assert out["root_cause_service"] == "db-service"
    assert out["root_cause_error_type"] == "DB_CONNECTION_FAILED"
    assert out["propagation_path"] == ["db-service", "order-service", "api-gateway"]
    assert out["source"] == "rule_based_fallback"
    assert out["confidence"] == 0.5
    assert "db-service" in out["explanation"]
    assert "100 occurrences" in out["explanation"]


def test_rule_based_ignores_low_volume_noise(evidence):
    # the noise row (auth-service / BAD_PASSWORD) starts earlier but has only 2 lines
    names = [(r["service"], r["error_type"]) for r in evidence["timeline"]]
    assert ("auth-service", "BAD_PASSWORD") in names
    out = hyp_mod.rule_based_hypothesis(evidence)
    assert out["root_cause_service"] != "auth-service"
    assert "auth-service" not in out["propagation_path"]


def test_rule_based_accepts_string_timestamps(evidence):
    for row in evidence["timeline"]:
        row["first_seen"] = row["first_seen"].strftime("%Y-%m-%d %H:%M:%S.%f")
        row["last_seen"] = row["last_seen"].strftime("%Y-%m-%d %H:%M:%S.%f")
    out = hyp_mod.rule_based_hypothesis(evidence)
    assert out["root_cause_service"] == "db-service"


def test_rule_based_path_has_no_duplicates(evidence, ts):
    evidence["timeline"].append({
        "service": "db-service", "level": "WARN", "error_type": "SLOW_QUERY",
        "first_seen": ts("14:05:05"), "last_seen": ts("14:10:00"), "occurrences": 50,
    })
    path = hyp_mod.rule_based_hypothesis(evidence)["propagation_path"]
    assert path.count("db-service") == 1
