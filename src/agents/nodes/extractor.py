"""Deterministic extraction from structured events and unstructured notes."""

from src.agents.state import AgentState, AgentUpdate
from src.agents.utils.rules import affirmed_terms, lab_findings


def extract_and_code_data(state: AgentState) -> AgentUpdate:
    raw = state["raw_data"]
    terms: dict[str, None] = {}
    for event in raw.get("adverse_events", []):
        for term in affirmed_terms(event["description"]):
            terms[f"{term} ({event.get('severity', 'Not reported')})"] = None
    for term in affirmed_terms(raw.get("clinical_notes", "")):
        terms[term] = None
    for term in lab_findings(raw.get("labs", {})):
        terms[term] = None
    return {"coded_terms": list(terms)}
