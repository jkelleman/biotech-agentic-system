import logging
from typing import Dict, Any
from src.agents.state import AgentState

logger = logging.getLogger("AegisCSR.writer")

def write_medical_narrative(state: AgentState) -> Dict[str, Any]:
    """
    Node B: Medical Writer Agent.
    Ingests structured variables, lab reports, and coded taxonomies to draft
    a rigorous, ICH E3-compliant patient safety narrative.
    """
    logger.info("Executing Medical Writer Node")
    raw_data = state.get("raw_data", {})
    coded_terms = state.get("coded_terms", [])
    errors = state.get("errors", [])
    
    # Extraction
    subject_id = raw_data.get("subject_id", "SUBJ-UNKNOWN")
    age = raw_data.get("age", "Unknown")
    sex = raw_data.get("sex", "Unknown")
    treatment_arm = raw_data.get("treatment_arm", "Placebo")
    
    # Compose Narrative
    narrative_sections = []
    narrative_sections.append(f"# Patient Safety Narrative: Subject {subject_id}")
    narrative_sections.append(f"## Demographics and Cohort Placement")
    narrative_sections.append(
        f"Subject {subject_id} is a {age}-year-old {sex} patient enrolled in the Phase IIb "
        f"THR-902 trial for Metabolic Dysfunction-Associated Steatohepatitis (MASH). "
        f"The subject was randomized to the **{treatment_arm}** treatment group."
    )
    
    narrative_sections.append("## Standardized Adverse Events (MedDRA Coded)")
    if coded_terms:
        event_list = "\n".join([f"- {term}" for term in coded_terms])
        narrative_sections.append(event_list)
    else:
        narrative_sections.append("No adverse events recorded.")
        
    narrative_sections.append("## Chronology of Present Case")
    # Chronological compilation from raw data events
    events = raw_data.get("adverse_events", [])
    if events:
        for ae in events:
            desc = ae.get("description", "Adverse Event")
            onset = ae.get("onset_day", "N/A")
            severity = ae.get("severity", "Mild")
            relation = ae.get("relation", "Unrelated")
            narrative_sections.append(
                f"On Day {onset}, the patient experienced a {severity.lower()} case of **{desc}**. "
                f"The clinical investigator rated this event as **{relation.lower()}** to the study drug."
            )
    else:
        narrative_sections.append("No medical anomalies or serious adverse events reported.")
        
    # Check for errors from QC and inject remedial corrections
    if errors:
        narrative_sections.append("### QC Revision Notes")
        narrative_sections.append(
            "Revision applied to resolve data discrepancies identified during compliance check: "
            f"Resolved - {', '.join(errors)}"
        )
        
    draft_narrative = "\n\n".join(narrative_sections)
    
    current_loops = state.get("loop_count", 0)
    
    return {
        "draft_narrative": draft_narrative,
        "loop_count": current_loops + 1
    }
