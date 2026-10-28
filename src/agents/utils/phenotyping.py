"""Conservative local text rules, not diagnostic or licensed terminology coding."""

import math
import re
from typing import List, Mapping, Optional, Tuple


def lab_value(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("Lab multiples of ULN must be finite non-negative numbers.")
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise ValueError("Lab multiples of ULN must be finite non-negative numbers.") from None
    if not math.isfinite(number) or number < 0:
        raise ValueError("Lab multiples of ULN must be finite non-negative numbers.")
    return number


LAB_RULES: Tuple[Tuple[str, float, str], ...] = (
    ("alt_peak_uln", 3.0, "Alanine aminotransferase increased"),
    ("bili_peak_uln", 2.0, "Blood bilirubin increased"),
)


def laboratory_terms(labs: Mapping[str, object]) -> List[str]:
    terms = []
    for field, threshold, label in LAB_RULES:
        if field in labs:
            value = lab_value(labs[field])
            if value >= threshold:
                terms.append(f"Investigations: {label} ({value:g}x ULN)")
    return terms


_RULES = (
    ("gallbladder", "Gastrointestinal disorders: Gallbladder-related event"),
    ("acute cholecystitis", "Gastrointestinal disorders: Cholecystitis Acute"),
    ("cholecystitis", "Gastrointestinal disorders: Cholecystitis"),
    ("liver", "Hepatobiliary disorders: Liver-related event"),
    ("liver enzymes", "Hepatobiliary disorders: Liver-related event"),
    ("alt", "Investigations: Alanine aminotransferase increased"),
    ("nausea", "Gastrointestinal disorders: Nausea"),
    ("vomiting", "Gastrointestinal disorders: Vomiting"),
    ("headache", "Nervous system disorders: Headache"),
)
_LABELS = dict(_RULES)
_KEYWORD_PATTERN = r"\b(?:" + "|".join(
    re.escape(term) for term in sorted(_LABELS, key=len, reverse=True)
) + r")\b"
_CLAUSES = re.compile(r"[.!?;\n]+|\b(?:but|however|although|yet)\b", re.IGNORECASE)
_PRE_NEGATION = re.compile(
    r"\b(?:no(?!\s+(?:change|increase|decrease)\b)|not(?!\s+only\b)|denies|denied|"
    r"without|negative\s+for|absence\s+of|free\s+of|rules?\s+out|ruled\s+out)\b",
    re.IGNORECASE,
)
_ANY_POST_NEGATION = re.compile(
    r"\b(?:absent|denied|not\s+(?:present|reported|observed)|ruled\s+out)\b",
    re.IGNORECASE,
)
_UNCERTAIN = re.compile(
    r"\b(?:history\s+of|family\s+history|possible|possibly|suspected|"
    r"monitor\s+for|risk\s+of|if|rule\s+out)\b", re.IGNORECASE
)
_AFFIRMATION = re.compile(
    r"\b(?:reports?|reported|developed|experiences?|experienced|complains?\s+of)\b",
    re.IGNORECASE,
)
_SCANNER = re.compile(
    "(?P<postnegation>" + _ANY_POST_NEGATION.pattern + ")|"
    "(?P<negation>" + _PRE_NEGATION.pattern + ")|"
    "(?P<uncertain>" + _UNCERTAIN.pattern + ")|"
    "(?P<affirmation>" + _AFFIRMATION.pattern + ")|"
    "(?P<term>" + _KEYWORD_PATTERN + ")",
    re.IGNORECASE,
)
_ABNORMAL = re.compile(r"\b(?:increased|elevated|high|abnormal|raised)\b", re.IGNORECASE)


def clinical_terms(text: str) -> List[str]:
    terms: List[str] = []
    seen = set()
    for clause in _CLAUSES.split(text):
        suppressed = False
        abnormal = _ABNORMAL.search(clause) is not None
        candidates = {}
        for match in _SCANNER.finditer(clause):
            if match.lastgroup != "term":
                if match.lastgroup == "postnegation":
                    candidates.clear()
                suppressed = match.lastgroup != "affirmation"
                continue
            if match.group().lower() == "alt" and not abnormal:
                continue
            label = _LABELS[match.group().lower()]
            if not suppressed:
                candidates[label] = None
        for label in candidates:
            if label not in seen:
                terms.append(label)
                seen.add(label)
    return terms


def event_term(description: str) -> Optional[str]:
    terms = clinical_terms(description)
    if terms:
        return terms[0]
    if _PRE_NEGATION.search(description) or _UNCERTAIN.search(description) or _ANY_POST_NEGATION.search(description):
        return None
    return f"General disorders: {description}"
