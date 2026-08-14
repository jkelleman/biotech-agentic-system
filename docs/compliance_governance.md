# Compliance, Governance & Security: Enforcing Regulated AI in Biotech

Pharmaceutical drug R&D is one of the most heavily regulated industries in the world. Deploying artificial intelligence within this domain requires strict adherence to international security standards, patient privacy laws, and regulatory audit frameworks. 

**AegisCSR** is engineered from the ground up as a "Compliance-First" agentic platform, bridging the gap between state-of-the-art LLM capabilities and the rigid standards of clinical operations.

---

## 1. FDA 21 CFR Part 11 Compliance
FDA 21 CFR Part 11 regulates electronic records and electronic signatures in clinical trials. It requires clinical systems to ensure reliability, trustworthiness, and clear audit trails.

AegisCSR satisfies 21 CFR Part 11 through these architectural patterns:
- **Immutable State Checkpointing**: LangGraph's persistent state saver is backed by an append-only PostgreSQL database. Every agent node transition, tool execution, and prompt state is captured as a permanent record. These historical logs can never be modified or deleted, preserving a high-resolution, chronologically correct audit trail.
- **Prompts-as-Code Governance**: All agent prompts are stored in a centralized, version-controlled git repository and managed through a prompt registry. Every change to a system prompt requires peer-review, automated unit testing, and cryptographic tagging before being compiled into production.
- **Electronic Signatures and IAM**: The final narrative output cannot be compiled into the clinical database without a double-signature from a certified Medical Monitor or Principal Investigator. These signatures are authenticated via OAuth2 identity providers with role-based access control (RBAC).

---

## 2. Patient Privacy & HIPAA Compliance
Under the Health Insurance Portability and Accountability Act (HIPAA), clinical trial patient data containing Protected Health Information (PHI) must be carefully protected.

### Secure LLM Gateway
AegisCSR enforces a strict boundary between internal clinical data servers and external Large Language Model APIs (e.g. OpenAI, Anthropic, or Cohere):
1. **Business Associate Agreements (BAAs)**: We mandate that any third-party model vendor (such as Microsoft Azure OpenAI or AWS Bedrock) must sign a BAA ensuring that customer data is never cached, stored, or utilized for training public foundational models.
2. **Client-Side Cryptographic De-identification**: Clinical files are stripped of direct HIPAA identifiers (names, SSNs, emails, detailed dates) before leaving our secure network. 

### Local Anonymization Flow
- A local utility runs a regular expression scanner to redact accidental phone numbers or emails in clinical trial notes.
- Unique patient identifiers (`USUBJID`) are mapped to randomized tokens (e.g., `USUBJID-THR902-142` becomes `SUBJ-ANON-1042`).
- The real identities are encrypted using local symmetric keys (`AES-256` Fernet) and stored in-memory in our secure enterprise perimeter.
- When the draft narrative returns from the LLM, the local de-identifier replaces the tokens back with original, compliant IDs for internal consumption. The external LLM never sees any PHI or traceable IDs.

```
 [ Local Server: Raw Data ] ──> [ Cryptographic De-identifier ] ──> [ Safe Outbound Token Data ]
                                                                                │
                                                                                ▼
 [ Local Server: CSR Narrative] <── [ Re-identifier Engine ] <── [ LLM API Generation Response ]
```

---

## 3. Human-in-the-Loop (HITL) Checkpoints
While AegisCSR has a self-correcting validation node, we never bypass human clinical expertise. The system treats AI as an accelerator, not an autonomous decision-maker.

### Interrupt-and-Review State Pattern
LangGraph natively allows us to **interrupt** execution before specific high-stakes nodes. In AegisCSR, the graph pauses immediately after a narrative passes the QC Compliance check.
- The state is locked.
- A webhook triggers a notification to the **Medical Monitor Portal**.
- The Medical Monitor reviews the drafted narrative side-by-side with the raw data tables.
- The reviewer can make edits directly to the draft or append manual feedback (e.g., *"Please detail the patient's prior medical history of diabetes more clearly"*).
- The system captures the reviewer's approval signature, updates the permanent State history, and resumes the graph execution to output the final report.

---

## 4. Mitigating Hallucinations and Errors
Large Language Models are non-deterministic, making them prone to hallucinations (fabricating numbers, labs, or clinical events). AegisCSR eliminates this risk through:
1. **Tool Sandboxing**: Rather than letting the LLM calculate stats, the Data Analyst Agent writes clean, sandboxed Python code to compute liver enzyme fold-increases. Only the execution results are added to the State.
2. **Structured LLM-as-a-Judge Auditing**: We utilize Pydantic structured output models to force the Compliance Judge to output a boolean `is_faithful` rating and a detailed list of `hallucinated_facts`. If any discrepancy is found, the system fails the draft, preventing faulty data from reaching clinicians.
