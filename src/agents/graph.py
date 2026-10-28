"""Identical local state transitions for LangGraph and native execution."""

import logging
from typing import Callable, Dict, Mapping, Optional, cast

from src.agents.nodes.extractor import extract_and_code_data
from src.agents.nodes.validator import quality_control_check
from src.agents.nodes.writer import write_medical_narrative
from src.agents.state import AgentState, ClinicalRecord, NodeUpdate
from src.agents.utils.deidentifier import ClinicalDeidentifier
from src.agents.utils.validation import validate_record
from src.runtime import RuntimeConfig

try:
    from langgraph.graph import END, StateGraph
except ModuleNotFoundError as exc:
    if exc.name not in ("langgraph", "langgraph.graph"):
        raise
    LANGGRAPH_AVAILABLE = False
else:
    LANGGRAPH_AVAILABLE = True

logger = logging.getLogger("AegisCSR.graph")
Node = Callable[[AgentState], NodeUpdate]


class PipelineExecutionError(RuntimeError):
    """Privacy-safe error boundary; no raw values or original exception attached."""

    def __init__(self, node: str) -> None:
        self.node = node
        super().__init__(f"Pipeline failed at node '{node}'; no output released.")


def route_after_qc(state: AgentState, config: Optional[RuntimeConfig] = None) -> str:
    config = config or RuntimeConfig()
    if state["compliance_score"] >= config.min_compliance_score and not state["errors"]:
        return "approve"
    if state["loop_count"] >= config.max_writer_passes:
        return "max_revisions_reached"
    return "rewrite"


class AegisStateGraphOrchestrator:
    """Fresh execution state and token vault per call; never fallback on errors."""

    _EDGES = {"extractor": "writer", "writer": "qc_checker", "finalize": "end"}

    def __init__(self, config: Optional[RuntimeConfig] = None) -> None:
        self.config = config or RuntimeConfig()
        if self.config.engine == "langgraph" and not LANGGRAPH_AVAILABLE:
            raise RuntimeError("LangGraph was explicitly requested but is not installed.")
        self._nodes: Dict[str, Node] = {
            "extractor": extract_and_code_data,
            "writer": write_medical_narrative,
            "qc_checker": quality_control_check,
            "finalize": self._finalize,
        }
        self.langgraph_app = None
        if self.config.engine != "native" and LANGGRAPH_AVAILABLE:
            self._compile_langgraph()

    @staticmethod
    def _run_node(name: str, node: Node, state: AgentState) -> NodeUpdate:
        try:
            update = node(state)
            update["node_history"] = [*state.get("node_history", []), name]
            return update
        except Exception:
            # Do not log exceptions/tracebacks: upstream messages can contain PHI.
            logger.error("Pipeline node failed: %s", name)
        raise PipelineExecutionError(name) from None

    def _finalize(self, state: AgentState) -> NodeUpdate:
        approved = route_after_qc(state, self.config) == "approve"
        errors = list(state["errors"])
        if not approved:
            errors.append("SYSTEM_HALT: Maximum revision count reached; review is required.")
        return {
            "is_approved": approved,
            "status": "approved" if approved else "review_required",
            "errors": errors,
        }

    def _next_node(self, name: str, state: AgentState) -> str:
        if name == "qc_checker":
            return "writer" if route_after_qc(state, self.config) == "rewrite" else "finalize"
        return self._EDGES[name]

    def _compile_langgraph(self) -> None:
        workflow = StateGraph(AgentState)
        for name, node in self._nodes.items():
            workflow.add_node(
                name,
                lambda state, name=name, node=node: self._run_node(name, node, state),
            )
        workflow.set_entry_point("extractor")
        for source, target in self._EDGES.items():
            workflow.add_edge(source, END if target == "end" else target)
        workflow.add_conditional_edges(
            "qc_checker",
            lambda state: self._next_node("qc_checker", state),
            {"writer": "writer", "finalize": "finalize"},
        )
        # No persistence, callbacks, remote models, or external tools.
        self.langgraph_app = workflow.compile()

    def execute(self, initial_state: Mapping[str, object]) -> AgentState:
        # Validation and privacy gateway run before either engine sees a record.
        raw_record = validate_record(initial_state["raw_data"])
        with ClinicalDeidentifier() as deidentifier:
            safe_record = cast(ClinicalRecord, deidentifier.anonymize_patient_record(raw_record))
            state: AgentState = {
                "raw_data": safe_record,
                "coded_terms": [],
                "draft_narrative": "",
                "compliance_score": 0.0,
                "loop_count": 0,
                "errors": [],
                "is_approved": False,
                "status": "running",
                "node_history": ["deidentify"],
            }
            if self.langgraph_app is not None:
                # Disable ambient LangSmith tracing, even if configured by the host.
                from langsmith import tracing_context

                with tracing_context(enabled=False):
                    state = self.langgraph_app.invoke(
                        state,
                        config={"recursion_limit": 2 * self.config.max_writer_passes + 4},
                    )
            else:
                name = "extractor"
                while name != "end":
                    state.update(self._run_node(name, self._nodes[name], state))
                    name = self._next_node(name, state)

            def output(current: AgentState) -> NodeUpdate:
                return {"draft_narrative": deidentifier.reidentify_narrative(current["draft_narrative"])}

            state.update(self._run_node("output", output, state))
            return state
