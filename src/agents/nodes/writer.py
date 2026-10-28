"""Source-grounded drafting without inferred diagnoses or trial details."""

from src.agents.state import AgentState, NodeUpdate


def write_medical_narrative(state: AgentState) -> NodeUpdate:
    record = state["raw_data"]
    sections = [f"# Patient Safety Narrative: Subject {record['subject_id']}"]
    sections.append("## Demographics and Cohort Placement")
    for field, label in (("age", "Age"), ("sex", "Sex"), ("treatment_arm", "Treatment arm")):
        sections.append(f"{label}: {record.get(field, 'Not reported')}")
    sections.append("## Extracted Events and Illustrative Terms")
    sections.append(
        "\n".join(f"- {term}" for term in state["coded_terms"])
        or "No affirmative findings identified by the configured rules."
    )
    sections.append("## Chronology of Present Case")
    for event in record.get("adverse_events", []):
        sections.append(
            f"Recorded event: **{event['description']}**. "
            f"Onset study day: {event.get('onset_day', 'Not reported')}. "
            f"Severity: {event.get('severity', 'Not reported')}. "
            f"Investigator relationship: {event.get('relation', 'Not reported')}."
        )
    if not record.get("adverse_events"):
        sections.append("No structured adverse-event entries supplied.")
    return {
        "draft_narrative": "\n\n".join(sections),
        "loop_count": state["loop_count"] + 1,
    }
