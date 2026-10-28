"""Deterministic structural QC; this is not clinical approval."""

import re

from src.agents.state import AgentState, AgentUpdate
from src.agents.utils.rules import lab_findings

DEDUCTION_PER_ERROR = 0.15


def quality_control_check(state: AgentState) -> AgentUpdate:
    raw = state["raw_data"]
    draft = state["draft_narrative"].casefold()
    errors: list[str] = []
    for field in ("subject_id", "age", "sex", "treatment_arm"):
        if field in raw and not re.search(
            r"(?<!\w)" + re.escape(str(raw[field]).casefold()) + r"(?!\w)", draft
        ):
            errors.append(f"Omission: {field} is missing from the narrative.")
    for finding in lab_findings(raw.get("labs", {})):
        if finding.casefold() not in draft:
            errors.append("Clinical Omission: An abnormal laboratory value is missing or incorrect.")
    for event in raw.get("adverse_events", []):
        if event["description"].casefold() not in draft:
            errors.append("Data Mismatch: A reported adverse event is missing.")
    for term in state["coded_terms"]:
        if term.casefold() not in draft:
            errors.append("Clinical Omission: An extracted finding is missing.")
    return {
        "compliance_score": max(0.0, 1.0 - len(errors) * DEDUCTION_PER_ERROR),
        "errors": errors,
    }
