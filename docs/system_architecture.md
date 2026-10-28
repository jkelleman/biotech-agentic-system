# System Architecture

## Local execution and responsibility boundaries

```text
run_record(record)
  validate input
  create per-record token vault / recursively redact selected identifiers
  initialize typed state
    extractor -> writer -> qc_checker
                   ^           |
                   |--rewrite--|
                               |
                            finalize
  restore_output (only output_narrative contains the original subject ID)
  close vault on success or failure
```

`src/agents/state.py` defines `ClinicalRecord`, `AdverseEvent`, `WorkflowInput`,
`AgentState`, and partial node-update contracts with runtime input validation.
Every execution starts a fresh state; stale caller-supplied scores, errors,
approval flags, and counters are not trusted as resume/checkpoint data.

`src/agents/graph.py` owns execution and routing. Both engines invoke the same
node wrappers, partial updates, router, and finalizer. Native execution is
available without LangGraph; `auto` selects it only when LangGraph is absent.
Explicit `langgraph` mode requires that dependency. Compilation or execution
failures are not retried through another engine. Node failures raise a sanitized
`PipelineNodeError` without logging input, generated text, or exception payloads.

QC passes only when the score meets the configured threshold and there are no
findings. Approval is evaluated before the revision cap, so a successful final
attempt is approved. Exhaustion produces `review_required`, preserves findings,
and appends a halt reason. `node_history` is a deterministic transition trace,
not a persistent or regulatory audit trail.

`src/agents/nodes/` contains source-grounded extraction, writing, and QC.
Unreported facts remain "Not reported"; no trial phase, diagnosis, treatment,
severity, or causality is invented. Rules and a QC score are not clinical review.

`src/agents/utils/rules.py` owns compiled whole-term rules, conservative
clause-scoped negation/uncertainty suppression, and finite non-negative ULN
validation. Cue offsets are scanned once per clause; term matches use binary
search rather than repeatedly rescanning growing prefixes. Inclusive triggers
are ALT >= 3, AST >= 3, and bilirubin >= 2 times ULN. These are illustrative
findings, not diagnostic criteria or licensed MedDRA coding.

`src/agents/utils/parser.py` streams UTF-8/BOM CSV using the standard library,
preserving strings, quoted newlines, leading-zero identifiers, and empty values.
It rejects empty/duplicate headers, missing subject IDs, ragged rows, and malformed
quoting. `stream_chunks` uses the requested batch size; `iter_subject_records`
keeps memory bounded, whereas `fetch_subject_records` materializes matching rows.
File errors propagate rather than yielding empty success records. Domain joins,
variable mapping, typed clinical-value conversion, and SAS XPT are not implemented.

`src/runtime/config.py` validates immutable settings from `config/runtime.json`.
No model, telemetry, or remote-service configuration is accepted. The optional
graph dependency is isolated in `requirements-langgraph.txt`; native runtime only
needs `cryptography`. Graph invocation disables inherited LangSmith tracing.

## Privacy and output contracts

`run_record` is the supported raw-record entry point. Its vault is scoped to
one invocation, including concurrent executions on the same orchestrator.
Restoration runs after either engine at the identical `restore_output` boundary.
Only `output_narrative` is re-identified; raw state, coded terms, and draft remain
tokenized. The caller must protect returned sensitive output.

The lower-level `execute` API intentionally accepts already-de-identified input
and returns tokenized output. It does not itself enforce the privacy gateway.
No checkpoint database, external clinical connector, model service, clinician
portal, electronic signatures, or persistent audit trail is included.
