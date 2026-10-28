"""Identical, explicit node boundaries for native and optional LangGraph execution."""

import logging
import math
from contextvars import Context
from copy import deepcopy
from functools import partial
from typing import Callable, Literal, cast

from src.agents.nodes.extractor import extract_and_code_data
from src.agents.nodes.validator import quality_control_check
from src.agents.nodes.writer import write_medical_narrative
from src.agents.state import (
    AgentState, AgentUpdate, ClinicalRecord, WorkflowInput, initialize_state, validate_record,
)
from src.agents.utils.deidentifier import ClinicalDeidentifier
from src.runtime.config import RuntimeConfig

logger = logging.getLogger("AegisCSR.graph")
Route = Literal["approve", "rewrite", "max_revisions_reached"]
Node = Callable[[AgentState], AgentUpdate]


class PipelineNodeError(RuntimeError):
    """Sanitized execution failure; never includes clinical input or draft text."""


def route_after_qc(state: AgentState, settings: RuntimeConfig | None = None) -> Route:
    config = settings or RuntimeConfig()
    # A passing last attempt is still a success.
    if state["compliance_score"] >= config.min_compliance_score and not state["errors"]:
        return "approve"
    if state["loop_count"] >= config.max_writer_passes:
        return "max_revisions_reached"
    return "rewrite"


class AegisStateGraphOrchestrator:
    """No checkpointing, callbacks, external models, or fallback after an engine failure."""

    def __init__(self, config: RuntimeConfig | None = None):
        self.config = config or RuntimeConfig()
        self._nodes: dict[str, Node] = {
            "extractor": extract_and_code_data,
            "writer": write_medical_narrative,
            "qc_checker": quality_control_check,
            "finalize": self._finalize,
        }
        self.langgraph_app = None
        if self.config.engine != "native":
            try:
                from langgraph.graph import END, StateGraph
            except ModuleNotFoundError as exc:
                if exc.name != "langgraph" or self.config.engine == "langgraph":
                    raise
            else:
                workflow = StateGraph(AgentState)
                for name in self._nodes:
                    workflow.add_node(name, partial(self._run_node, name))
                workflow.set_entry_point("extractor")
                workflow.add_edge("extractor", "writer")
                workflow.add_edge("writer", "qc_checker")
                workflow.add_conditional_edges(
                    "qc_checker", partial(route_after_qc, settings=self.config),
                    {"approve": "finalize", "rewrite": "writer",
                     "max_revisions_reached": "finalize"},
                )
                workflow.add_edge("finalize", END)
                self.langgraph_app = workflow.compile()

    def _finalize(self, state: AgentState) -> AgentUpdate:
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

    def _run_node(self, name: str, state: AgentState) -> AgentState:
        try:
            current = state.copy()
            current["status"] = "running"
            update = self._nodes[name](deepcopy(current))
            if not isinstance(update, dict) or set(update) - AgentUpdate.__annotations__.keys():
                raise ValueError("Invalid node update")
            current.update(update)
            score = current["compliance_score"]
            if (isinstance(score, bool) or not isinstance(score, (float, int))
                    or not math.isfinite(score) or not 0 <= score <= 1):
                raise ValueError("Invalid QC score")
            if type(current["loop_count"]) is not int or not 0 <= current["loop_count"] <= self.config.max_writer_passes:
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
            # Explicit execution boundary: do not log exception text, which may contain PHI.
            logger.error("Pipeline node failed: %s", name)
            raise PipelineNodeError(f"Pipeline node failed: {name}") from None

    def execute(self, initial_state: WorkflowInput) -> AgentState:
        """Low-level API for already de-identified input; returns tokenized output."""
        state = initialize_state(initial_state)
        if self.langgraph_app is not None:
            # Isolate inherited callback contexts as well as environment-enabled tracing.
            from langsmith import tracing_context

            app = self.langgraph_app

            def invoke_graph() -> AgentState:
                with tracing_context(enabled=False):
                    return cast(
                        AgentState,
                        app.invoke(state, config={
                            "callbacks": [],
                            "recursion_limit": 2 * self.config.max_writer_passes + 4,
                        }),
                    )

            return Context().run(invoke_graph)
        name = "extractor"
        while True:
            state = self._run_node(name, state)
            if name == "finalize":
                return state
            if name == "qc_checker":
                name = "writer" if route_after_qc(state, self.config) == "rewrite" else "finalize"
            else:
                name = {"extractor": "writer", "writer": "qc_checker"}[name]

    def run_record(self, record: ClinicalRecord) -> AgentState:
        """Privacy gateway: tokenized state machine, then authorized local output restoration.

        The returned output_narrative is sensitive. All other state remains tokenized.
        A new vault per invocation prevents cross-record restoration, including concurrent runs.
        """
        validate_record(record)
        with ClinicalDeidentifier() as deidentifier:
            safe_record = deidentifier.anonymize_patient_record(record)
            state = self.execute({"raw_data": safe_record})
            state["output_narrative"] = deidentifier.reidentify_narrative(state["draft_narrative"])
            state["node_history"] = [*state["node_history"], "restore_output"]
            return state
