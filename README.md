<p align="center">
  <img src="banner.svg" alt="Biotech Agentic System Banner" style="width:100%">
</p>

# AegisCSR

**Local, deterministic clinical safety narrative drafts—without LLM calls.**

![CI](https://github.com/jkelleman/biotech-agentic-system/actions/workflows/tests.yml/badge.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)
![Project status: prototype](https://img.shields.io/badge/status-prototype-informational)

AegisCSR is a local Python prototype that transforms illustrative clinical-trial records into structured safety narrative drafts. Its in-memory workflow uses explicit rules and templates rather than external LLM calls, so the demo does not send records to an external model.

> **In short:** Provide a trial record and get a template-based safety narrative draft from a local, rule-driven pipeline.

## Key capabilities

- **De-identification:** Masks configured identifier fields, email addresses, and phone numbers in clinical text, then replaces the subject ID with a temporary token during processing.
- **Targeted extraction:** Identifies selected adverse-event terms and laboratory anomalies using keyword lists and configured numerical thresholds.
- **Structured drafting:** Builds a narrative draft from the extracted data and a template.
- **Automated quality checks:** Checks for selected omissions and records whether the configured automated QC threshold was met.
- **ID restoration:** Restores the original subject ID to the local output after the draft is assembled.

## Quick start

Requires Python 3.10 or later.

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
python -m pip install -r requirements.txt

# Run the illustrative local workflow
PYTHONPATH=. python src/main.py

# Run the tests
PYTHONPATH=. python -m unittest discover -s tests -v
```

## Architecture

The pipeline processes a record in stages:

```text
Raw record -> Redaction -> ID tokenization -> Targeted extraction
                                               |
                                               v
Output draft <- ID restoration <- Automated QC <- Template drafting
```

<details>
<summary>Execution modes</summary>

The workflow uses LangGraph to coordinate pipeline nodes when LangGraph is installed. Otherwise, it uses a built-in Python loop. Both modes run the same underlying pipeline logic.

</details>

<details>
<summary>What the demo processes</summary>

The illustrative case in `src/main.py` runs through these steps:

1. Redacts selected identifier fields, email addresses, and phone numbers in clinical notes.
2. Replaces the subject ID with a temporary token.
3. Extracts selected adverse-event and laboratory terms using keyword and threshold rules.
4. Drafts a narrative from a template and checks for selected omissions.
5. Restores the original subject ID in the local output.

The demo uses a hard-coded example. It does not load external clinical data or call an LLM.

</details>

## Project status and limitations

<details>
<summary>Read the prototype limitations</summary>

AegisCSR is an experimental local prototype, not a validated or production-ready clinical system. Its deterministic Python rules do not establish clinical accuracy, regulatory compliance, or suitability for submission.

De-identification is limited to the configured example fields and patterns. It does not establish HIPAA compliance or guarantee that a record is de-identified. Do not use real patient information.

The `is_approved` flag indicates only whether the automated QC threshold was met; it is not human approval. MedDRA coding, narrative review, human approval, electronic signatures, and audit logging are not implemented. Business impact, regulatory compliance, and clinical accuracy have not been independently measured.

</details>

## Project structure

<details>
<summary>Browse the repository layout</summary>

```text
config/                  Example workflow configuration
docs/                    Scope, architecture, security, and evaluation notes
src/main.py              Local demonstration entry point
src/agents/              Workflow state, graph, and deterministic nodes
src/agents/utils/        CSV parser and illustrative de-identification helper
tests/                   Unit and workflow tests
requirements.txt         Python runtime dependencies
```

</details>

## Documentation

- [Scenario and intended use](docs/business_scenario.md)
- [System architecture](docs/system_architecture.md)
- [Security and regulatory considerations](docs/compliance_governance.md)
- [Evaluation approach](docs/evaluation_observability.md)

<details>
<summary>30-second introduction</summary>

Compiling clinical-trial safety narratives can require substantial manual effort to review medical reports, identify laboratory changes, and prepare summaries. Generative AI may help automate parts of that work, but clinical workflows also require careful control over source data and review of generated content.

AegisCSR explores a different approach: a local, in-memory pipeline that applies explicit rules to redact selected identifiers, extract configured events and laboratory findings, and assemble a template-based draft. It does not call an external LLM. This prototype demonstrates a transparent workflow for exploration; its output still requires appropriate validation and human review before any clinical or regulatory use.

</details>
