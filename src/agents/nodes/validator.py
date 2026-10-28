"""Selected source-presence checks, not a clinical or compliance certification."""

import re

from src.agents.state import AgentState, NodeUpdate
from src.agents.utils.phenotyping import laboratory_terms

DEDUCTION_PER_ERROR = 0.15


def quality_control_check(state: AgentState) -> NodeUpdate:
    record = state["raw_data"]
    draft = state["draft_narrative"]
    errors = []

    def contains(value: object) -> bool:
        return re.search(r"(?<!\w)" + re.escape(str(value)) + r"(?!\w)", draft, re.IGNORECASE) is not None

    if not contains(record["subject_id"]):
        errors.append("Omission: Subject ID is missing.")
    for field in ("age", "sex", "treatment_arm"):
        if field in record and not contains(record[field]):
            errors.append(f"Omission: {field} is missing or incorrect.")
    for term in laboratory_terms(record.get("labs", {})):
        if term not in draft:
            errors.append("Clinical Omission: Laboratory threshold finding or exact value is missing.")
    for event in record.get("adverse_events", []):
        for field in ("description", "onset_day", "severity", "relation"):
            if field in event and not contains(event[field]):
                errors.append(f"Data Mismatch: Adverse-event {field} is missing.")
    for term in state["coded_terms"]:
        if term not in draft:
            errors.append("Omission: Extracted finding is missing.")
    return {
        "compliance_score": max(0.0, 1.0 - len(errors) * DEDUCTION_PER_ERROR),
        "errors": errors,
    }
