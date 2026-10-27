# Evaluation and Observability

## What is evaluated today

The repository includes unit tests for the de-identification example and the workflow. The validator uses deterministic checks for selected fields, adverse-event text, and an ALT mention. Its score is a simple penalty-based value; it is not a clinical quality metric or a calibrated confidence score.

The tests do not establish clinical accuracy, completeness, regulatory compliance, or safety. No LLM evaluation, golden clinical reference set, telemetry backend, or production alerting is configured.

## Suggested evaluation for future development

Before expanding the prototype, define a representative set of permitted sample records and expected outputs. Evaluate at least:

- Whether every stated fact is supported by its source field.
- Whether required events, lab values, dates, and treatment details are included.
- Whether incorrect or missing input fields are surfaced rather than silently omitted.
- Whether revisions improve the draft without introducing unsupported facts.

Keep evaluation data and expected outputs versioned, document their source and usage terms, and require qualified clinical review for any clinical interpretation. Public sample data can support software tests, but should not be treated as evidence of clinical performance.

## Observability

The current application uses Python logging for local execution. It does not send traces or clinical data to LangSmith, Arize Phoenix, or another external service. Any future telemetry integration should be reviewed for privacy, retention, access, and vendor requirements before use.
