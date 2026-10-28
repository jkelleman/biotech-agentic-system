"""Source-grounded narrative templates; missing facts are never invented."""

from src.agents.state import AgentState, AgentUpdate


def write_medical_narrative(state: AgentState) -> AgentUpdate:
    raw = state["raw_data"]
    sections = [
        f"# Patient Safety Narrative: Subject {raw['subject_id']}",
        "## Demographics",
        f"Age: {raw.get('age', 'Not reported')}; "
        f"Sex: {raw.get('sex', 'Not reported')}; "
        f"Treatment arm: {raw.get('treatment_arm', 'Not reported')}.",
        "## Extracted Findings (illustrative, not diagnostic coding)",
        "\n".join(f"- {term}" for term in state["coded_terms"])
        or "No findings matched the configured rules.",
        "## Reported Event Chronology",
    ]
    for event in raw.get("adverse_events", []):
        sections.append(
            f"Reported event: {event['description']}; "
            f"Onset day: {event.get('onset_day', 'Not reported')}; "
            f"Severity: {event.get('severity', 'Not reported')}; "
            f"Relationship: {event.get('relation', 'Not reported')}."
        )
    if not raw.get("adverse_events"):
        sections.append("No structured adverse events supplied.")
    return {
        "draft_narrative": "\n\n".join(sections),
        "loop_count": state["loop_count"] + 1,
    }
