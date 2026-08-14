<p align="center">
  <img src="banner.svg" alt="Biotech Agentic System Banner" width="100%">
</p>

# Biotech Agentic System

This repository hosts the core architecture, implementation patterns, and enterprise governance framework for a production-grade multi-agent system designed for commercial-stage biotechnology and clinical development. The platform automates complex, high-value operations—such as clinical trial safety reporting, Clinical Study Report (CSR) synthesis, and structured adverse event extraction—while maintaining deterministic validation, regulatory compliance, and security guardrails.

---

## Technical Architecture and Orchestration

The system uses stateful, directed cyclic graphs to orchestrate specialized agents, ensuring strict execution boundaries and reproducible pathways necessary for regulated clinical environments.

```
                  +------------------------+
                  |    Clinical Data In    |
                  +-----------+------------+
                              |
                              v
                  +------------------------+
            +---->+   Orchestrator Node    +<----------------+
            |     +-----------+------------+                 |
            |                 |                              |
            |        +--------+--------+                     |
            |        v                 v                     |
            | +-------------+   +-------------+              |
            | |  Data       |   |  Medical    |              |
            | |  Extractor  |   |  Writer     |              |
            | +------+------+   +------+------+              |
            |        |                 |                     |
            +--------+-----------------+------- Human Review |
                     v                 v        (HITL Check)
               [State Update]    [State Update]
```

### State Management and Graph Topology

For complex biotechnology workflows, stateful cyclic graphs provide several engineering advantages over traditional linear pipelines or autonomous multi-agent chats:

1. **Deterministic Execution Paths**: Restricting agent transitions to defined graph edges with explicit condition checks prevents infinite reasoning loops and bounds API resource consumption.
2. **State Checkpointing**: Persisting the execution graph state at each node allows seamless recovery from transient network or tool-calling failures without restarting the process.
3. **Human-in-the-Loop Interruption**: Pausing execution prior to high-risk nodes (e.g., database writes or external reporting) exposes the current state for manual clinical investigator review, validation, or modification.

---

## Core Engineering Implementations

The following reference implementations demonstrate stateful orchestration, client-side data de-identification, and constant-memory data ingestion.

### 1. Stateful Multi-Agent Orchestration

The following implementation utilizes LangGraph to define a structured clinical safety reporting workflow. It implements validation scoring, state checkpointing, and cycle limits to prevent runaway execution.

```python
from typing import Annotated, Dict, Any, List
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    raw_data: Dict[str, Any]
    coded_terms: List[str]
    draft_narrative: str
    compliance_score: float
    loop_count: int
    errors: List[str]

def extract_and_code_data(state: AgentState) -> Dict[str, Any]:
    # Extract data and match with MedDRA taxonomy
    return {
        "coded_terms": ["Elevated ALT", "Hepatic Steatosis"],
        "loop_count": state.get("loop_count", 0) + 1
    }

def write_medical_narrative(state: AgentState) -> Dict[str, Any]:
    # Generate structured narrative draft
    return {
        "draft_narrative": "Patient exhibited elevated ALT levels consistent with baseline hepatic steatosis.",
        "loop_count": state["loop_count"] + 1
    }

def quality_control_check(state: AgentState) -> Dict[str, Any]:
    # Execute deterministic evaluation or LLM-as-a-judge scoring
    return {
        "compliance_score": 0.85, 
        "errors": []
    }

def route_after_qc(state: AgentState) -> str:
    # Define conditional routing to prevent infinite iteration
    if state["loop_count"] > 5:
        return "force_human_intervention"
    if state["compliance_score"] >= 0.90:
        return "approve"
    return "rewrite"

# Construct stateful execution graph
workflow = StateGraph(AgentState)

workflow.add_node("extractor", extract_and_code_data)
workflow.add_node("writer", write_medical_narrative)
workflow.add_node("qc_checker", quality_control_check)

workflow.set_entry_point("extractor")
workflow.add_edge("extractor", "writer")
workflow.add_edge("writer", "qc_checker")

workflow.add_conditional_edges(
    "qc_checker",
    route_after_qc,
    {
        "approve": END,
        "rewrite": "writer",
        "force_human_intervention": END
    }
)

app = workflow.compile()
```

### 2. Client-Side Data De-identification (HIPAA Compliance)

This module provides client-side anonymization, stripping Protected Health Information (PHI) and tokenizing Patient IDs before outbound LLM submission, and local reverse mapping for clinical re-identification.

```python
import os
import re
from typing import Dict, Any, Tuple
from cryptography.fernet import Fernet

class ClinicalDeidentifier:
    def __init__(self):
        # NOTE: A persistent key must be loaded from a secure vault (e.g., AWS KMS) in production.
        # Generating a key in __init__ is for demonstration and limits decryption to the current instance.
        self.encryption_key = Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        
        # Internal mapping registry for pseudo-anonymization lookup
        self._token_registry: Dict[str, str] = {}
        self._reverse_registry: Dict[str, str] = {}

    def _encrypt_value(self, value: str) -> str:
        """Encrypts sensitive data so it can be safely recovered later."""
        return self.cipher.encrypt(value.encode('utf-8')).decode('utf-8')

    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypts a previously encrypted sensitive data token."""
        return self.cipher.decrypt(encrypted_value.encode('utf-8')).decode('utf-8')

    def anonymize_patient_record(self, raw_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Removes direct HIPAA identifiers and tokenizes patient IDs (USUBJID)
        prior to transmitting payloads to external LLM endpoints.
        Note: The token mappings are maintained internally on the instance.
        """
        anonymized = raw_record.copy()
        
        # Remove direct PII
        if "patient_name" in anonymized:
            del anonymized["patient_name"]
        if "ssn" in anonymized:
            del anonymized["ssn"]

        # Tokenize Patient Subject ID
        raw_id = str(anonymized.get("subject_id", ""))
        if raw_id:
            if raw_id not in self._token_registry:
                token = f"SUBJ-ANON-{len(self._token_registry) + 1001}"
                encrypted_raw_id = self._encrypt_value(raw_id)
                
                # Store mapping securely within secure infrastructure boundaries
                self._token_registry[raw_id] = token
                self._reverse_registry[token] = encrypted_raw_id
            
            anonymized["subject_id"] = self._token_registry[raw_id]

        # Apply heuristic regular expressions to redact unstructured PII
        if "clinical_notes" in anonymized:
            text = anonymized["clinical_notes"]
            text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[REDACTED_EMAIL]', text)
            text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[REDACTED_PHONE]', text)
            anonymized["clinical_notes"] = text

        return anonymized

    def reidentify_narrative(self, llm_output_text: str) -> str:
        """Re-injects true patient identities into local text files post-generation."""
        reidentified_text = llm_output_text
        tokens_found = re.findall(r'SUBJ-ANON-\d+', reidentified_text)
        
        for token in tokens_found:
            if token in self._reverse_registry:
                encrypted_id = self._reverse_registry[token]
                true_id = self._decrypt_value(encrypted_id)
                reidentified_text = reidentified_text.replace(token, true_id)
                
        return reidentified_text

if __name__ == "__main__":
    scrubber = ClinicalDeidentifier()
    
    raw_payload = {
        "subject_id": "USUBJID-NASH-0042",
        "patient_name": "John Doe",
        "age": 54,
        "clinical_notes": "Spoke with investigator at john.doe@email.com. Patient shows severe hepatic steatosis."
    }
    
    # Pre-Gateway Outbound processing
    safe_payload = scrubber.anonymize_patient_record(raw_payload)
    print("--- Safe Outbound Payload (Sent to LLM) ---")
    print(safe_payload)
    
    # Simulated incoming LLM generation text response
    mock_llm_response = f"The safety summary for {safe_payload['subject_id']} indicates elevated liver enzymes."
    
    # Post-Gateway Inbound processing
    final_narrative = scrubber.reidentify_narrative(mock_llm_response)
    print("\n--- Final Re-identified Internal Text ---")
    print(final_narrative)
```

### 3. Constant-Memory Streaming for Large Clinical Files

Biotechnology applications must regularly process large-scale datasets, such as multi-gigabyte SAS transfer files (.xpt) or laboratory telemetry CSVs. Loading these entirely into memory risks Out-Of-Memory (OOM) failures.

```
                      +----------------------------------------+
                      |      Large SAS / CSV File Upload       |
                      +-------------------+--------------------+
                                          |
                                          v
                      +----------------------------------------+
                      |    Secure Storage (SSE-KMS Encryption) |
                      +-------------------+--------------------+
                                          |
                                          v
                      +----------------------------------------+
                      |  Asynchronous Processing Pool (Celery) |
                      +-------------------+--------------------+
                                          |
                                          v
                      +----------------------------------------+
                      |  Streamed Chunking (Pandas Iterator)   |
                      +-----------+--------------------+-------+
                                  |                    |
              Batch 1 (Rows 1-500)|                    | Batch 2 (Rows 501-1000)
                                  v                    v
                      +---------------+        +---------------+
                      | Extract/Code  |        | Extract/Code  |
                      | Agent Node    |        | Agent Node    |
                      +---------------+        +---------------+
```

The platform mitigates OOM risks via decoupled asynchronous processing and streamed chunking:

```python
import pandas as pd

def stream_and_process_clinical_file(file_path: str, chunk_size: int = 500):
    """Processes large clinical files in sequential blocks to maintain a flat memory profile."""
    iterator = pd.read_csv(file_path, chunksize=chunk_size)
    
    for chunk_index, chunk in enumerate(iterator):
        payload = chunk.to_dict(orient="records")
        execute_agent_workflow_on_batch(payload)
        print(f"Successfully processed chunk {chunk_index}. Memory footprint stable.")
```

*State Minimization*: Never attach raw binary files or large dataframes directly to the graph state. Store immutable S3 URI references (e.g., `s3://clinical-vault/raw/part_1.csv`) and pass only block pointers between agent nodes.

---

## Applied Test, Evals, and Observability

Traditional software unit tests are insufficient for non-deterministic LLM applications. Our framework implements systematic evaluations, tracking, and guardrails across offline regression testing and online production monitoring.

### 1. Automated Faithfulness and Grounding Evaluation

The evaluation node uses LLM-as-a-judge patterns to score medical writer output against clinical raw inputs. The following evaluator validates compliance, scores confidence, and logs feedback directly back to a centralized LangSmith trace dashboard.

```python
import os
from typing import Dict, Any
from langsmith import Client
from pydantic import BaseModel, Field
from openai import OpenAI

ls_client = Client()
openai_client = OpenAI()

class ComplianceVerdict(BaseModel):
    is_faithful: bool = Field(description="True if the narrative contains NO facts missing from or contradictory to the raw data.")
    hallucinated_facts: list[str] = Field(description="List of specific claims or numbers not backed by the raw data.")
    confidence_score: float = Field(description="Confidence score between 0.0 and 1.0.")

def evaluate_agent_run(run_id: str) -> Dict[str, Any]:
    """Fetches an execution trace from LangSmith, audits the output narrative, and commits scores."""
    run = ls_client.read_run(run_id)
    raw_clinical_data = run.inputs.get("raw_data", {})
    generated_narrative = run.outputs.get("draft_narrative", "")
    
    if not generated_narrative:
        raise ValueError(f"Run {run_id} contains no valid agent output narrative.")

    system_prompt = (
        "You are an expert FDA clinical trial data auditor. Your job is to verify "
        "that the medical narrative matches the raw clinical data exactly. "
        "Flag any numerical discrepancies, undocumented lab values, or fabricated symptoms."
    )
    
    user_prompt = f"""
    [RAW CLINICAL DATA]
    {raw_clinical_data}

    [GENERATED AGENT NARRATIVE]
    {generated_narrative}

    Compare the narrative to the raw data. Ensure strict adherence to facts.
    """

    completion = openai_client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format=ComplianceVerdict,
    )
    
    verdict = completion.choices[0].message.parsed

    # Commit feedback directly to the matching LangSmith trace
    ls_client.create_feedback(
        run_id=run_id,
        key="clinical_faithfulness",
        score=1.0 if verdict.is_faithful else 0.0,
        comment=f"Hallucinations found: {', '.join(verdict.hallucinated_facts)}" if verdict.hallucinated_facts else "Perfect compliance."
    )

    return verdict.model_dump()
```

- **Structured Parsing**: Using Pydantic schemas with structured parsing guarantees the evaluation output adheres to the specified schema, preventing downstream failures.
- **Trace Binding**: Linking evaluations directly to LangSmith trace identifiers allows engineers to monitor regression trends over successive prompt and model adjustments.

---

## Reference Testing Datasets

To evaluate and validate the biotechnology orchestration pipelines, the following open-source clinical and safety datasets are recommended:

1. **CDISC SDTM/ADaM Pilot Project** (`cdisc-org/sdtm-adam-pilot-project`)
   - **Domain**: Structured clinical trial data.
   - **Details**: Provides reference standard clinical data formatted to CDISC SDTM and ADaM standards, including demographics (ADSL) and adverse events (ADAE). This dataset is critical for verifying low-level data-extraction scripts written by analysis agents.

2. **safetyData** (`SafetyGraphics/safetyData`)
   - **Domain**: Permissive clinical safety profiles.
   - **Details**: An MIT-licensed R/CRAN package compiling formatted clinical trial datasets designed for safety and efficacy interactive reports. It contains standard patient safety variables across key clinical domains.

3. **MIMIC EHR Databases (MIMIC-III / MIMIC-IV)**
   - **Domain**: Longitudinal clinical records.
   - **Details**: De-identified clinical telemetry and clinical narrative notes from intensive care units. Highly valuable for testing unstructured PII scrubbing models and clinical narrative generation at scale.

4. **PHUSE Synthetic CDISC Datasets**
   - **Domain**: Synthetic clinical trials.
   - **Details**: Programmatically synthesized, fully compliant CDISC datasets designed for end-to-end pipeline testing without privacy restrictions.

---

## Enterprise Governance and Regulatory Protocols

### 1. FDA 21 CFR Part 11 Compliance
FDA 21 CFR Part 11 requires immutable audit trails, system validations, and electronic signatures. This platform achieves compliance through:
- **Append-Only Ledger Store**: Leveraging LangGraph checkpointers configured over an immutable, append-only PostgreSQL database to permanently record every state transition, tool execution, and prompt hash.
- **Cryptographic Prompt Registry**: Version-controlling prompt templates in Git, locking them with SHA-256 hashes, and auditing prompt-to-model assignments.
- **Electronic Signature Gateway**: Injecting mandatory Human-in-the-Loop nodes for data writing operations. Final approvals require verified investigator authentication signatures via an OAuth2 gateway.

### 2. HIPAA Compliance and Zero-Retention Protocols
To protect Protected Health Information (PHI) and clinical patient privacy:
- **Enterprise BAAs**: Mandating zero-retention Business Associate Agreements (BAAs) with API providers (e.g., AWS Bedrock, Azure OpenAI) to prohibit training on clinical data and prevent persistent caching.
- **Local De-identification Gateway**: Forcing clinical payloads through the local de-identification service before routing to external APIs, ensuring patient identities never leave the internal security boundary.
- **Data Encryption**: Encrypting all data at rest via AES-256 and in transit via TLS 1.3.

### 3. Verification of System Reliability
External audits require systematic proof of safety:
- **Continuous Regression Auditing**: Running automated regression suites against historical clinical reference sets prior to any production deployment.
- **LLM-as-a-Judge Monitoring**: Measuring factual grounding, semantic correctness, and context relevance on all outbound messages.
- **Graceful Failure Routing**: Redirecting systems to isolated queue states for manual oversight whenever confidence scores drop below a 0.90 threshold.
