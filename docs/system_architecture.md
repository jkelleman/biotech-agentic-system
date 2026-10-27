# System Architecture

## Implemented workflow

The local demo in `src/main.py` constructs one example record and passes it through a small set of deterministic functions:

```text
Example record
    |
    v
ClinicalDeidentifier
    |
    v
extract_and_code_data
    |
    v
write_medical_narrative
    |
    v
quality_control_check
    |
    v
Local output with subject ID restored
```

`AegisStateGraphOrchestrator` in `src/agents/graph.py` uses LangGraph when available and otherwise runs the same nodes in a native Python loop. A failed quality check routes back to the writer, up to the configured loop limit in code. The current workflow does not pause for a human reviewer.

## Implemented components

- **State:** `AgentState` holds the input record, coded terms, draft, score, loop count, errors, and approval flag.
- **Extraction:** `extract_and_code_data` uses simple keyword matching and numeric thresholds. It does not perform MedDRA lookup or general-purpose clinical coding.
- **Writing:** `write_medical_narrative` assembles a fixed template from the fields present in the record.
- **Validation:** `quality_control_check` checks selected text and input values. It is not a comprehensive fact-checking or compliance engine.
- **De-identification:** `ClinicalDeidentifier` provides limited in-memory tokenization and regex redaction for the demonstration fields.
- **CSV parsing:** `CDISCChunkParser` reads CSV files in chunks. It does not read SAS XPT files or assemble multiple CDISC domains into the `AgentState` schema.

## Not implemented

The repository does not include an LLM client, production checkpoint database, external clinical-data connector, MedDRA license or terminology service, clinician portal, electronic signatures, or persistent audit trail. The configuration file lists example settings; it does not provision these services.

These boundaries should be kept explicit if the prototype is extended. A production architecture would need separate requirements, threat modeling, validation, and operational controls.
