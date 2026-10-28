"""Local, scoped pseudonymization and selected-identifier redaction.

This is not a complete HIPAA Safe Harbor implementation. Python cannot guarantee
memory zeroization; process isolation and governed input schemas remain necessary.
"""

import hashlib
import hmac
import re
import secrets
from threading import RLock
from typing import Any

from cryptography.fernet import Fernet

from src.agents.state import ClinicalRecord

_EMAIL = re.compile(r"(?<![\w.+-])[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+", re.I)
_PHONE = re.compile(
    r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?"
    r"\d{3}[\s.-]?\d{4}(?:\s*(?:ext\.?|x|extension)\s*\d{1,6})?(?!\w)",
    re.I,
)
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_TOKEN = re.compile(r"(?<![\w-])SUBJ-ANON-[0-9a-f]{32}(?![\w-])")
_AGE = re.compile(r"\b(?:9\d|1[01]\d|12\d|130)[ -]*(?:years?[- ]old|y/?o)\b", re.I)

DEFAULT_IDENTIFIER_FIELDS = frozenset({
    "patient_name", "name", "first_name", "last_name", "full_name",
    "ssn", "social_security_number", "phone", "phone_number", "telephone",
    "mobile", "fax", "email", "email_address", "address", "street_address",
    "city", "county", "zip", "zip_code", "postal_code", "date_of_birth", "dob",
    "birth_date", "medical_record_number", "mrn", "account_number",
    "health_plan_number", "beneficiary_number", "license_number",
    "device_identifier", "vehicle_identifier", "ip_address", "url",
})


def _field_name(value: str) -> str:
    return re.sub(r"[\s-]+", "_", value.strip().lower())


class ClinicalDeidentifier:
    """Thread-safe in-memory vault. Prefer one context-managed instance per record."""

    def __init__(self, identifier_fields: frozenset[str] = DEFAULT_IDENTIFIER_FIELDS):
        if any(not isinstance(field, str) or not field.strip() for field in identifier_fields):
            raise ValueError("Identifier fields must be non-empty strings")
        self.identifier_fields = frozenset(_field_name(field) for field in identifier_fields)
        if "subject_id" in self.identifier_fields:
            raise ValueError("subject_id must be tokenized, not removed")
        self._lock = RLock()
        self._cipher: Fernet | None = Fernet(Fernet.generate_key())
        self._lookup_key = secrets.token_bytes(32)
        self._token_registry: dict[bytes, str] = {}
        self._reverse_registry: dict[str, bytes] = {}

    def __enter__(self) -> "ClinicalDeidentifier":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            self._token_registry.clear()
            self._reverse_registry.clear()
            self._lookup_key = b""
            self._cipher = None

    def _require_cipher(self) -> Fernet:
        if self._cipher is None:
            raise RuntimeError("Token vault is closed")
        return self._cipher

    def anonymize_patient_record(self, raw_record: ClinicalRecord) -> ClinicalRecord:
        if not isinstance(raw_record, dict):
            raise ValueError("Clinical record must be an object")
        raw_id = raw_record.get("subject_id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ValueError("subject_id must be a non-empty string")
        with self._lock:
            cipher = self._require_cipher()
            identifiers: set[str] = set()

            def collect(value: Any, selected: bool = False, name: bool = False) -> None:
                if isinstance(value, dict):
                    for key, child in value.items():
                        if not isinstance(key, str):
                            raise ValueError("Clinical record keys must be strings")
                        field = _field_name(key)
                        if field == "subject_id" and child != raw_id:
                            raise ValueError("Conflicting subject identifiers in one record")
                        collect(child, selected or field in self.identifier_fields,
                                name or field in {"patient_name", "full_name", "name"})
                elif isinstance(value, list):
                    for child in value:
                        collect(child, selected, name)
                elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
                    text = str(value).strip()
                    if "SUBJ-ANON-" in text:
                        raise ValueError("Input contains a reserved subject token marker")
                    if selected and text:
                        identifiers.add(text)
                        if name:
                            identifiers.update(part for part in text.split() if len(part) >= 2)
                elif value is not None and not isinstance(value, bool):
                    raise ValueError("Clinical records must contain JSON-compatible values")

            collect(raw_record)
            # One compiled matcher per record, longest-first to avoid partial substitutions.
            selected_values = "|".join(
                re.escape(value).replace(r"\ ", r"\s+")
                for value in sorted(identifiers, key=lambda x: (-len(x), x))
            )
            selected_branch = (
                r"|(?P<identifier>(?<!\w)(?:" + selected_values + r")(?!\w))"
                if identifiers else ""
            )
            # One substitution prevents tokenizing an ID embedded in a longer selected value.
            value_pattern = re.compile(
                r"(?P<email>" + _EMAIL.pattern + r")|"
                r"(?P<phone>" + _PHONE.pattern + r")|"
                r"(?P<ssn>" + _SSN.pattern + r")|"
                r"(?P<subject>(?<![\w-])(?-i:" + re.escape(raw_id) + r")(?![\w-]))"
                + selected_branch, re.I,
            )
            digest = hmac.new(self._lookup_key, raw_id.encode(), hashlib.sha256).digest()
            token = self._token_registry.get(digest)
            if token is None:
                token = "SUBJ-ANON-" + secrets.token_hex(16)
                while token in self._reverse_registry:
                    token = "SUBJ-ANON-" + secrets.token_hex(16)
                self._token_registry[digest] = token
                self._reverse_registry[token] = cipher.encrypt(raw_id.encode())

            def scrub_text(text: str) -> str:
                def replace_value(match: re.Match[str]) -> str:
                    value = match.group()
                    if value == raw_id:
                        return token
                    if match.lastgroup == "email":
                        return "[REDACTED_EMAIL]"
                    if match.lastgroup == "phone":
                        return "[REDACTED_PHONE]"
                    if match.lastgroup == "ssn":
                        return "[REDACTED_SSN]"
                    return "[REDACTED_IDENTIFIER]"

                text = value_pattern.sub(replace_value, text)
                # Preserve generated tokens from broad numeric/selected-value matches.
                def scrub_fragment(fragment: str) -> str:
                    return _AGE.sub("90+ years old", fragment)

                parts = re.split(f"({_TOKEN.pattern})", text)
                return "".join(part if _TOKEN.fullmatch(part) else scrub_fragment(part) for part in parts)

            def scrub(value: Any) -> Any:
                if isinstance(value, dict):
                    return {
                        key: (token if _field_name(key) == "subject_id" and child == raw_id
                              else "90+" if _field_name(key) == "age" and type(child) is int and child > 89
                              else scrub(child))
                        for key, child in value.items()
                        if _field_name(key) not in self.identifier_fields
                    }
                if isinstance(value, list):
                    return [scrub(child) for child in value]
                return scrub_text(value) if isinstance(value, str) else value

            return scrub(raw_record)

    def reidentify_narrative(self, output_text: str) -> str:
        """One-pass exact-token restoration; unknown or malformed tokens fail closed."""
        if not isinstance(output_text, str):
            raise ValueError("Narrative must be a string")
        with self._lock:
            cipher = self._require_cipher()
            if "SUBJ-ANON-" in _TOKEN.sub("", output_text):
                raise ValueError("Malformed subject token in output")

            def restore(match: re.Match[str]) -> str:
                encrypted = self._reverse_registry.get(match.group())
                if encrypted is None:
                    raise ValueError("Unknown subject token in output")
                return cipher.decrypt(encrypted).decode()

            return _TOKEN.sub(restore, output_text)
