def _cell(v):
    if v is None:
        return "-"
    return str(v).replace("|", "/").replace("\n", " ")


def _table(rows, cols):
    if not rows:
        return "_none_\n"
    out = ["| " + " | ".join(cols) + " |",
           "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        out.append("| " + " | ".join(_cell(r.get(c)) for c in cols) + " |")
    return "\n".join(out) + "\n"


def to_markdown(result):
    if result.get("status") != "ok":
        return (f"# Investigation Report\n\n**Incident:** {result.get('incident')}\n\n"
                "No anomalous period was found in the requested time range.\n")

    p = result["period"]
    h = result["hypothesis"]
    v = result["verification"]
    tr = result["traces"]

    lines = []
    add = lines.append

    add("# Incident Investigation Report\n")
    add(f"**Incident description:** {result['incident']}\n")
    add(f"**Searched range:** {result['requested_range']['start']} to {result['requested_range']['end']}\n")

    add("## 1. Anomalous period\n")
    add(f"- **Start:** {p['start']}")
    add(f"- **End:** {p['end']}")
    add(f"- **Error/warn lines in window:** {p['bad_lines_in_window']}")
    add(f"- **Peak per minute:** {p['peak_bad_per_minute']} (normal baseline: {p['baseline_bad_per_minute']})\n")

    add("## 2. Affected services (ordered by first error)\n")
    add(_table(result["services"],
               ["service", "errors", "warns", "total_lines", "first_error", "avg_latency_ms"]))

    add("## 3. Major error groups\n")
    add(_table(result["error_groups"],
               ["service", "level", "error_type", "pattern", "count", "first_seen", "last_seen"]))

    add("## 4. Request traces\n")
    add(f"Failing requests sampled: **{tr['requests_sampled']}**\n")
    add("Most common request paths among failing requests:\n")
    add(_table(tr["common_paths"], ["path", "count"]))
    if tr["sample_traces"]:
        t = tr["sample_traces"][0]
        add(f"\nExample trace (request `{t['request_id']}`):\n")
        add(_table(t["events"], ["ts", "service", "level", "error_type", "message"]))

    add("\n## 5. Timeline\n")
    add(_table(result["timeline"],
               ["first_seen", "service", "level", "error_type", "occurrences", "last_seen"]))

    add("\n## 6. Root-cause hypothesis\n")
    add(f"- **Root cause service:** {h.get('root_cause_service')}")
    add(f"- **Root cause error type:** {h.get('root_cause_error_type')}")
    add(f"- **Propagation path:** {' -> '.join(h.get('propagation_path') or [])}")
    add(f"- **Confidence:** {h.get('confidence')}")
    add(f"- **Produced by:** {h.get('source', 'unknown')}\n")
    add(f"{h.get('explanation')}\n")

    add("## 7. Verification against logs\n")
    add(f"- Claimed error exists in window: **{v.get('error_exists_in_window')}**")
    add(f"- Appeared before all other significant errors: **{v.get('appeared_first')}**")
    add(f"- Share of failing requests containing it: **{v.get('coverage_of_failing_requests')}**")
    add(f"- **Verified: {v.get('verified')}**\n")

    add("## 8. Investigation attempts\n")
    for a in result["attempts"]:
        if "error" in a:
            add(f"- Attempt {a['attempt']}: failed ({a['error']})")
        else:
            add(f"- Attempt {a['attempt']}: verified = {a['verification'].get('verified')}")
    add("")

    return "\n".join(lines)
