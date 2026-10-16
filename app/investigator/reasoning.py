from .hypothesis import generate_hypothesis, rule_based_hypothesis
from .verify import verify


def find_root_cause(description, evidence):
    """LLM -> verify -> one retry with feedback -> rule-based fallback.
    Returns (hypothesis, verification, attempts_log)."""
    s, e = evidence["period"]["start"], evidence["period"]["end"]
    log = []
    feedback = None

    for attempt in (1, 2):
        try:
            hyp = generate_hypothesis(description, evidence, feedback)
        except Exception as ex:  # quota, network, bad JSON...
            log.append({"attempt": attempt, "error": f"{type(ex).__name__}: {ex}"})
            break
        ver = verify(hyp, s, e)
        log.append({"attempt": attempt, "hypothesis": hyp, "verification": ver})
        if ver.get("verified"):
            hyp["source"] = "llm"
            return hyp, ver, log
        feedback = {"hypothesis": hyp, "verification": ver}

    hyp = rule_based_hypothesis(evidence)
    ver = verify(hyp, s, e)
    log.append({"attempt": "fallback", "hypothesis": hyp, "verification": ver})
    return hyp, ver, log
