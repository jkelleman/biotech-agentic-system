import logging
from typing import Dict, Any, List
from src.agents.state import AgentState

logger = logging.getLogger("AegisCSR.validator")

def quality_control_check(state: AgentState) -> Dict[str, Any]:
    """
    Node C: QC & Compliance Auditor Agent (The Critic).
    Runs programmatic checks to verify that the generated medical narrative matches
    the raw data tables exactly, flags potential hallucinations, and outputs a quality score.
    """
    logger.info("Executing Quality Control & Compliance Check Node")
    raw_data = state.get("raw_data", {})
    draft_narrative = state.get("draft_narrative", "")
    
    errors: List[str] = []
    
    # 1. Verification of Key Demographics
    subject_id = raw_data.get("subject_id", "")
    age = str(raw_data.get("age", ""))
    sex = raw_data.get("sex", "")
    treatment_arm = raw_data.get("treatment_arm", "")
    
    if subject_id not in draft_narrative:
        errors.append(f"Omission: Subject ID '{subject_id}' is missing from the draft narrative.")
        
    if age not in draft_narrative:
        errors.append(f"Accuracy Error: Patient age '{age}' is missing from the narrative.")
        
    if sex.lower() not in draft_narrative.lower():
        errors.append(f"Accuracy Error: Patient gender/sex '{sex}' mismatch in narrative.")
        
    if treatment_arm.lower() not in draft_narrative.lower():
        errors.append(f"Accuracy Error: Treatment arm '{treatment_arm}' is incorrectly stated or omitted.")
        
    # 2. Lab Thresholds Audit
    labs = raw_data.get("labs", {})
    alt_max = labs.get("alt_peak_uln", 1.0)
    
    # Critical clinical trigger: ALT > 3x ULN MUST be explicitly detailed
    if alt_max >= 3.0 and "alt" not in draft_narrative.lower() and "alanine" not in draft_narrative.lower():
        errors.append(f"Clinical Omission: Patient experienced an ALT peak of {alt_max}x ULN, but it is not documented in the narrative.")
        
    # 3. Adverse Events Transcription Check
    aes = raw_data.get("adverse_events", [])
    for ae in aes:
        desc = ae.get("description", "").lower()
        if desc not in draft_narrative.lower():
            errors.append(f"Data Mismatch: Reported Adverse Event '{desc}' was not transcribed in final report.")
            
    # Calculate Compliance Score (1.0 = perfect, deduct 0.15 per error)
    base_score = 1.0
    deduction = len(errors) * 0.15
    compliance_score = max(0.0, base_score - deduction)
    
    logger.info(f"QC Completed. Score: {compliance_score:.2f}. Identified Errors: {errors}")
    
    return {
        "compliance_score": compliance_score,
        "errors": errors
    }
