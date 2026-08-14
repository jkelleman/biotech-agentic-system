from typing import Dict, Any, List
from typing_extensions import TypedDict

class AgentState(TypedDict):
    """
    State definition for the AegisCSR multi-agent clinical trial synthesis platform.
    Keeps track of raw data, structured taxonomy coding, the drafted text, and QC audits.
    """
    raw_data: Dict[str, Any]       # Raw clinical trial data extracted from CDISC (ADSL, ADAE, ADLB)
    coded_terms: List[str]         # Coded medical taxonomies mapped via MedDRA (e.g., Elevated ALT)
    draft_narrative: str           # The generated clinical study narrative drafted by the Writer Agent
    compliance_score: float        # The rating assigned by the Compliance Auditor Node (0.0 - 1.0)
    loop_count: int                # Counter of rewrite/revision iterations to prevent infinite loops
    errors: List[str]              # Detailed compliance infractions, factual mismatches, or omissions
    is_approved: bool              # Flag denoting whether human reviewer approved the narrative
