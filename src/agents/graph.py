"""Identical local state transitions for LangGraph and native execution."""

import logging
import math
from contextvars import Context
from copy import deepcopy
from typing import Callable, Dict, Literal, Mapping, Optional, cast

from src.agents.nodes.extractor import extract_and_code_data
from src.agents.nodes.validator import quality_control_check
from src.agents.nodes.writer import write_medical_narrative
from src.agents.state import (
    AgentState,
    AgentUpdate,
    ClinicalRecord,
    NodeUpdate,
    WorkflowInput,
    initialize_state,
    validate_record,
)
from src.agents.utils.deidentifier import ClinicalDeidentifier
from src.runtime import RuntimeConfig

try:
    from langgraph.graph import END, StateGraph
except ModuleNotFoundError as exc:
    if exc.name not in ("langgraph", "langgraph.graph"):
        raise
    LANGGRAPH_AVAILABLE = False
    END = None
    StateGraph = None
else:
    LANGGRAPH_AVAILABLE = True

logger = logging.getLogger("AegisCSR.graph")
Route = Literal["approve", "rewrite", "max_revisions_reached"]
Node = Callable[[AgentState], NodeUpdate]


class PipelineExecutionError(RuntimeError):
    """Privacy-safe error boundary; no raw values or original exception attached."""

    def __init__(self, node: str) -> None:
        self.node = node
        super().__init__(f"Pipeline node failed: {node}")


PipelineNodeError = PipelineExecutionError


def route_after_qc(
    state: AgentState, config: Optional[RuntimeConfig] = None
) -> Route:
    settings = config or RuntimeConfig()
    if state["compliance_score"] >= settings.min_compliance_score and not state["errors"]:
        return "approve"
    if state["loop_count"] >= settings.max_writer_passes:
        return "max_revisions_reached"
    return "rewrite"


class AegisStateGraphOrchestrator:
    """Fresh execution state and token vault per call; never fallback on errors."""

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
        if self.config.engine == "langgraph" and not LANGGRAPH_AVAILABLE:
            raise RuntimeError("LangGraph was explicitly requested but is not installed.")
        if self.config.engine != "native" and LANGGRAPH_AVAILABLE:
            try:
                from langgraph.graph import END as graph_end, StateGraph as graph_type
            except ModuleNotFoundError as exc:
                if exc.name != "langgraph":
                    raise
                if self.config.engine == "langgraph":
                    raise RuntimeError(
                        "LangGraph was explicitly requested but is not installed."
                    ) from None
            else:
                global END, StateGraph
                END = graph_end
                if StateGraph is None:
                    StateGraph = graph_type
                self._compile_langgraph()

    def _run_node(self, name: str, node: Node, state: AgentState) -> AgentState:
        failure = None
        try:
            current = deepcopy(state)
            if name not in ("output", "restore_output"):
                current["status"] = "running"
            update = node(deepcopy(current))
            if not isinstance(update, dict) or set(update) - AgentUpdate.__annotations__.keys():
                raise ValueError("Invalid node update")
            current.update(update)
            score = current["compliance_score"]
            if (
                isinstance(score, bool)
                or not isinstance(score, (float, int))
                or not math.isfinite(score)
                or not 0 <= score <= 1
            ):
                raise ValueError("Invalid QC score")
            if (
                type(current["loop_count"]) is not int
                or not 0 <= current["loop_count"] <= self.config.max_writer_passes
            ):
                raise ValueError("Invalid writer pass count")
            if name == "writer" and current["loop_count"] != state["loop_count"] + 1:
                raise ValueError("Writer must increment the pass count exactly once")
            for key in ("errors", "coded_terms", "node_history"):
                items = current.get(key)
                if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
                    raise ValueError("Invalid state list")
            for key in ("draft_narrative", "output_narrative"):
                if not isinstance(current.get(key), str):
                    raise ValueError("Invalid narrative")
            if type(current["is_approved"]) is not bool:
                raise ValueError("Invalid approval flag")
            if current["status"] not in ("running", "approved", "review_required"):
                raise ValueError("Invalid workflow status")
            current["node_history"] = [*state["node_history"], name]
            return current
        except Exception:
            logger.error("Pipeline node failed: %s", name)
            failure = PipelineExecutionError(name)
        raise failure

    def _finalize(self, state: AgentState) -> NodeUpdate:
        approved = route_after_qc(state, self.config) == "approve"
        errors = list(state["errors"])
        if not approved:
            errors.append("SYSTEM_HALT: Maximum revision count reached; review is required.")
        return {
            "is_approved": approved,
            "status": "approved" if approved else "review_required",
            "errors": errors,
            "output_narrative": state["draft_narrative"],
        }

    def _next_node(self, name: str, state: AgentState) -> str:
        if name == "qc_checker":
            return "writer" if route_after_qc(state, self.config) == "rewrite" else "finalize"
        return {"extractor": "writer", "writer": "qc_checker", "finalize": "end"}[name]

    def _compile_langgraph(self) -> None:
        workflow = StateGraph(AgentState)
        for name, node in self._nodes.items():
            workflow.add_node(
                name,
                lambda state, name=name: self._run_node(name, self._nodes[name], state),
            )
        workflow.set_entry_point("extractor")
        workflow.add_edge("extractor", "writer")
        workflow.add_edge("writer", "qc_checker")
        workflow.add_conditional_edges(
            "qc_checker",
            lambda state: route_after_qc(state, self.config),
            {
                "approve": "finalize",
                "rewrite": "writer",
                "max_revisions_reached": "finalize",
            },
        )
        workflow.add_edge("finalize", END)
        self.langgraph_app = workflow.compile()

    def _execute_safe(self, initial_state: WorkflowInput) -> AgentState:
        state = initialize_state(initial_state)
        if self.langgraph_app is not None:
            from langsmith import tracing_context

            def invoke_graph() -> AgentState:
                with tracing_context(enabled=False):
                    return cast(
                        AgentState,
                        self.langgraph_app.invoke(
                            state,
                            config={
                                "callbacks": [],
                                "recursion_limit": 2 * self.config.max_writer_passes + 4,
                            },
                        ),
                    )

            return Context().run(invoke_graph)

        name = "extractor"
        while name != "end":
            state = self._run_node(name, self._nodes[name], state)
            name = self._next_node(name, state)
        return state

    def execute(self, initial_state: Mapping[str, object]) -> AgentState:
        raw_record = initial_state["raw_data"]
        validate_record(raw_record)
        with ClinicalDeidentifier() as deidentifier:
            safe_record = cast(
                ClinicalRecord, deidentifier.anonymize_patient_record(raw_record)
            )
            state = self._execute_safe({"raw_data": safe_record})
            state["node_history"] = ["deidentify", *state["node_history"]]

            def output(current: AgentState) -> NodeUpdate:
                restored = deidentifier.reidentify_narrative(current["draft_narrative"])
                return {"draft_narrative": restored, "output_narrative": restored}

            output_state = self._run_node("output", output, state)
            return output_state

    def run_record(self, record: ClinicalRecord) -> AgentState:
        """Return tokenized state and a separately restored local output narrative."""
        validate_record(record)
        with ClinicalDeidentifier() as deidentifier:
            safe_record = cast(
                ClinicalRecord, deidentifier.anonymize_patient_record(record)
            )
            state = self._execute_safe({"raw_data": safe_record})

            def restore_output(current: AgentState) -> NodeUpdate:
                return {
                    "output_narrative": deidentifier.reidentify_narrative(
                        current["draft_narrative"]
                    )
                }

            return self._run_node("restore_output", restore_output, state)
