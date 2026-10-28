"""Seeded, streaming fictional clinical fixtures with independent expected findings.

Emails use reserved .invalid domains, telephone numbers use the fictional NANP
555-01xx range, and SSNs start with the invalid area 000. No patient data is used.
"""

import random
from dataclasses import dataclass
from typing import Iterator, TypedDict

from src.agents.state import ClinicalRecord


class SyntheticContact(TypedDict):
    address: str
    email_address: str


class SyntheticClinicalRecord(ClinicalRecord, total=False):
    email: str
    date_of_birth: str
    medical_record_number: str
    contact: SyntheticContact


@dataclass(frozen=True)
class SyntheticCase:
    record: SyntheticClinicalRecord
    expected_terms: tuple[str, ...]
    forbidden_identifiers: tuple[str, ...]


_NAMES = (
    ("Avery", "Example"), ("Morgan", "Sample"), ("Quinn", "Testcase"),
    ("Riley", "Fictional"), ("Casey", "Demonstration"), ("Jordan", "Placeholder"),
)
_PHONE_STYLES = (
    "{area}-{exchange}-{line}",
    "({area}) {exchange}-{line}",
    "+1 {area} {exchange} {line}",
    "{area}.{exchange}.{line}",
    "{area}{exchange}{line}",
    "+1 ({area}) {exchange}-{line} ext. 42",
    "{area}-{exchange}-{line} x123",
)
_SCENARIOS = (
    ("Patient denies nausea but reports vomiting.", "Vomiting",
     "Gastrointestinal disorders: Vomiting"),
    ("No vomiting or headache. Patient reports nausea.", "Nausea",
     "Gastrointestinal disorders: Nausea"),
    ("Nausea and vomiting were denied. Headache is absent.", "", ""),
    ("Patient developed headache; denies nausea and vomiting.", "Headache",
     "Nervous system disorders: Headache"),
    ("No nausea. Acute cholecystitis documented.", "Acute cholecystitis",
     "Gastrointestinal disorders: Cholecystitis"),
)


def _validate_parameters(count: int, seed: int, note_repetitions: int) -> None:
    if type(count) is not int or count < 0:
        raise ValueError("count must be a non-negative integer")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(note_repetitions) is not int or note_repetitions < 1:
        raise ValueError("note_repetitions must be a positive integer")


def _phone(index: int, style: int) -> str:
    return _PHONE_STYLES[style % len(_PHONE_STYLES)].format(
        area="202", exchange="555", line=f"{100 + index % 100:04d}",
    )


def generate_mock_cases(
    count: int = 1000, *, seed: int = 42, note_repetitions: int = 1,
) -> Iterator[SyntheticCase]:
    """Return a lazy, reproducible stream, including ground truth for evaluation.

    Scenarios and phone styles cycle to guarantee coverage; a private seeded RNG
    varies demographics and source fields without changing the global random state.
    Generation allocates one case at a time, regardless of count.
    """
    _validate_parameters(count, seed, note_repetitions)
    return _iter_cases(count, seed, note_repetitions)


def _iter_cases(count: int, seed: int, note_repetitions: int) -> Iterator[SyntheticCase]:
    rng = random.Random(seed)
    for index in range(count):
        first, last = rng.choice(_NAMES)
        name = f"{first} {last}"
        subject_id = f"SYN-{seed}-{index:08d}"
        age = rng.randint(18, 96)
        dob = f"{2026 - age:04d}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        email = f"{first.lower()}.{last.lower()}+trial{index}@site{index % 11}.example.invalid"
        other_email = f"care.team+case{index}@unit{index % 7}.example.invalid"
        phone = _phone(index, index)
        other_phone = _phone(index + 31, index + 3)
        ssn = f"000-{10 + index % 90:02d}-{index % 10000:04d}"
        mrn = f"MRN-SYN-{seed}-{index:08d}"
        address = f"{100 + index} Synthetic Example Lane"
        clinical, event, term = _SCENARIOS[index % len(_SCENARIOS)]
        severity = rng.choice(("Mild", "Moderate", "Severe"))
        alt = (2.99, 3.0, 3.01, 0.0, 6.2)[index % 5]
        ast = (1.0, 2.99, 3.0, 3.01, 0.0)[index % 5]
        bilirubin = (1.99, 2.0, 2.01, 0.0, 3.7)[index % 5]
        laboratory_text = (
            f"Laboratory results: ALT {alt}x ULN; AST {ast}x ULN; "
            f"bilirubin {bilirubin}x ULN."
        )
        note = (
            f"{name}, subject {subject_id}, {age}-year-old; DOB {dob}; "
            f"SSN {ssn}; MRN {mrn}; address {address}.\n"
            f"Contact {email} at {phone}; alternate {other_email} at {other_phone}.\n"
            + "\n".join(
                f"{clinical} {laboratory_text} "
                "The patient remains alert; observations documented by study staff."
                for _ in range(note_repetitions)
            )
        )
        record: SyntheticClinicalRecord = {
            "subject_id": subject_id,
            "patient_name": name,
            "ssn": ssn,
            "phone": phone,
            "email": email,
            "date_of_birth": dob,
            "medical_record_number": mrn,
            "contact": {"address": address, "email_address": other_email},
            "age": age,
            "sex": rng.choice(("Female", "Male", "Not reported")),
            "treatment_arm": rng.choice(("Investigational treatment", "Comparator", "Placebo")),
            "labs": {
                "alt_peak_uln": str(alt) if index % 2 else alt,
                "ast_peak_uln": ast,
                "bili_peak_uln": bilirubin,
            },
            "adverse_events": [{
                "description": f"{event} reported in {name} ({subject_id})",
                "onset_day": rng.randint(1, 90),
                "severity": severity,
                "relation": rng.choice(("Unrelated", "Possibly related", "Not assessed")),
            }] if event else [],
            "clinical_notes": note,
        }
        expected = [f"{term} ({severity})", term] if event else []
        # The oracle intentionally does not import the production threshold engine.
        if alt >= 3:
            expected.append(f"Investigations: Alanine aminotransferase increased ({alt}x ULN)")
        if ast >= 3:
            expected.append(f"Investigations: Aspartate aminotransferase increased ({ast}x ULN)")
        if bilirubin >= 2:
            expected.append(f"Investigations: Blood bilirubin increased ({bilirubin}x ULN)")
        yield SyntheticCase(
            record=record,
            expected_terms=tuple(expected),
            forbidden_identifiers=(
                name, first, last, dob, email, other_email, phone, other_phone, ssn, mrn, address,
            ),
        )


def generate_clinical_records(
    count: int = 1000, *, seed: int = 42, note_repetitions: int = 1,
) -> Iterator[SyntheticClinicalRecord]:
    """Record-only interface for local pipelines and multi-thousand-record loads."""
    return (
        case.record
        for case in generate_mock_cases(count, seed=seed, note_repetitions=note_repetitions)
    )
