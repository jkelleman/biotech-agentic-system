"""Typed workflow contracts and fail-fast clinical input validation."""

from copy import deepcopy
from typing import Literal, TypedDict

from src.agents.utils.rules import validate_labs


class AdverseEvent(TypedDict, total=False):
    description: str
    onset_day: int | str
    severity: str
    relation: str


class ClinicalRecord(TypedDict, total=False):
    subject_id: str
    patient_name: str
    ssn: str
    phone: str
    age: int | str
    sex: str
    treatment_arm: str
    adverse_events: list[AdverseEvent]
    labs: dict[str, float | int | str]
    clinical_notes: str


class AgentState(TypedDict):
    raw_data: ClinicalRecord
    coded_terms: list[str]
    draft_narrative: str
    compliance_score: float
    loop_count: int
    errors: list[str]
    is_approved: bool
    status: Literal["ready", "running", "approved", "review_required"]
    node_history: list[str]
    output_narrative: str


class WorkflowInput(TypedDict):
    raw_data: ClinicalRecord


class AgentUpdate(TypedDict, total=False):
    coded_terms: list[str]
    draft_narrative: str
    compliance_score: float
    loop_count: int
    errors: list[str]
    is_approved: bool
    status: Literal["ready", "running", "approved", "review_required"]
    node_history: list[str]
    output_narrative: str


def validate_record(record: ClinicalRecord) -> None:
    if not isinstance(record, dict):
        raise ValueError("Clinical record must be an object")
    subject_id = record.get("subject_id")
    if not isinstance(subject_id, str) or not subject_id.strip():
        raise ValueError("subject_id must be a non-empty string")
    for field in ("sex", "treatment_arm", "clinical_notes"):
        if field in record and not isinstance(record[field], str):
            raise ValueError(f"{field} must be a string")
    age = record.get("age")
    if "age" in record and not (
        (type(age) is int and 0 <= age <= 130) or age == "90+"
    ):
        raise ValueError("age must be an integer in [0, 130] or '90+'")
    events = record.get("adverse_events", [])
    if not isinstance(events, list):
        raise ValueError("adverse_events must be a list")
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Each adverse event must be an object")
        if not isinstance(event.get("description"), str) or not event["description"].strip():
            raise ValueError("Each adverse event requires a description")
        for field in ("severity", "relation"):
            if field in event and not isinstance(event.get(field), str):
                raise ValueError(f"Event {field} must be a string")
        if "onset_day" in event:
            onset = event["onset_day"]
            if isinstance(onset, bool) or not isinstance(onset, (int, str)):
                raise ValueError("Event onset_day must be an integer or string")
    validate_labs(record.get("labs", {}))


def initialize_state(initial: WorkflowInput) -> AgentState:
    """Always start a new run; caller-owned data and previous results are not mutated."""
    if not isinstance(initial, dict) or "raw_data" not in initial:
        raise ValueError("Initial state requires raw_data")
    validate_record(initial["raw_data"])
    return {
        "raw_data": deepcopy(initial["raw_data"]),
        "coded_terms": [],
        "draft_narrative": "",
        "compliance_score": 0.0,
        "loop_count": 0,
        "errors": [],
        "is_approved": False,
        "status": "ready",
        "node_history": [],
        "output_narrative": "",
    }
