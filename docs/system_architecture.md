# System Architecture

## Responsibility boundaries

`src/runtime.py` validates immutable local settings. `src/agents/state.py`
defines TypedDict contracts for clinical records, events, laboratory data,
workflow state, and partial node updates. `utils/validation.py` performs runtime
validation before execution; invalid records raise errors without echoing values.
Input records are copied, not mutated. Each call starts fresh; supplied drafts,
QC results, and loop counters are never trusted as resumable checkpoints.

`utils/deidentifier.py` owns identifier removal and an invocation-local token
vault. Raw records never enter LangGraph. The graph and native engine receive
only the privacy-gateway output. De-identification is not a guarantee of
anonymity; see [privacy boundaries](compliance_governance.md).

## Shared state machine

```text
validate -> deidentify -> extractor -> writer -> qc_checker
                                        ^           |
                                        | rewrite   |
                                        +-----------+
                                                    |
                                      approve / exhausted
                                                    v
                                                finalize
                                                    |
                                                    v
                                  output (local subject-ID restoration)
```

Both engines invoke the same node wrappers and transition function.
`node_history` records completed boundaries. A node failure logs only its name
and raises `PipelineExecutionError` without exposing underlying exception values;
no partial narrative is released. Validation errors are explicit `ValueError`s.
Compile failures and broken dependency installations propagate, rather than
silently switching engines.

QC approval requires both a score meeting the configured threshold and no
reported errors. A successful last permitted writer pass is approved. Exhaustion
sets `is_approved=False`, `status=review_required`, and a `SYSTEM_HALT` error.
Finalization and output run in both modes. Unknown output tokens fail closed.
Mappings are cleared by context-manager exit even after errors.

`execute()` returns a narrative with restored subject IDs, but `raw_data` and
`coded_terms` remain pseudonymized. This mixed-privacy result must stay local.
Tokens vary across invocations; source-grounded narrative content, QC results,
and transitions do not. No persistent graph checkpoint or cross-call state is
used. One orchestrator may execute concurrent independent calls.

## Clinical utilities

- CSV ingestion uses a strict UTF-8/BOM-aware standard-library reader with
  constant row memory, no numeric or NA coercion, and explicit structural errors.
  Header-only files are allowed; subject filtering requires a subject column
  even when no rows exist. Collecting all matching events is explicitly opt-in.
- Text phenotyping scans precompiled keyword/context rules once per clause.
  Negated, historical, and uncertain contexts suppress findings; explicit
  positive assertions reset suppression. Post-negation conservatively discards
  candidate findings in that clause. Terms retain encounter order and are deduplicated.
- Laboratory rules share finite non-negative numeric validation and inclusive
  thresholds between extraction and QC. Missing labs are not assumed normal.
- Drafting reports supplied demographics and event attributes, marks missing
  data as not reported, and adds no hard-coded trial indication or causality.
  QC checks source-value presence and exact threshold finding text, not general
  clinical truth or unsupported extra statements.

## Local deployment

The default runtime has no LangGraph dependency. Install
`requirements-langgraph.txt` to use the optional graph engine. Ambient LangSmith
tracing is disabled around graph invocation. No callbacks, persistence, remote
models, or network connectors are configured. For an actual air gap, provision
reviewed packages offline and deny network egress at the host/container boundary.

Authentication, authorization, durable audit storage, clinician review,
electronic signatures, full CDISC domain assembly, and clinical terminology
licensing are not implemented.
