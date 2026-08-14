# System Architecture & Technical Design: AegisCSR

AegisCSR is built as an enterprise-grade multi-agent system. In a clinical trial setting, traditional unstructured LLM agents are too unpredictable and liable to "hallucinate" critical safety facts. AegisCSR solves this by using **LangGraph** to model the system as a stateful, cyclic directed graph. This provides strict, deterministic control over execution pathways, ensures data lineage, and implements self-correcting loop limits.

---

## High-Level System Architecture

The AegisCSR platform orchestrates four distinct specialized agents, each serving as a node in our state machine:

```
                              ┌────────────────────────┐
                              │  Client Raw Data Input  │
                              └───────────┬────────────┘
                                          │ (Local PHI De-identification)
                                          ▼
                              ┌────────────────────────┐
                              │   Ingested Secure State│
                              └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                        ┌────►│  Data Extraction &     │◄────────────────┐
                        │     │  MedDRA Coding Agent   │                 │
                        │     └───────────┬────────────┘                 │
                        │                 │ (Standardized Variables)     │
                        │                 ▼                              │
                        │     ┌────────────────────────┐                 │
                        │     │  Medical Writer Agent  │                 │
                        │     └───────────┬────────────┘                 │
                        │                 │ (Draft Narrative Paragraphs) │
                        │                 ▼                              │
                        │     ┌────────────────────────┐                 │
                        │     │  QC Compliance Auditor │                 │
                        │     └───────────┬────────────┘                 │
                        │                 │ (Compliance Score + Feedback)│
                        │                 ▼                              │
                        │     ┌────────────────────────┐                 │
                        │     │  Conditional Router    │                 │
                        │     └───────┬──────────┬─────┘                 │
                        │             │          │                       │
                        │     Score < │          │ Score >= 90%          │
                        │     90%     │          │ OR Loop Count > 5     │
                        │             ▼          ▼                       │
                        └─────── [Rewrite]    [End / HITL Checkpoint] ───┘
                                                     │ (Re-identification)
                                                     ▼
                                              [Final CSR Narrative]
```

---

## Core System Components

### 1. Cryptographic Gateway & De-identifier
Before clinical trial data ever leaves the local enterprise network to be processed by a cloud-hosted LLM (e.g., GPT-4o on Azure OpenAI or AWS Bedrock), it passes through a local **De-identification Gateway**. This module strips out direct HIPAA identifiers (names, SSNs, phone numbers) and cryptographically scrambles unique subject identifiers (`subject_id` or `USUBJID`). Mapping registries are stored in-memory within secure local boundaries.

### 2. Streamed CDISC Ingestion Engine
To prevent Out-Of-Memory (OOM) crashes when parsing large clinical files (such as SAS `.xpt` datasets), AegisCSR utilizes a chunk-based pandas iterator. Instead of loading the full clinical database, we extract localized, patient-specific rows matching the target `USUBJID` across the **ADSL** (demographics), **ADAE** (adverse events), and **ADLB** (laboratory) domains.

### 3. State Management & LangGraph State Graph
The entire workflow is modeled as a `StateGraph` which manages a shared, mutable `AgentState` TypedDict. Every node in the graph reads from this state, performs its operation, and writes its updates back to the state. This is an append-only, stateful checkpoint pattern, meaning we preserve full traceability of how the final text was compiled.

#### The `AgentState` TypedDict Structure:
- `raw_data`: Dict containing the de-identified patient demographics and records.
- `coded_terms`: List of standardized medical terms coded during execution (e.g., MedDRA terms).
- `draft_narrative`: The active markdown text of the drafted safety narrative.
- `compliance_score`: Float between 0.0 and 1.0 representing the rating of the QC Auditor.
- `loop_count`: Integer tracker indicating the number of revision iterations.
- `errors`: List of validation errors, hallucinations, or contradictions identified during QC.

### 4. Special Agent Squad Nodes

#### Node A: Data Extraction & MedDRA Coding Agent
- **Responsibility**: Inspects raw patient logs. Extracts critical covariates (e.g., Age, Treatment Cohort, Adverse Event onset date, baseline vs. post-baseline lab measurements).
- **Taxonomy Standard**: Cross-references raw adverse event descriptions (e.g., "stomach pain and nausea") with standard **MedDRA (Medical Dictionary for Regulatory Activities)** terminology (e.g., "Gastrointestinal Disorders: Abdominal Pain / Nausea") using vector search and contextual semantic matching.

#### Node B: Medical Writer Agent
- **Responsibility**: Ingests the extracted variables and coded terms from the state. Synthesizes a structured narrative according to standard ICH E3 guidelines (Structure and Content of Clinical Study Reports).
- **Output Format**: Structured Markdown containing:
  - Patient Demographics & Treatment Assignment.
  - History of Present Illness / Adverse Event Chronology.
  - Longitudinal Laboratory Findings (focusing on ALT/AST/Bilirubin elevations).
  - Disposition, drug discontinuation, or resolution status.

#### Node C: QC Compliance Auditor Agent (The Critic)
- **Responsibility**: Acts as an "LLM-as-a-judge" clinical auditor. It performs structured data validation, comparing the written draft narrative against the raw data values in the state.
- **Auditing Criteria**:
  - **Faithfulness**: Are there any numerical claims in the draft that do not exist in the raw dataset?
  - **Formatting**: Does the structure adhere to ICH E3 regulations?
  - **Omissions**: Did the narrative fail to mention critical lab elevations (e.g. ALT exceeding 3x ULN) or treatment drug interruption?

### 5. Conditional Routing Logic
AegisCSR uses conditional routing edges to manage revision.
- If the QC Compliance Auditor assigns a score **>= 90%**, the graph terminates, and the payload is sent to the medical monitor for Human-in-the-Loop review.
- If the score is **< 90%**, the graph routes the state back to the **Medical Writer Agent** for a revision, with the precise errors and feedback appended to the state.
- To prevent infinite loops and runaway API costs, we enforce an explicit loop limit (**Maximum Iteration Counter = 5**). If exceeded, the graph automatically terminates with a "Force Human Intervention" flag, routing the draft to a senior clinical auditor with the full execution log.
