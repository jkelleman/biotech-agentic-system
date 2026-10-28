"""Bounded local terminology rules, not diagnostic or licensed MedDRA coding."""

import math
import re
from bisect import bisect_right
from dataclasses import dataclass


@dataclass(frozen=True)
class EventRule:
    pattern: re.Pattern[str]
    term: str


EVENT_RULES = (
    EventRule(re.compile(r"\b(?:cholecystitis|gallbladder inflammation)\b", re.I),
              "Gastrointestinal disorders: Cholecystitis"),
    EventRule(re.compile(
        r"\b(?:elevated|increased|high)\s+(?:alt|alanine aminotransferase)\b|"
        r"\b(?:alt|alanine aminotransferase)\s+(?:(?:is|was)\s+)?(?:elevated|increased|high)\b",
        re.I),
              "Investigations: Alanine aminotransferase increased"),
    EventRule(re.compile(
        r"\b(?:elevated|increased|high)\s+liver enzymes?\b|"
        r"\bliver enzymes?\s+(?:(?:is|was|are|were)\s+)?(?:elevated|increased|high)\b",
        re.I),
              "Investigations: Hepatic enzymes increased"),
    EventRule(re.compile(r"\bnausea\b", re.I), "Gastrointestinal disorders: Nausea"),
    EventRule(re.compile(r"\bvomiting\b", re.I), "Gastrointestinal disorders: Vomiting"),
    EventRule(re.compile(r"\bheadache\b", re.I), "Nervous system disorders: Headache"),
)
LAB_RULES = (
    ("alt_peak_uln", 3.0, "Investigations: Alanine aminotransferase increased"),
    ("ast_peak_uln", 3.0, "Investigations: Aspartate aminotransferase increased"),
    ("bili_peak_uln", 2.0, "Investigations: Blood bilirubin increased"),
)
_CLAUSES = re.compile(r"[.;!?\n]|\b(?:but|however|although|yet)\b", re.I)
_CONTEXT = re.compile(
    r"\b(?:(?P<negative>no|not(?!\s+only\b)|den(?:y|ies|ied)|without|negative for|"
    r"free of|absence of|rule[ds]? out)|"
    r"(?P<uncertain>possible|suspected|rule out|cannot exclude|family history of)|"
    r"(?P<reset>reports?|developed|experienc(?:es|ed)|complains? of|has))\b", re.I
)
_POST_NEGATION = re.compile(
    r"(?:\s*(?:,|and|or)\s*(?:nausea|vomiting|headache)){0,2}"
    r"\s*(?:(?:is|was|were|are|has been)\s+)?"
    r"(?:absent|denied|ruled out|not present|not ruled out|possible|suspected)\b",
    re.I,
)


def affirmed_terms(text: str) -> list[str]:
    """Match whole terms within clauses; conservatively suppress negated/uncertain mentions."""
    found: dict[str, None] = {}
    for clause in _CLAUSES.split(text):
        cues = list(_CONTEXT.finditer(clause))
        ends = [cue.end() for cue in cues]
        for rule in EVENT_RULES:
            for match in rule.pattern.finditer(clause):
                cue_index = bisect_right(ends, match.start()) - 1
                if cue_index >= 0 and cues[cue_index].lastgroup != "reset":
                    continue
                if _POST_NEGATION.match(clause, match.end()):
                    continue
                found[rule.term] = None
    return list(found)


def validate_labs(labs: object) -> dict[str, float]:
    if not isinstance(labs, dict):
        raise ValueError("labs must be an object of ULN multiples")
    values: dict[str, float] = {}
    for field, _, _ in LAB_RULES:
        if field not in labs:
            continue
        value = labs[field]
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError(f"{field} must be a finite non-negative ULN multiple")
        try:
            number = float(value)
        except (ValueError, OverflowError):
            raise ValueError(f"{field} must be a finite non-negative ULN multiple") from None
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"{field} must be a finite non-negative ULN multiple")
        values[field] = number
    return values


def lab_findings(labs: object) -> list[str]:
    values = validate_labs(labs)
    return [
        f"{term} ({values[field]}x ULN)"
        for field, threshold, term in LAB_RULES
        if field in values and values[field] >= threshold
    ]
