"""Fail-closed clinical input validation without echoing patient values."""

from copy import deepcopy
from typing import Any, Dict

from src.agents.utils.phenotyping import lab_value


def validate_record(record: object) -> Dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("Clinical record must be an object.")
    subject = record.get("subject_id")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("subject_id must be a non-empty string.")
    age = record.get("age")
    if "age" in record and (
        type(age) is not int or not 0 <= age <= 130
    ):
        raise ValueError("age must be an integer in [0, 130].")
    for field in ("sex", "treatment_arm"):
        if field in record and (
            not isinstance(record[field], str) or not record[field].strip()
        ):
            raise ValueError(f"{field} must be a non-empty string.")
    if "clinical_notes" in record and not isinstance(record["clinical_notes"], str):
        raise ValueError("clinical_notes must be a string.")
    labs = record.get("labs", {})
    if not isinstance(labs, dict):
        raise ValueError("labs must be an object.")
    for field in ("alt_peak_uln", "bili_peak_uln"):
        if field in labs:
            lab_value(labs[field])
    events = record.get("adverse_events", [])
    if not isinstance(events, list):
        raise ValueError("adverse_events must be a list.")
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Each adverse event must be an object.")
        for field in ("description", "severity", "relation"):
            if field == "description" or field in event:
                if not isinstance(event.get(field), str) or not event[field].strip():
                    raise ValueError(f"Event {field} must be a non-empty string.")
        if "onset_day" in event and type(event["onset_day"]) is not int:
            raise ValueError("Event onset_day must be an integer.")
    validated = deepcopy(record)
    for field in ("alt_peak_uln", "bili_peak_uln"):
        if field in labs:
            validated["labs"][field] = lab_value(labs[field])
    return validated
