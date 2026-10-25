from app.investigator.report import _cell, _table, to_markdown


def sample_result(evidence):
    return {
        "status": "ok",
        "incident": "Users reported checkout failures",
        "requested_range": {"start": "2026-10-01 00:00:00", "end": "2026-10-01 23:59:59"},
        **evidence,
        "hypothesis": {
            "root_cause_service": "db-service",
            "root_cause_error_type": "DB_CONNECTION_FAILED",
            "propagation_path": ["db-service", "order-service", "api-gateway"],
            "confidence": 0.9,
            "source": "llm",
            "explanation": "The database refused connections first.",
        },
        "verification": {
            "error_exists_in_window": True, "appeared_first": True,
            "coverage_of_failing_requests": 1.0, "verified": True,
        },
        "attempts": [
            {"attempt": 1, "error": "RuntimeError: quota"},
            {"attempt": 2, "hypothesis": {}, "verification": {"verified": True}},
        ],
    }


def test_cell_handles_none_pipes_and_newlines():
    assert _cell(None) == "-"
    assert _cell("a|b") == "a/b"
    assert _cell("line1\nline2") == "line1 line2"
    assert _cell(5) == "5"


def test_table_renders_header_separator_and_rows():
    out = _table([{"a": 1, "b": "x"}, {"a": 2}], ["a", "b"])
    lines = out.strip().split("\n")
    assert lines[0] == "| a | b |"
    assert lines[1] == "|---|---|"
    assert lines[2] == "| 1 | x |"
    assert lines[3] == "| 2 | - |"  # missing key renders as a dash


def test_table_with_no_rows():
    assert _table([], ["a"]).strip() == "_none_"


def test_no_anomaly_report():
    md = to_markdown({"status": "no_anomaly_found", "incident": "slow checkout"})
    assert "slow checkout" in md
    assert "No anomalous period was found" in md


def test_full_report_contains_every_section(evidence):
    md = to_markdown(sample_result(evidence))

    assert md.startswith("# Incident Investigation Report")
    for heading in ("## 1. Anomalous period", "## 2. Affected services",
                    "## 3. Major error groups", "## 4. Request traces",
                    "## 5. Timeline", "## 6. Root-cause hypothesis",
                    "## 7. Verification against logs", "## 8. Investigation attempts"):
        assert heading in md
    assert "Users reported checkout failures" in md
    assert "**Root cause service:** db-service" in md
    assert "db-service -> order-service -> api-gateway" in md
    assert "**Verified: True**" in md
    assert "Attempt 1: failed (RuntimeError: quota)" in md
    assert "Attempt 2: verified = True" in md


def test_report_renders_missing_values_as_dash(evidence):
    md = to_markdown(sample_result(evidence))
    # auth-service has no first_error (NaT in the fixture)
    assert "| auth-service | 0 | 0 | 160 | - |" in md.replace("NaT", "-")


def test_report_includes_example_trace_when_present(evidence):
    result = sample_result(evidence)
    result["traces"]["sample_traces"] = [{
        "request_id": "abc-123",
        "events": [{"ts": "t", "service": "db-service", "level": "ERROR",
                    "error_type": "E", "message": "boom"}],
    }]
    md = to_markdown(result)
    assert "Example trace (request `abc-123`)" in md
    assert "boom" in md
