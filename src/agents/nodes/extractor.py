import logging
from typing import Dict, Any
from src.agents.state import AgentState

logger = logging.getLogger("AegisCSR.extractor")

def extract_and_code_data(state: AgentState) -> Dict[str, Any]:
    """
    Node A: Data Extraction & MedDRA Coding Agent.
    Inspects raw patient databases, extracts demographic metrics, and cross-references
    unstructured adverse events with standardized MedDRA classification mappings.
    """
    logger.info("Executing Data Extraction & MedDRA Coding Node")
    raw_data = state.get("raw_data", {})
    subject_id = raw_data.get("subject_id", "SUBJ-UNKNOWN")
    
    # 1. Demographics Extraction
    age = raw_data.get("age", "Unknown")
    sex = raw_data.get("sex", "Unknown")
    treatment_arm = raw_data.get("treatment_arm", "Placebo")
    
    # 2. Adverse Event & Lab Analysis
    adverse_events = raw_data.get("adverse_events", [])
    lab_records = raw_data.get("labs", {})
    
    # 3. Standardized MedDRA Coding Simulation
    # In production, this would perform a semantic similarity/vector database lookup
    # against the MedDRA Terminology dictionary (e.g., Pinecone/pgvector).
    coded_terms = []
    for ae in adverse_events:
        ae_desc = ae.get("description", "").lower()
        severity = ae.get("severity", "Mild")
        
        if "gallbladder" in ae_desc or "cholecystitis" in ae_desc:
            coded_terms.append(f"Gastrointestinal disorders: Cholecystitis Acute ({severity})")
        elif "liver" in ae_desc or "liver enzymes" in ae_desc or "alt" in ae_desc:
            coded_terms.append(f"Hepatobiliary disorders: Drug-induced liver injury ({severity})")
        else:
            coded_terms.append(f"General disorders: {ae.get('description', 'Unspecified AE')} ({severity})")
            
    # Process lab enzymes (ALT / AST)
    alt_max = lab_records.get("alt_peak_uln", 1.0)
    bili_max = lab_records.get("bili_peak_uln", 1.0)
    
    if alt_max >= 3.0:
        coded_terms.append(f"Investigations: Alanine aminotransferase increased ({alt_max}x ULN)")
    if bili_max >= 2.0:
        coded_terms.append(f"Investigations: Blood bilirubin increased ({bili_max}x ULN)")
        
    logger.info(f"Coded Terms for Subject {subject_id}: {coded_terms}")
    
    return {
        "coded_terms": coded_terms
    }
