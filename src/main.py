import os
import logging
from src.agents.utils.deidentifier import ClinicalDeidentifier
from src.agents.graph import AegisStateGraphOrchestrator
from src.agents.state import AgentState

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AegisCSR.main")

def run_pipeline_demo():
    logger.info("Initializing AegisCSR Multi-Agent Pipeline Demo...")
    
    # 1. Initialize local security gateway (Cryptographic De-identifier)
    deidentifier = ClinicalDeidentifier()
    
    # 2. Build mock raw clinical data representing our metabolic liver trial scenario
    # Fictional values that resemble direct identifiers for the local demo.
    raw_patient_payload = {
        "subject_id": "USUBJID-THR902-142",
        "patient_name": "Leonard Vance",
        "ssn": "000-12-3456",
        "phone": "555-019-2831",
        "age": 54,
        "sex": "Male",
        "treatment_arm": "THR-902 10mg Active Dose",
        "labs": {
            "alt_peak_uln": 4.2,  # Hepatobiliary trigger ALT > 3x ULN
            "bili_peak_uln": 2.2  # Bilirubin > 2x ULN
        },
        "adverse_events": [
            {
                "description": "Severe Acute Cholecystitis",
                "onset_day": 28,
                "severity": "Severe",
                "relation": "Possibly Related"
            }
        ],
        "clinical_notes": "Patient Vance checked in with investigator via email: l.vance@clinic.org. Complaining of severe RUQ abdominal pain."
    }
    
    logger.info(f"Raw Patient Record (Local Core): Subject ID = {raw_patient_payload['subject_id']}")
    
    # 3. Client-Side Anonymization: Stripping PHI before outbound transmission
    safe_patient_payload = deidentifier.anonymize_patient_record(raw_patient_payload)
    logger.info("Limited demo tokenization and redaction completed.")
    logger.info(f"Tokenized subject ID: {safe_patient_payload['subject_id']}")
    logger.info(f"Selected field removed: 'patient_name' in payload = {'patient_name' in safe_patient_payload}")
    
    # 4. Construct initial state for the LangGraph orchestrator
    initial_state: AgentState = {
        "raw_data": safe_patient_payload,
        "coded_terms": [],
        "draft_narrative": "",
        "compliance_score": 0.0,
        "loop_count": 0,
        "errors": [],
        "is_approved": False
    }
    
    # 5. Compile and run the state graph orchestrator
    orchestrator = AegisStateGraphOrchestrator()
    final_state = orchestrator.execute(initial_state)
    
    # 6. Retrieve safe de-identified draft narrative (The text returned from cloud LLM gateway)
    safe_draft_text = final_state.get("draft_narrative", "")
    logger.info("========== TOKENIZED DEMO DRAFT ==========")
    print(safe_draft_text)
    logger.info("=======================================================")
    
    # 7. Local Re-identification: Restoration of original clinical IDs inside secure perimeter
    final_restored_narrative = deidentifier.reidentify_narrative(safe_draft_text)
    logger.info("========== FINAL RESTORED INTERNAL CSR NARRATIVE ==========")
    print(final_restored_narrative)
    logger.info("===========================================================")
    
    logger.info(f"Pipeline completed. Automated QC threshold met: {final_state['is_approved']}")
    logger.info(f"Final illustrative QC score: {final_state['compliance_score']:.2f}")

if __name__ == "__main__":
    run_pipeline_demo()
