# Evaluation and Observability

## What is evaluated today

The repository includes `unittest` cases for nested identifier redaction, supported email/phone formats, exact token restoration, vault lifecycle and concurrency, CSV structure and identifier preservation, negation handling, and inclusive ALT/AST/bilirubin thresholds. Workflow cases exercise equivalent native/LangGraph states and histories, successful final revisions, exhausted revisions, sanitized node failures, invalid updates, per-record isolation, and disabled inherited tracing. CI runs both dependency profiles.

The validator checks selected source fields, reported event descriptions, extracted findings, and exact abnormal-laboratory findings including their numerical values. Its score is a simple penalty-based value, not a clinical quality metric or calibrated confidence score. Unresolved findings block approval even if the configured score threshold is met. Approval remains automated structural QC only.

The tests do not establish clinical accuracy, completeness, regulatory compliance, or safety. No LLM evaluation, golden clinical reference set, telemetry backend, or production alerting is configured.

## Reproducible synthetic performance evaluation

`src/utils/mock_generator.py` streams fictional records with independent expected
findings. Count, seed, and note repetition count are configurable; large workloads
do not need to be held in memory. Private seeded RNG state makes fixtures repeatable
without weakening cryptographic token randomness or modifying global randomness.
Phone styles, contact values, nested identifiers, event descriptions, negations,
and lab boundaries are deliberately varied. These are engineering fixtures, not
realistic prevalence estimates or a validated clinical reference corpus.

Run `python -m tests.benchmark --records 2000 --repeats 3 --note-repetitions 4`.
The default comparison requires the optional LangGraph requirements; `--engine
native` works with base dependencies. Each engine runs in a fresh worker
interpreter, excluding import/compilation and equal warm-up from measurements.
Mean, median, nearest-rank P95 latency, throughput, and percentage deltas are
printed without record contents. Generation, assertions, and tracemalloc are
excluded from per-record latency. Throughput is total measured invocations
divided by their cumulative execution time, not end-to-end file-ingestion throughput.

A separate unretained streaming pass records peak `tracemalloc` Python allocations,
including fixture generation. This does not capture total RSS or native-library
allocations; use platform-level profiling separately when sizing deployments.
The benchmark does not retain result states. Latency samples scale with the
requested timing workload and are freed before memory measurement.

Every timed record must satisfy the independent clinical oracle, redaction and
restoration checks, and exact transition history. Complete states are normalized
only for random subject tokens, then hashed with length framing; both engines must
produce the same digest and sample count. Positive, internally consistent metrics
are required, including under `python -O`. Optional `--max-latency-ratio`,
`--max-memory-ratio`, and `--min-throughput-rps` budgets produce a nonzero exit
after printing the summary when unmet. No machine-dependent thresholds are imposed
by default. CI runs small correctness/measurement smoke workloads; run thousands
of records on representative hardware for actual capacity decisions.

## Suggested evaluation for future development

Before expanding the prototype, define a representative set of permitted sample records and expected outputs. Evaluate at least:

- Whether every stated fact is supported by its source field.
- Whether required events, lab values, dates, and treatment details are included.
- Whether incorrect or missing input fields are surfaced rather than silently omitted.
- Whether revisions improve the draft without introducing unsupported facts.

Keep evaluation data and expected outputs versioned, document their source and usage terms, and require qualified clinical review for any clinical interpretation. Public sample data can support software tests, but should not be treated as evidence of clinical performance.

## Observability

The current application uses Python logging for local execution. It does not send traces or clinical data to LangSmith, Arize Phoenix, or another external service. Any future telemetry integration should be reviewed for privacy, retention, access, and vendor requirements before use.
