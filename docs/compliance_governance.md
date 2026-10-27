# Security and Regulatory Considerations

## Current scope

This repository is an educational prototype. It is not validated for clinical use and does not establish compliance with HIPAA, FDA 21 CFR Part 11, or any other regulatory requirement. No real patient information should be entered into the demo.

The de-identification helper in `src/agents/utils/deidentifier.py` removes three named fields (`patient_name`, `ssn`, and `phone`), redacts email and phone patterns in `clinical_notes`, and replaces `subject_id` with an in-memory token. Its Fernet key is generated at initialization, and the token mapping exists only in process memory. Other identifier fields, free-text patterns, quasi-identifiers, and re-identification risks are not comprehensively handled.

This example is not a HIPAA de-identification method and should not be used to protect production data. Encryption and tokenization alone do not establish compliance or make data anonymous.

## Controls needed before any regulated use

A real deployment would require a separately designed and validated system, including controls such as:

- A documented privacy threat model and validated de-identification process appropriate to the data and use case.
- Secure key generation, storage, rotation, access controls, and recovery procedures.
- Authentication, authorization, audit trails, data retention rules, and incident response.
- Qualification and validation activities tied to intended use and applicable regulations.
- Human review and approval processes with authenticated electronic signatures, if required.
- A security, privacy, and legal review of any data processors and model providers.

These are considerations for future design, not capabilities implemented in this repository.
