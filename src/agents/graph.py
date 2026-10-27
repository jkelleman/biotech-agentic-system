import logging
from typing import Dict, Any

from src.agents.state import AgentState
from src.agents.nodes.extractor import extract_and_code_data
from src.agents.nodes.writer import write_medical_narrative
from src.agents.nodes.validator import quality_control_check

logger = logging.getLogger("AegisCSR.graph")

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    END = "__end__"

# 1. Routing Logic
def route_after_qc(state: AgentState) -> str:
    """
    Conditional routing edge. Resolves which node the state should proceed to next.
    - Prevents runaway costs and infinite loops via loop limits.
    - Stops after the configured revision limit without marking the draft approved.
    - Routes back to medical writer for editing if compliance score is low.
    - Approves and ends if score is >= 0.90.
    """
    loop_count = state.get("loop_count", 0)
    compliance_score = state.get("compliance_score", 0.0)
    
    # 5 is the maximum number of writer passes.
    if loop_count >= 5:
        logger.warning(f"Maximum revision count reached ({loop_count}); ending without approval.")
        return "max_revisions_reached"
        
    if compliance_score >= 0.90:
        logger.info(f"QC threshold met ({compliance_score:.2f} >= 0.90). Ending workflow.")
        return "approve"
        
    logger.info(f"Compliance Score ({compliance_score:.2f} < 0.90). Routing back to writer for revision.")
    return "rewrite"


# 2. State Machine Compiler
class AegisStateGraphOrchestrator:
    """
    Compiles and executes the AegisCSR Multi-Agent workflow.
    Utilizes LangGraph when available; provides a native Python fallback State Machine
    to guarantee local mock-testing compatibility.
    """
    def __init__(self):
        self.langgraph_app = None
        if LANGGRAPH_AVAILABLE:
            self._compile_langgraph()
            
    def _compile_langgraph(self):
        """Constructs and compiles the state graph using LangGraph framework."""
        try:
            workflow = StateGraph(AgentState)
            
            # Register Nodes
            workflow.add_node("extractor", extract_and_code_data)
            workflow.add_node("writer", write_medical_narrative)
            workflow.add_node("qc_checker", quality_control_check)
            
            # Register Edges
            workflow.set_entry_point("extractor")
            workflow.add_edge("extractor", "writer")
            workflow.add_edge("writer", "qc_checker")
            
            # Add Conditional Edges out of QC checker
            workflow.add_conditional_edges(
                "qc_checker",
                route_after_qc,
                {
                    "approve": END,
                    "rewrite": "writer",
                    "max_revisions_reached": END
                }
            )
            
            self.langgraph_app = workflow.compile()
            logger.info("LangGraph compiled successfully.")
        except Exception as e:
            logger.error(f"Error compiling LangGraph: {e}")
            self.langgraph_app = None

    def execute(self, initial_state: AgentState) -> AgentState:
        """
        Runs the state machine. Falls back to pure Python state loop if LangGraph is missing.
        """
        if self.langgraph_app:
            logger.info("Running pipeline via LangGraph Engine")
            return self.langgraph_app.invoke(initial_state)
            
        logger.info("Running pipeline via Native Python State Machine Fallback")
        state = initial_state.copy()
        state["loop_count"] = state.get("loop_count", 0)
        state["errors"] = state.get("errors", [])
        state["coded_terms"] = state.get("coded_terms", [])
        state["draft_narrative"] = state.get("draft_narrative", "")
        state["compliance_score"] = state.get("compliance_score", 0.0)
        state["is_approved"] = False
        
        # Extractor Node
        ext_res = extract_and_code_data(state)
        state.update(ext_res)
        
        # State Loop
        while True:
            # Writer Node
            writer_res = write_medical_narrative(state)
            state.update(writer_res)
            
            # QC Checker Node
            qc_res = quality_control_check(state)
            state.update(qc_res)
            
            # Evaluate Router Edge
            next_step = route_after_qc(state)
            if next_step == "approve":
                state["is_approved"] = True
                break
            elif next_step == "max_revisions_reached":
                state["is_approved"] = False
                state["errors"].append("SYSTEM_HALT: Maximum revision count reached; review is required.")
                break
            # Else, next_step == "rewrite", state loops back to writer node automatically
            
        return state
