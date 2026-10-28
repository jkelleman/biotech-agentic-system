"""Typed workflow contracts; raw inputs are validated before execution."""

from copy import deepcopy
from typing import List, Literal, Union
from typing_extensions import NotRequired, TypedDict

from src.agents.utils.validation import validate_record as validate_clinical_record


class AdverseEvent(TypedDict):
    description: str
    onset_day: NotRequired[int]
    severity: NotRequired[str]
    relation: NotRequired[str]


class LaboratoryData(TypedDict, total=False):
    alt_peak_uln: float
    ast_peak_uln: float
    bili_peak_uln: float


class ClinicalRecord(TypedDict):
    subject_id: str
    age: NotRequired[Union[int, Literal["90+"]]]
    sex: NotRequired[str]
    treatment_arm: NotRequired[str]
    clinical_notes: NotRequired[str]
    labs: NotRequired[LaboratoryData]
    adverse_events: NotRequired[List[AdverseEvent]]


class AgentState(TypedDict):
    raw_data: ClinicalRecord
    coded_terms: List[str]
    draft_narrative: str
    compliance_score: float
    loop_count: int
    errors: List[str]
    is_approved: bool
    status: NotRequired[Literal["running", "approved", "review_required"]]
    node_history: NotRequired[List[str]]
    output_narrative: str


class NodeUpdate(TypedDict, total=False):
    coded_terms: List[str]
    draft_narrative: str
    compliance_score: float
    loop_count: int
    errors: List[str]
    is_approved: bool
    status: Literal["running", "approved", "review_required"]
    node_history: List[str]
    output_narrative: str


AgentUpdate = NodeUpdate


class WorkflowInput(TypedDict):
    raw_data: ClinicalRecord


def validate_record(record: ClinicalRecord) -> None:
    validate_clinical_record(record)


def initialize_state(initial: WorkflowInput) -> AgentState:
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
        "status": "running",
        "node_history": [],
        "output_narrative": "",
    }
