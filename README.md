# AegisCSR

**Deterministic Clinical Safety Narratives—Local Pipeline, Fast, and LLM-Free.**

AegisCSR is a local Python prototype that transforms raw clinical trial records into clean, structured safety narrative drafts. By utilizing a deterministic multi-agent pipeline instead of external LLM calls, this framework keeps data entirely in-memory, deterministic, and under your control.
![CI](https://github.com/jkelleman/biotech-agentic-system/actions/workflows/tests.yml/badge.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)
![Project status: prototype](https://img.shields.io/badge/status-prototype-informational)

> **TL;DR:** Add trial data in. A safety-narrative draft out. Local, deterministic, and LLM-free.

## What It Does

The core pipeline processes a patient record through a highly coordinated, multi-step workflow:

* **Smart Redaction:** Scrubs selected identifier fields, emails, and phone numbers directly from clinical notes.
* **Reversible Tokenization:** Swaps the sensitive subject ID with a temporary token for secure local processing, restoring it only at the final output stage.
* **Targeted Extraction:** Isolates specific adverse events and laboratory anomalies using keyword lists and precise numerical threshold rules.
* **Automated Drafting:** Assembles a template-based safety narrative and performs automatic quality checks to catch missing data elements before completion.

## Architecture & Dual-Execution Engine

This system uses a modular, state-driven design to coordinate tasks. It features a flexible runtime setup:
* **Graph Mode:** Coordinates discrete tasks as agents using a LangGraph workflow.
* **Fallback Mode:** Executes the exact same deterministic pipeline using a standard Python loop if LangGraph isn't installed in the environment.

## Quick Start

Get the prototype running locally in seconds. Requires Python 3.10 or later.

```bash
# Set up a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install requirements
python -m pip install -r requirements.txt

# Run the illustrative demo pipeline
PYTHONPATH=. python src/main.py

# Run the test suite
PYTHONPATH=. python -m unittest discover -s tests -v
```

## 📂 Repository Blueprint

* `src/main.py` - The main entry point running the illustrative workflow.
* `src/agents/` - Deterministic pipeline nodes, execution logic, and state management.
* `src/agents/utils/` - Local CSV parsers and string-matching de-identification engines.
* `config/` - YAML configuration profiles for managing workflow parameters.
* `docs/` - System architecture blueprints, security boundaries, and validation notes.

## What the prototype does

The demo in `src/main.py` runs a hard-coded illustrative case through these steps:

1. Removes selected identifier fields and redacts email addresses and phone numbers in clinical notes.
2. Replaces the subject ID with a temporary token.
3. Extracts a few adverse-event and laboratory terms using simple keyword and threshold rules.
4. Drafts a template-based narrative and checks for selected omissions.
5. Restores the original subject ID in the local output.

The workflow uses LangGraph if it is installed; otherwise, it runs using a built-in Python loop. It does not call an LLM or load external clinical data.

## Project status and limitations

This repository is a local prototype, not a validated or production-ready clinical system. The agents are deterministic Python functions; MedDRA coding, narrative review, human approval, electronic signatures, audit logging, and external model integrations are not implemented. The de-identification example is limited and does not establish HIPAA compliance or guarantee that a record is de-identified. Do not use real patient information.

The workflow's `is_approved` flag records whether its automated QC threshold was met; it does not represent human approval.

Business impact, regulatory compliance, and clinical accuracy have not been independently measured. The included checks are examples, not evidence that generated text is safe or fit for submission.

## Who might find this useful?

If your team is exploring clinical-trial safety workflows, pharmacovigilance, or draft safety-narrative automation, this prototype may offer a small, transparent starting point. That could be relevant to biopharma organizations such as Pfizer, Roche, Novartis, AstraZeneca, Merck, Amgen, Gilead Sciences, Moderna, and Regeneron, as well as clinical research organizations such as IQVIA, ICON, Parexel, Fortrea, and Labcorp.

These are examples of organizations in the broader life-sciences space—not customers, users, or endorsers of this project. The prototype is not validated or suitable for production or clinical use; see [Project status and limitations](#project-status-and-limitations).

## Quick start

Requires Python 3.10 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=. python src/main.py
```

Run the tests:

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
```

## Public sample data

The [SafetyGraphics `safetyData` package](https://github.com/SafetyGraphics/safetyData) provides PHUSE sample CDISC SDTM and ADaM datasets. Its README states that the PHUSE data are available under the MIT license. The subject-level, adverse-event, and laboratory ADaM datasets are relevant starting points for a non-production demonstration. Review the upstream license and attribution requirements before redistributing data.

The dataset is not bundled or connected to this demo. `safetyData` is an R package, while `CDISCChunkParser` currently reads CSV files and expects a `subject_id` column. A small preprocessing step is needed to export the chosen table, rename `USUBJID` to `subject_id`, and map the trial-specific variables into the record shape used by `src/main.py`. The current parser does not combine ADSL, ADAE, and ADLB datasets into a patient record.

For example, export the subject-level dataset from R after installing `safetyData`:

```r
install.packages("safetyData")
adsl <- safetyData::adam_adsl
names(adsl)[names(adsl) == "USUBJID"] <- "subject_id"
write.csv(adsl, "adsl.csv", row.names = FALSE)
```

This export is only a starting point; it does not make the dataset directly usable by the narrative pipeline.

## Repository layout

```text
config/agent_config.yaml        Example workflow configuration
docs/                           Scope, architecture, security, and evaluation notes
src/main.py                     Local demonstration entry point
src/agents/                     Workflow state, graph, and deterministic nodes
src/agents/utils/               CSV parser and illustrative de-identification helper
tests/                           Unit and workflow tests
requirements.txt                Python runtime dependencies
```

## Documentation

- [Scenario and intended use](docs/business_scenario.md)
- [System architecture](docs/system_architecture.md)
- [Security and regulatory considerations](docs/compliance_governance.md)
- [Evaluation approach](docs/evaluation_observability.md)
