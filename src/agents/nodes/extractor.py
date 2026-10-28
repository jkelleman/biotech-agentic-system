"""Deterministic extraction with shared text and laboratory rules."""

from src.agents.state import AgentState, NodeUpdate
from src.agents.utils.phenotyping import clinical_terms, event_term, laboratory_terms


def extract_and_code_data(state: AgentState) -> NodeUpdate:
    record = state["raw_data"]
    terms = []
    for event in record.get("adverse_events", []):
        term = event_term(event["description"])
        if term is not None:
            terms.append(f"{term} ({event.get('severity', 'Not reported')})")
    terms.extend(clinical_terms(record.get("clinical_notes", "")))
    terms.extend(laboratory_terms(record.get("labs", {})))
    return {"coded_terms": list(dict.fromkeys(terms))}
