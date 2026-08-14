# Evaluation & Observability: Engineering Reliability into Agentic Workflows

Unlike traditional software engineering, agentic systems are non-deterministic. A prompt that works perfectly today might fail tomorrow due to subtle shifts in context or model API updates. To maintain FDA-grade reliability, AegisCSR implements a dual-pillar evaluation and observability framework.

---

## 1. The Dual-Pillar Framework

Our architecture separates testing into two distinct operational layers:
- **Offline Evaluation (Pre-deployment regression testing)**: Verifies prompt changes, new nodes, or system-level updates against historical golden datasets.
- **Online Observability (In-production tracing)**: Monitors live API calls, tracks token costs, logs latencies, and alerts developers to errors or runtime execution loops.

```
                          ┌────────────────────────┐
                          │   System Development   │
                          └───────────┬────────────┘
                                      │
                                      ▼
                        ┌────────────────────────────┐
                        │ OFFLINE EVALUATION PILLAR  │
                        │ - LLM-as-a-judge auditing  │
                        │ - Golden dataset tests     │
                        │ - Ragas & TruLens scoring  │
                        └─────────────┬──────────────┘
                                      │ (Passes quality gates)
                                      ▼
                        ┌────────────────────────────┐
                        │ ONLINE OBSERVABILITY PILLAR│
                        │ - LangSmith trace monitoring│
                        │ - Real-time error alerts   │
                        │ - Live feedback injection  │
                        └────────────────────────────┘
```

---

## 2. Offline Evaluation & LLM-as-a-Judge

Before deploying code changes, AegisCSR is subjected to a batch validation pipeline. We run the system on a **Golden Dataset** consisting of 100 manual clinical safety narratives written by certified medical writers, cross-referenced with their corresponding CDISC raw tables.

### Key Evaluation Metrics
Using evaluation libraries like **Ragas** and **TruLens**, we score each generated narrative across three core vectors:

1. **Faithfulness / Groundedness** (Scale: 0.0 to 1.0)
   - *Formula*: $Number\ of\ claims\ verified\ by\ raw\ data\ /\ Total\ claims\ made$
   - *Purpose*: Eliminates hallucinations by ensuring every statistical value or medical symptom described is directly supported by the CDISC tables in the state.
2. **Context Relevance** (Scale: 0.0 to 1.0)
   - *Purpose*: Measures whether the narrative includes all necessary variables (e.g. baseline ALT, age, drug dose) without cluttering the text with irrelevant raw data columns.
3. **Semantic Correctness & ICH E3 Alignment** (Scale: 0.0 to 1.0)
   - *Purpose*: Grades the style, medical tone, and structural adherence of the generated narrative to international clinical documentation guidelines.

### Production Guardrail threshold
AegisCSR mandates a **minimum Faithfulness score of 0.90** before a narrative can progress to the Human review step. Any draft falling below this threshold is routed back to the Writer node with the precise contradictory claims highlighted.

---

## 3. Online Observability & LangSmith Tracing

In production, every agent execution is mapped to a secure **LangSmith** or **Arize Phoenix** dashboard. This provides high-fidelity, nested trace logs for each run.

### Why Online Tracing is Critical for Clinical Systems
- **Catching Infinite Loops**: If the writer agent and the compliance auditor get stuck in an endless loop of revision (due to conflicting prompt constraints), developers can view the nested graph path in real-time. LangSmith captures the exact state values passed between `writer` and `qc_checker`.
- **Debugging Tool Failures**: If a CDISC pandas-parser script fails to run due to a null-value type mismatch, the full traceback, local variable bindings, and raw JSON payload are captured within the specific trace node.
- **Monitoring Cost & Latency**: Large models like GPT-4o are powerful but can be expensive and slow. LangSmith logs precise token-utilization counts and execution latencies, allowing our platform engineers to optimize prompt lengths and swap lighter, faster models (like GPT-4o-mini) into non-critical nodes (e.g., data extraction).

---

## 4. Live Feedback Loop Injection
By using the LangSmith SDK, our automated compliance evaluator logs its verdicts directly back to the active run trace using the `create_feedback` API. 
- Clinical administrators can monitor the performance of different model prompts over time.
- If a clinician reviews a draft and manually edits it in the Portal, the differential changes are captured and automatically labeled as a new "fine-tuning or few-shot example" in our prompt registry, creating a continuous improvement flywheel.
