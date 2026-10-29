"""Local pseudonymization gateway with explicit, short-lived token ownership."""

import hashlib
import hmac
import re
import secrets
from threading import RLock
from typing import Any, Dict, Iterable, Optional

from cryptography.fernet import Fernet


_EMAIL = re.compile(r"(?<![\w.+-])[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE)
_PHONE = re.compile(
    r"(?<!\w)(?:(?:\+\d{1,3}[\s.-]*)?"
    r"(?:\(\d{3}\)|\d{3})[\s.-]*\d{3}[\s.-]*\d{4}"
    r"|\+[1-9]\d{7,14}"
    r"|\+\d{1,3}[\s.-]+\d{1,4}[\s.-]+\d{3,4}[\s.-]+\d{3,4})"
    r"(?:\s*(?:ext\.?|x|extension)\s*\d{1,6})?(?!\w)",
    re.IGNORECASE,
)
_SSN = re.compile(r"(?<!\d)\d{3}[- ]\d{2}[- ]\d{4}(?!\d)")
_TOKEN = re.compile(r"(?<![\w-])SUBJ-ANON-[A-Za-z0-9-]+(?![\w-])")
_NAME_FIELDS = frozenset({"patient_name", "name", "first_name", "last_name", "full_name"})
DEFAULT_IDENTIFIER_FIELDS = frozenset({
    *_NAME_FIELDS, "ssn", "social_security_number", "phone", "phone_number",
    "telephone", "mobile", "fax", "email", "email_address", "address",
    "street_address", "city", "county", "zip", "zip_code", "postal_code",
    "dob", "date_of_birth", "birth_date", "medical_record_number", "mrn",
    "health_plan_number", "account_number", "certificate_number", "license_number",
    "vehicle_id", "device_id", "url", "ip_address", "biometric_id", "photo",
})


def _field(key: str) -> str:
    key = re.sub(r"([a-z])([A-Z])", r"\1_\2", key.strip())
    normalized = re.sub(r"[\s-]+", "_", key.lower())
    return "subject_id" if normalized == "usubjid" else normalized


class ClinicalDeidentifier:
    """Selected-field redaction, not a validated HIPAA Safe Harbor implementation.

    Own one instance per workflow/session. Only subject IDs are reversible.
    Mappings are keyed by keyed digests, with encrypted originals, under a lock.
    """

    def __init__(self, identifier_fields: Iterable[str] = ()) -> None:
        self._fields = DEFAULT_IDENTIFIER_FIELDS | frozenset(_field(k) for k in identifier_fields)
        if "subject_id" in self._fields:
            raise ValueError("subject_id must be tokenized, not selected for removal.")
        self._lock = RLock()
        self._cipher: Optional[Fernet] = Fernet(Fernet.generate_key())
        self._digest_key = secrets.token_bytes(32)
        self._token_registry: Dict[bytes, str] = {}
        self._reverse_registry: Dict[str, bytes] = {}
        self._closed = False

    def __enter__(self) -> "ClinicalDeidentifier":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _ensure_open(self) -> Fernet:
        if self._closed or self._cipher is None:
            raise RuntimeError("De-identification session is closed.")
        return self._cipher

    def close(self) -> None:
        with self._lock:
            self._token_registry.clear()
            self._reverse_registry.clear()
            self._digest_key = b""
            self._cipher = None
            self._closed = True

    def _tokenize(self, value: str) -> str:
        cipher = self._ensure_open()
        digest = hmac.digest(self._digest_key, value.encode("utf-8"), hashlib.sha256)
        if digest not in self._token_registry:
            token = "SUBJ-ANON-" + secrets.token_hex(16)
            while token in self._reverse_registry:
                token = "SUBJ-ANON-" + secrets.token_hex(16)
            self._token_registry[digest] = token
            self._reverse_registry[token] = cipher.encrypt(value.encode("utf-8"))
        return self._token_registry[digest]

    def anonymize_patient_record(self, raw_record: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(raw_record, dict):
            raise ValueError("Clinical record must be an object.")
        with self._lock:
            self._ensure_open()
            literals = set()
            subjects: Dict[str, str] = {}

            def collect(value: Any, selected: bool = False, name: bool = False) -> None:
                if isinstance(value, dict):
                    for key, item in value.items():
                        if not isinstance(key, str):
                            raise ValueError("Clinical record field names must be strings.")
                        field = _field(key)
                        if field == "subject_id":
                            if not isinstance(item, str) or not item.strip():
                                raise ValueError("subject_id must be a non-empty string.")
                            subjects[item] = self._tokenize(item)
                        else:
                            collect(item, selected or field in self._fields, name or field in _NAME_FIELDS)
                elif isinstance(value, list):
                    for item in value:
                        collect(item, selected, name)
                elif isinstance(value, (str, int, float, bool)) or value is None:
                    if selected and value is not None and str(value).strip():
                        text = str(value).strip()
                        literals.update((text, text.casefold()))
                        if name:
                            for part in re.findall(r"[^\W\d_]+(?:['-][^\W\d_]+)*", text):
                                literals.update((part, part.casefold()))
                else:
                    raise ValueError("Clinical record must contain only JSON-compatible values.")

            collect(raw_record)
            subject_pattern = (
                re.compile(r"(?<!\w)(?:" + "|".join(re.escape(s) for s in sorted(subjects, key=len, reverse=True)) + r")(?!\w)")
                if subjects else None
            )
            # Tokens are protected from subsequent literal redaction.
            literal_pattern = (
                re.compile(
                    r"SUBJ-ANON-[a-f0-9]{32}|(?<!\w)(?:"
                    + "|".join(re.escape(s) for s in sorted(literals, key=len, reverse=True))
                    + r")(?!\w)", re.IGNORECASE
                ) if literals else None
            )

            def scrub(text: str) -> str:
                if subject_pattern:
                    text = subject_pattern.sub(lambda m: subjects[m.group()], text)
                text = _EMAIL.sub("[REDACTED_EMAIL]", text)
                text = _PHONE.sub("[REDACTED_PHONE]", text)
                text = _SSN.sub("[REDACTED_SSN]", text)
                if literal_pattern:
                    text = literal_pattern.sub(
                        lambda m: m.group() if m.group() in self._reverse_registry
                        else "[REDACTED_IDENTIFIER]",
                        text,
                    )
                return text

            def clean(value: Any) -> Any:
                if isinstance(value, dict):
                    result = {}
                    for key, item in value.items():
                        field = _field(key)
                        if field in self._fields:
                            continue
                        if field == "subject_id":
                            result[key] = subjects[item]
                        elif field == "age" and type(item) is int and item > 89:
                            result[key] = "90+"
                        else:
                            result[key] = clean(item)
                    return result
                if isinstance(value, list):
                    return [clean(item) for item in value]
                return scrub(value) if isinstance(value, str) else value

            return clean(raw_record)

    def reidentify_narrative(self, text: str) -> str:
        """Restore whole tokens exactly once; reject foreign/session-expired tokens."""
        with self._lock:
            cipher = self._ensure_open()
            tokens = set(_TOKEN.findall(text))
            if tokens - self._reverse_registry.keys():
                raise ValueError("Narrative contains an unknown subject token.")
            originals = {
                token: cipher.decrypt(self._reverse_registry[token]).decode("utf-8")
                for token in tokens
            }
            return _TOKEN.sub(lambda match: originals[match.group()], text)
