# Evaluation and Observability

## Automated software checks

Run `python -m unittest discover -s tests -v`. CI covers Python 3.10-3.12 with
both the minimal runtime and optional LangGraph dependencies. LangGraph-specific
tests explicitly skip when it is absent; native tests always run.

The suite covers recursive identifier redaction, common contact formats, Unicode
case variants, non-mutation, random token ownership, concurrent assignment,
whole-token/non-recursive restoration, foreign-token rejection, and vault cleanup.
CSV cases cover leading zeros, literal NA, missing values, multiline quoted
notes, invalid encoding, missing files/columns, malformed rows, and lazy errors.

Phenotyping checks include exact inclusive threshold boundaries, invalid and
non-finite lab values, whole-word matching, negation, post-negated lists,
uncertainty/history, positive contrast clauses, and order-preserving
deduplication. No drug-induced liver injury diagnosis is inferred.

Both engines run the same success, remediation, exhaustion, concurrency,
last-pass approval, input validation, failure sanitization, and no-network
scenarios. Parity tests use a fixed token generator only inside tests to compare
complete returned state exactly. Production tokens remain random. Socket
connection attempts are rejected in the offline test even with ambient tracing
enabled.

## Reproducible synthetic performance evaluation

`src/utils/mock_generator.py` streams fictional records with independent expected
findings. Count, seed, and note repetition are configurable; fixtures vary contact
formats, nested identifiers, event descriptions, negations, and laboratory
boundaries. These engineering fixtures are not a validated clinical reference
corpus.

Run `python -m tests.benchmark --records 2000 --repeats 3 --note-repetitions 4`.
The default comparison requires the optional LangGraph dependencies;
`--engine native` works with base dependencies. Each engine runs in a fresh worker
interpreter after equal warm-up. The report includes latency, throughput, memory
allocation, and parity metrics without record contents. CI runs a small benchmark
smoke check; use representative hardware and workloads for capacity decisions.

The benchmark validates records against an independent clinical oracle and
compares complete results after normalizing only random subject tokens. Reported
Python allocation peaks do not include total RSS or native-library allocations.

## Limits

QC scores are penalty-based software checks, not clinical quality or compliance
metrics. Presence checks cannot detect every unsupported claim, contextual
mismatch, or clinical omission. Conservative clause-level negation can miss
positive findings in ambiguous lists and complex prose. Tests are not evidence
of privacy completeness, clinical performance, or fitness for submission.

Before clinical use, establish governed reference datasets, privacy recall and
precision targets, clinical review, negative controls, and intended-use-specific
acceptance criteria. Benchmark throughput and memory against representative
record and note sizes on the actual deployment hardware.

## Local observability

Returned state includes node history, revision count, status, score, and
value-free QC error categories. Failed nodes log only their boundary name.
No patient identifiers, clinical terms, or exception payloads are logged by
pipeline nodes. The demo's explicitly identifiable fictional narrative goes to
stdout, not an external service. No persistent audit trail, production alerting,
or telemetry backend is implemented.
