# Security and Regulatory Considerations

## Scope and limitations

This is a hardened local reference implementation, not a clinically validated
system or evidence of HIPAA, FDA 21 CFR Part 11, or other regulatory compliance.
Use fictional or appropriately governed demonstration data only.

The privacy gateway removes the configured identifier fields recursively from
JSON-shaped records and redacts their known values in all retained text, including
event descriptions. Default fields cover names, contact details, DOB, addresses,
SSN, and several account/record/device identifiers; field-name matching ignores
case and normalizes spaces/hyphens. Full-name components are also redacted.
Generic email, supported phone/extension, and hyphenated SSN patterns are scrubbed.
Ages above 89 are grouped as `90+` in age fields and supported narrative phrases.

This is **not complete HIPAA Safe Harbor de-identification**. Arbitrary dates,
all geographic information, photographs, biometrics, arbitrary identifier-bearing
dictionary keys, name variants, unsupported international phone formats, and
contextual identity are not comprehensively detected. Unknown schema aliases and
clinical language require validated, dataset-specific controls. Selected-value
matching can also over-redact clinically relevant text. Negation rules are
conservative heuristics, not a clinically validated language model.

## Token vault and lifecycle

Subject tokens use 128 bits of cryptographic randomness, not sequential counters.
An instance-scoped HMAC lookup avoids storing plaintext subject IDs as map keys;
reverse mappings contain Fernet ciphertext. A reentrant lock protects assignment,
lookup, restoration, and closure. Repeated subjects in a shared vault reuse a token;
separate record invocations deliberately use unrelated tokens.

Only exact, complete tokens are restored in a single substitution pass. Unknown
or malformed tokens and input containing the reserved token marker are rejected.
Restoration never restores removed names, emails, or other identifiers. Conflicting
nested subject IDs are rejected rather than leaking another subject's identifier.
The per-record vault is closed in a context manager even when a node fails.

Closing drops mappings and key references. Python does not guarantee memory
zeroization; ciphertext and ephemeral keys in the same process do not protect
against a process-memory compromise. Raw input and authorized output necessarily
contain identifiers and remain the caller's responsibility.

## Local operation

No external LLM APIs, callbacks, checkpoints, or network connectors are configured.
Optional LangGraph execution explicitly disables inherited LangSmith tracing.
Logs contain generic stage/failure information, not record contents or exception
payloads. Node histories are in-memory traces only. Govern host logging, process
isolation, core dumps, swap, telemetry, and access to sensitive output separately;
use network-denial controls for an air-gapped deployment.

## Controls still needed for regulated use

- Validated privacy threat model, schema, redaction performance, and risk assessment.
- Authentication, authorization, retention, recovery, and incident-response controls.
- Qualified clinical review, terminology licensing, and intended-use validation.
- Persistent, tamper-evident audit trails and authenticated electronic signatures.
- Governed dependency artifacts, deployment hardening, monitoring, and change control.

These are deployment requirements, not implemented product guarantees.
