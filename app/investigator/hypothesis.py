import json
import math

import pandas as pd
from openai import OpenAI

from ..config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

PROMPT = """You are an experienced site reliability engineer investigating a software incident.
Use ONLY the evidence below. Do not invent services, errors or numbers.

Incident description from the user:
{description}

Evidence (JSON). The timeline is ordered by when each error first appeared:
{evidence}
{feedback}
Decide which single (service, error_type) is the ROOT cause: the first thing that
broke, not the downstream symptoms. Return ONLY a JSON object with these keys:
- "root_cause_service": string, exactly as it appears in the evidence
- "root_cause_error_type": string, exactly as it appears in the evidence
- "explanation": string, 2-4 sentences using numbers from the evidence
- "propagation_path": list of service names in the order the failure spread
- "confidence": number between 0 and 1
No text before or after the JSON."""


def _clean(o):
    """Make evidence JSON-safe: NaN -> None, timestamps -> strings."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, float) and math.isnan(o):
        return None
    if o is None or isinstance(o, (str, int, float, bool)):
        return o
    return str(o)


def _extract_json(text):
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON in LLM reply: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def generate_hypothesis(description, evidence, feedback=None):
    fb = ""
    if feedback:
        fb = ("\nYour previous hypothesis FAILED verification against the logs:\n"
              + json.dumps(_clean(feedback), indent=2)
              + "\nReconsider and answer again.\n")
    prompt = PROMPT.format(
        description=description,
        evidence=json.dumps(_clean(evidence), indent=1),
        feedback=fb,
    )
    r = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,  # generous: Gemini 2.5 "thinking" tokens count against this
        response_format={"type": "json_object"},
    )
    text = r.choices[0].message.content or ""
    return _extract_json(text)


def rule_based_hypothesis(evidence):
    """No-LLM fallback: the significant error group that appeared first is the root cause."""
    tl = pd.DataFrame(evidence["timeline"])
    tl["first_seen"] = pd.to_datetime(tl["first_seen"])
    tl = tl[tl["occurrences"] >= 0.1 * tl["occurrences"].max()].sort_values("first_seen")
    first = tl.iloc[0]
    path = list(dict.fromkeys(tl["service"]))
    return {
        "root_cause_service": first["service"],
        "root_cause_error_type": first["error_type"],
        "explanation": (
            f"{first['service']} was the first service to fail with {first['error_type']} "
            f"at {first['first_seen']}, with {int(first['occurrences'])} occurrences in the "
            f"anomalous window. Other affected services failed after it."),
        "propagation_path": path,
        "confidence": 0.5,
        "source": "rule_based_fallback",
    }
