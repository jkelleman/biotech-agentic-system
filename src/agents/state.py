"""Typed workflow contracts; raw inputs are validated before execution."""

from typing import List, Literal, Union
from typing_extensions import NotRequired, TypedDict


class AdverseEvent(TypedDict):
    description: str
    onset_day: NotRequired[int]
    severity: NotRequired[str]
    relation: NotRequired[str]


class LaboratoryData(TypedDict, total=False):
    alt_peak_uln: float
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


class NodeUpdate(TypedDict, total=False):
    coded_terms: List[str]
    draft_narrative: str
    compliance_score: float
    loop_count: int
    errors: List[str]
    is_approved: bool
    status: Literal["running", "approved", "review_required"]
    node_history: List[str]
