# Security and Regulatory Considerations

## Implemented privacy boundary

This repository is not validated for clinical use and does not establish HIPAA,
FDA 21 CFR Part 11, or other regulatory compliance. Use fictional records only.

`ClinicalDeidentifier` recursively removes configured identifier fields,
including common names, contacts, addresses, birth dates, and record numbers.
Selected values and supplied name components are removed from string values
throughout nested dictionaries and lists. Common email, North American phone,
international E.164/grouped phone, and formatted SSN patterns are redacted even
when no corresponding structured field exists. Numeric ages above 89 are grouped
as `90+`. Field names are case/camel-case normalized for selection; `USUBJID`
is recognized as a subject identifier by the privacy gateway. The pipeline
clinical schema still requires a canonical `subject_id`.

This is Safe Harbor-inspired **risk reduction, not complete Safe Harbor
de-identification**. It cannot reliably identify all unknown names, geographical
details, dates in arbitrary prose, nonstandard identifiers, unsupported telephone
formats, or identifying combinations. Dictionary keys other than selected field
names are not scrubbed and must be schema labels, never patient data. Clinical
free text requires a separately validated privacy process.

## Token lifecycle

Subject IDs receive cryptographically random 128-bit opaque tokens. An RLock
protects assignment, redaction, restoration, and cleanup. Forward lookup uses
HMAC-SHA256 with a session-specific secret; reverse mapping stores Fernet-encrypted
originals. The key and maps never leave process memory. Original identifiers are
not dictionary lookup keys. Token ownership is session-local, and unknown tokens
raise an error instead of being silently retained.

Restoration matches complete tokens once, so replacements cannot recursively
restore or partially replace other identifiers. Only subject IDs are reversible;
removed names and contact details are never restored. Each pipeline invocation
owns a separate vault, which is cleared on success or exception. Python cannot
guarantee physical zeroization of immutable strings, garbage-collected copies,
swap, or crash dumps. Protect the host and memory accordingly.

The output node deliberately restores subject IDs in the narrative. That output
is identifiable and must go only to a trusted local destination. The demo prints
its fictional final narrative to stdout. Do not redirect real identifiable
output to shared logs, external telemetry, or ungoverned storage.

## Offline operation and failures

There are no model API calls or external data fetches. LangGraph invocation
disables ambient tracing and does not configure callbacks or checkpoint storage.
Node errors expose only a node name, not patient content or original exception
messages. The pipeline does not log subject identifiers or coded findings.
Failed execution never silently falls back or releases a partial result.

These application controls do not replace network isolation. A production
deployment must enforce egress denial, trusted dependency provisioning, process
isolation, access control, secure stdout handling, and safe host logging policies.

## Remaining regulated-use requirements

Before any real clinical use, independently design and validate the privacy
process, intended-use clinical rules, key lifecycle, authentication and
authorization, audit trails, retention, incident response, and human approval.
Obtain qualified clinical, security, privacy, and legal review. Encryption and
tokenization alone do not make a record anonymous or establish compliance.
