<p align="center">
  <img src="banner.svg" alt="Biotech Agentic System Banner" style="width:100%">
</p>

# AegisCSR

**Deterministic Clinical Safety Narratives—Local Pipeline, Fast, and LLM-Free.**

AegisCSR is a local Python prototype that transforms raw clinical trial records into clean, structured safety narrative drafts. By utilizing a deterministic multi-agent pipeline instead of external LLM calls, this framework keeps data entirely in-memory, deterministic, and under your control.
![CI](https://github.com/jkelleman/biotech-agentic-system/actions/workflows/tests.yml/badge.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)
![Project status: prototype](https://img.shields.io/badge/status-prototype-informational)

> **TL;DR:** Add trial data in. A safety-narrative draft out. Local, deterministic, and LLM-free.

## What It Does

The core pipeline processes a patient record through a highly coordinated, multi-step workflow:

* **Selected-Identifier Redaction:** Removes configured identifier fields recursively and scrubs their known values, emails, and supported phone/SSN formats from text.
* **Reversible Tokenization:** Swaps the sensitive subject ID with a temporary token for secure local processing, restoring it only at the final output stage.
* **Targeted Extraction:** Applies whole-term, negation-aware note rules and validated ALT, AST, and bilirubin thresholds.
* **Automated Drafting:** Assembles a template-based safety narrative and performs automatic quality checks to catch missing data elements before completion.

## Architecture & Dual-Execution Engine

This system uses a modular, state-driven design to coordinate tasks. It features a flexible runtime setup:
* **Graph Mode:** Coordinates discrete tasks as agents using a LangGraph workflow.
* **Fallback Mode:** Executes the exact same deterministic pipeline using a standard Python loop if LangGraph isn't installed in the environment.

Both engines use the same validated state, node wrappers, router, revision limit, and terminal finalizer. Execution errors fail explicitly; an installed but broken graph never silently falls back or replays a record. Automatic QC approval requires both a passing score and no unresolved findings.

## Quick Start

Get the prototype running locally in seconds. Requires Python 3.10 or later.

```bash
# Set up a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install requirements
python -m pip install -r requirements.txt

# Optional graph execution (not required for the native engine)
python -m pip install -r requirements-langgraph.txt

# Run the illustrative demo pipeline
PYTHONPATH=. python src/main.py

# Run the test suite
PYTHONPATH=. python -m unittest discover -s tests -v
```

## Repository Blueprint

* `src/main.py` - The main entry point running the illustrative workflow.
* `src/agents/` - Deterministic pipeline nodes, execution logic, and state management.
* `src/agents/utils/` - Local CSV parsers and string-matching de-identification engines.
* `src/runtime/` - Validated local runtime settings, loaded by the demo from `config/runtime.json`.
* `docs/` - System architecture blueprints, security boundaries, and validation notes.

## What the prototype does

The demo in `src/main.py` runs a hard-coded illustrative case through these steps:

1. Removes selected identifier fields and redacts email addresses and phone numbers in clinical notes.
2. Replaces the subject ID with a temporary token.
3. Extracts a few adverse-event and laboratory terms using simple keyword and threshold rules.
4. Drafts a template-based narrative and checks for selected omissions.
5. Restores the original subject ID in the local output.

The workflow uses LangGraph if it is installed; otherwise, it runs using a built-in Python loop. It does not call an LLM or load external clinical data.

For application integration, use the per-record privacy gateway:

```python
from src.agents.graph import AegisStateGraphOrchestrator
from src.runtime.config import RuntimeConfig

pipeline = AegisStateGraphOrchestrator(RuntimeConfig(engine="native"))
result = pipeline.run_record({
    "subject_id": "DEMO-001",
    "clinical_notes": "Patient denies nausea but reports vomiting.",
    "labs": {"alt_peak_uln": "3.0"},
})
authorized_local_output = result["output_narrative"]
```

`output_narrative` contains the restored subject ID and is sensitive. The draft and record in the returned state remain tokenized. The lower-level `execute({"raw_data": ...})` API requires caller-de-identified input and never restores identifiers. Each `run_record` call owns a fresh in-memory vault, cleared on success or failure; random tokens intentionally differ across runs, while clinical decisions and transitions remain deterministic.

The CSV parser streams string-valued rows, preserving leading-zero IDs and missing values. Malformed files and missing required headers fail explicitly; CSV ingestion does not infer a clinical record or join domains.

For air-gapped deployment, pre-stage approved dependency wheels and install with `pip --no-index --find-links=/approved/wheels -r requirements.txt` (or the optional graph requirements). No network connection is needed at runtime. LangSmith tracing is explicitly disabled during graph execution, including inherited tracing settings. Keep sensitive output out of logging, tracing, and external middleware.

## Synthetic clinical workloads and benchmarks

`src/utils/mock_generator.py` provides lazy, seeded synthetic records and independent clinical ground truth. Fixtures cycle through negated/affirmed events, below/at/above-threshold ALT/AST/bilirubin values, leading-zero ID components, nested identifiers, varied phones/extensions, emails, DOB, SSN, and MRN embedded in notes and event descriptions. They use fictional names, reserved `.invalid` email domains, `555-01xx` phone numbers, and invalid `000` SSNs; no real patient data is loaded.

```python
from src.utils.mock_generator import generate_clinical_records

for record in generate_clinical_records(10_000, seed=42, note_repetitions=8):
    result = pipeline.run_record(record)
```

Compare both engines after installing `requirements-langgraph.txt`:

```bash
python -m tests.benchmark --records 2000 --repeats 3 --note-repetitions 4
# Native-only deployments can benchmark without optional graph dependencies:
python -m tests.benchmark --engine native --records 2000
# Optional hardware-specific acceptance budgets (nonzero exit on failure):
python -m tests.benchmark --records 2000 --max-latency-ratio 10 --max-memory-ratio 10
```

Each engine runs in a fresh interpreter with identical seeded data and warm-up. The terminal summary reports mean/P50/P95 latency, records per second, peak traced Python allocations, and engine deltas. Latency excludes startup, generation, validation assertions, and memory instrumentation. A separate streamed memory pass includes data generation and does not measure total process RSS or native-library allocations. Every timed result is checked against independent clinical and redaction expectations; token-normalized complete-state digests must match across engines. Random security tokens are deliberately not seeded. No universal speed guarantee is implied; configure budgets on representative deployment hardware.

## Project status and limitations

This repository is a hardened local reference implementation, not a validated or production-ready clinical system. The agents are deterministic Python functions; licensed MedDRA coding, clinical narrative review, human approval, electronic signatures, and persistent audit logging are not implemented. Selected-identifier redaction is not a complete HIPAA Safe Harbor method and does not guarantee that a record is de-identified. Dates, geography, biometrics, contextual identity, and unsupported international phone formats require additional controls and validation. Do not use real patient information.

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
config/runtime.json             Local engine, revision limit, and QC threshold
docs/                           Scope, architecture, security, and evaluation notes
src/main.py                     Local demonstration entry point
src/agents/                     Workflow state, graph, and deterministic nodes
src/agents/utils/               Streaming CSV, redaction/token vault, clinical rules
src/runtime/                    Immutable validated runtime configuration
src/utils/mock_generator.py     Streaming seeded synthetic clinical fixtures
tests/                           Unit and workflow tests
tests/benchmark.py              Isolated latency, throughput, memory, and parity checks
requirements.txt                Python runtime dependencies
requirements-langgraph.txt      Optional LangGraph runtime dependencies
```

## Documentation

- [Scenario and intended use](docs/business_scenario.md)
- [System architecture](docs/system_architecture.md)
- [Security and regulatory considerations](docs/compliance_governance.md)
- [Evaluation approach](docs/evaluation_observability.md)
