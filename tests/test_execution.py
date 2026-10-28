from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import logging
import os
import socket
import unittest
from unittest.mock import patch

from src.agents.graph import (
    AegisStateGraphOrchestrator, LANGGRAPH_AVAILABLE, PipelineExecutionError,
)
from src.agents.nodes.validator import quality_control_check
from src.agents.nodes.writer import write_medical_narrative
from src.agents.utils.deidentifier import ClinicalDeidentifier
from src.runtime import RuntimeConfig


def initial_state():
    return {
        "raw_data": {
            "subject_id": "PATIENT-0001", "patient_name": "Fictional Person",
            "age": 54, "sex": "Male", "treatment_arm": "Trial arm A",
            "labs": {"alt_peak_uln": 3.0, "bili_peak_uln": 2.0},
            "clinical_notes": "Person denies nausea but reports vomiting.",
            "adverse_events": [{
                "description": "Acute cholecystitis", "onset_day": 10,
                "severity": "Severe", "relation": "Possibly related",
            }],
        },
        "coded_terms": [], "draft_narrative": "", "compliance_score": 0.0,
        "loop_count": 0, "errors": [], "is_approved": False,
    }


class NativeExecutionTests(unittest.TestCase):
    engine = "native"

    def run_pipeline(self, state=None, **config):
        return AegisStateGraphOrchestrator(
            RuntimeConfig(engine=self.engine, **config)
        ).execute(initial_state() if state is None else state)

    def test_successful_last_pass_is_approved(self):
        final = self.run_pipeline(max_writer_passes=1)
        self.assertTrue(final["is_approved"])
        self.assertEqual(final["status"], "approved")
        self.assertEqual(final["node_history"], [
            "deidentify", "extractor", "writer", "qc_checker", "finalize", "output"
        ])
        self.assertIn("PATIENT-0001", final["draft_narrative"])
        self.assertNotIn("PATIENT-0001", str(final["raw_data"]))
        self.assertNotIn("Person", str(final))
        self.assertNotIn("Phase IIb", final["draft_narrative"])
        self.assertNotIn("Nausea", final["draft_narrative"])

    def test_inputs_and_stale_state_are_not_mutated_or_trusted(self):
        state = initial_state()
        state.update(loop_count=999, errors=["stale"], is_approved=True, draft_narrative="stale")
        original = deepcopy(state)
        result = self.run_pipeline(state)
        self.assertEqual(state, original)
        self.assertEqual(result["loop_count"], 1)
        self.assertEqual(result["errors"], [])

    def test_missing_optional_data_is_not_fabricated(self):
        result = self.run_pipeline({"raw_data": {"subject_id": "S1", "clinical_notes": ""}})
        self.assertTrue(result["is_approved"])
        self.assertIn("Not reported", result["draft_narrative"])
        self.assertNotIn("Placebo", result["draft_narrative"])

    def test_old_age_group_survives_qc(self):
        state = initial_state()
        state["raw_data"]["age"] = 95
        result = self.run_pipeline(state)
        self.assertTrue(result["is_approved"])
        self.assertIn("Age: 90+", result["draft_narrative"])

    def test_failed_qc_halts_with_identical_terminal_metadata(self):
        with patch("src.agents.graph.write_medical_narrative", side_effect=lambda state: {
            "draft_narrative": "Incomplete draft", "loop_count": state["loop_count"] + 1
        }):
            result = self.run_pipeline(max_writer_passes=3)
        self.assertFalse(result["is_approved"])
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["loop_count"], 3)
        self.assertEqual(result["node_history"].count("writer"), 3)
        self.assertIn("SYSTEM_HALT", result["errors"][-1])

    def test_rewrite_can_succeed_on_final_pass(self):
        def writer(state):
            if not state["loop_count"]:
                return {"draft_narrative": "", "loop_count": 1}
            return write_medical_narrative(state)

        with patch("src.agents.graph.write_medical_narrative", side_effect=writer):
            result = self.run_pipeline(max_writer_passes=2)
        self.assertTrue(result["is_approved"])
        self.assertEqual(result["loop_count"], 2)
        self.assertEqual(result["errors"], [])
        self.assertNotIn("Resolved", result["draft_narrative"])

    def test_node_failure_never_falls_back_or_exposes_error_values(self):
        for node in ("extract_and_code_data", "write_medical_narrative", "quality_control_check"):
            with self.subTest(node=node), patch(
                f"src.agents.graph.{node}", side_effect=ValueError("PATIENT-0001 SECRET")
            ), self.assertLogs("AegisCSR.graph", level=logging.ERROR) as logs:
                with self.assertRaises(PipelineExecutionError) as error:
                    self.run_pipeline()
                self.assertNotIn("SECRET", str(error.exception))
                self.assertIsNone(error.exception.__context__)
                self.assertNotIn("PATIENT-0001", str(logs.output))

    def test_output_rejects_foreign_subject_tokens(self):
        def writer(state):
            update = write_medical_narrative(state)
            update["draft_narrative"] += "\nSUBJ-ANON-foreign"
            return update

        with patch("src.agents.graph.write_medical_narrative", side_effect=writer):
            with self.assertLogs("AegisCSR.graph", level=logging.ERROR):
                with self.assertRaises(PipelineExecutionError) as error:
                    self.run_pipeline()
        self.assertEqual(error.exception.node, "output")

    def test_vault_is_destroyed_after_success_and_node_failure(self):
        vault = ClinicalDeidentifier()
        with patch("src.agents.graph.ClinicalDeidentifier", return_value=vault):
            self.run_pipeline()
        self.assertEqual(vault._reverse_registry, {})
        self.assertIsNone(vault._cipher)
        vault = ClinicalDeidentifier()
        with patch("src.agents.graph.ClinicalDeidentifier", return_value=vault):
            with patch("src.agents.graph.write_medical_narrative", side_effect=RuntimeError("SECRET")):
                with self.assertLogs("AegisCSR.graph", level=logging.ERROR):
                    with self.assertRaises(PipelineExecutionError):
                        self.run_pipeline()
        self.assertEqual(vault._token_registry, {})
        self.assertIsNone(vault._cipher)

    def test_concurrent_calls_are_isolated(self):
        orchestrator = AegisStateGraphOrchestrator(RuntimeConfig(engine=self.engine))

        def execute(index):
            state = initial_state()
            state["raw_data"]["subject_id"] = f"SUBJECT-{index:04d}"
            return orchestrator.execute(state)

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(execute, range(16)))
        self.assertEqual(len({result["raw_data"]["subject_id"] for result in results}), 16)
        for index, result in enumerate(results):
            self.assertIn(f"SUBJECT-{index:04d}", result["draft_narrative"])
            self.assertNotIn("SUBJ-ANON-", result["draft_narrative"])

    def test_no_network_even_with_ambient_tracing_enabled(self):
        with patch.dict(os.environ, {"LANGSMITH_TRACING": "true", "LANGCHAIN_TRACING_V2": "true"}):
            with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
                result = self.run_pipeline()
        self.assertTrue(result["is_approved"])

    def test_malformed_records_raise_without_patient_values(self):
        for update in (
            {"subject_id": None}, {"subject_id": ""}, {"age": True}, {"age": "54"}, {"age": None},
            {"labs": []}, {"labs": {"alt_peak_uln": "SECRET"}},
            {"adverse_events": {}}, {"adverse_events": [None]},
            {"adverse_events": [{"description": ""}]},
            {"adverse_events": [{"description": "Nausea", "onset_day": True}]},
            {"sex": None}, {"clinical_notes": 123},
        ):
            state = initial_state()
            state["raw_data"].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError) as error:
                self.run_pipeline(state)
            self.assertNotIn("SECRET", str(error.exception))


@unittest.skipUnless(LANGGRAPH_AVAILABLE, "Install requirements-langgraph.txt for engine parity tests")
class LangGraphExecutionTests(NativeExecutionTests):
    engine = "langgraph"

    def test_native_and_graph_final_states_are_identical(self):
        for limit in (1, 5):
            with patch("src.agents.utils.deidentifier.secrets.token_hex", return_value="a" * 32):
                native = AegisStateGraphOrchestrator(
                    RuntimeConfig(engine="native", max_writer_passes=limit)
                ).execute(initial_state())
                graph = self.run_pipeline(max_writer_passes=limit)
            self.assertEqual(native, graph)

    def test_failed_native_and_graph_final_states_are_identical(self):
        with patch("src.agents.utils.deidentifier.secrets.token_hex", return_value="a" * 32):
            with patch("src.agents.graph.write_medical_narrative", side_effect=lambda state: {
                "draft_narrative": "", "loop_count": state["loop_count"] + 1
            }):
                native = AegisStateGraphOrchestrator(
                    RuntimeConfig(engine="native", max_writer_passes=4)
                ).execute(initial_state())
                graph = self.run_pipeline(max_writer_passes=4)
        self.assertEqual(native, graph)


class EngineSelectionTests(unittest.TestCase):
    def test_auto_fallback_only_when_dependency_is_absent(self):
        with patch("src.agents.graph.LANGGRAPH_AVAILABLE", False):
            orchestrator = AegisStateGraphOrchestrator()
            self.assertIsNone(orchestrator.langgraph_app)
            self.assertTrue(orchestrator.execute(initial_state())["is_approved"])
            with self.assertRaises(RuntimeError):
                AegisStateGraphOrchestrator(RuntimeConfig(engine="langgraph"))

    @unittest.skipUnless(LANGGRAPH_AVAILABLE, "LangGraph not installed")
    def test_graph_compile_errors_are_not_silently_swallowed(self):
        with patch("src.agents.graph.StateGraph", side_effect=RuntimeError("compile failure")):
            with self.assertRaises(RuntimeError):
                AegisStateGraphOrchestrator()

    def test_qc_rejects_wrong_lab_value_and_demographic_substrings(self):
        state = initial_state()
        state["coded_terms"] = []
        state["draft_narrative"] = (
            "PATIENT-0001 154 Female Trial arm A Acute cholecystitis "
            "10 Severe Possibly related ALT 99"
        )
        result = quality_control_check(state)
        self.assertTrue(any("age" in error for error in result["errors"]))
        self.assertTrue(any("sex" in error for error in result["errors"]))
        self.assertTrue(any("Laboratory" in error for error in result["errors"]))
