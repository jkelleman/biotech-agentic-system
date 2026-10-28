import importlib.util
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from unittest.mock import patch

from src.agents.graph import AegisStateGraphOrchestrator, PipelineNodeError, route_after_qc
from src.agents.nodes.validator import quality_control_check
from src.agents.nodes.writer import write_medical_narrative
from src.agents.state import initialize_state
from src.runtime.config import RuntimeConfig

HAS_LANGGRAPH = importlib.util.find_spec("langgraph") is not None
ENGINES = ("native", "langgraph") if HAS_LANGGRAPH else ("native",)


class TestAegisStateGraph(unittest.TestCase):
    def setUp(self):
        self.record = {
            "subject_id": "SUBJECT-001",
            "patient_name": "Leonard Vance",
            "age": 54,
            "sex": "Male",
            "treatment_arm": "THR-902 Active Dose",
            "labs": {"alt_peak_uln": 4.2, "bili_peak_uln": 2.2},
            "adverse_events": [{
                "description": "Severe Acute Cholecystitis",
                "onset_day": 28,
                "severity": "Severe",
                "relation": "Possibly Related",
            }],
            "clinical_notes": "Vance denies nausea but reports vomiting.",
        }
        self.initial_state = {"raw_data": self.record}

    def orchestrator(self, engine, passes=5):
        return AegisStateGraphOrchestrator(RuntimeConfig(engine=engine, max_writer_passes=passes))

    def test_pipeline_execution_and_exact_engine_parity(self):
        original = deepcopy(self.initial_state)
        results = []
        with patch("src.agents.utils.deidentifier.secrets.token_hex", return_value="a" * 32):
            for engine in ENGINES:
                with self.subTest(engine=engine):
                    result = self.orchestrator(engine).execute(self.initial_state)
                    self.assertTrue(result["is_approved"])
                    self.assertEqual(result["status"], "approved")
                    self.assertEqual(result["compliance_score"], 1.0)
                    self.assertEqual(result["node_history"], [
                        "deidentify", "extractor", "writer", "qc_checker", "finalize", "output",
                    ])
                    self.assertIn("Cholecystitis", result["draft_narrative"])
                    self.assertIn("Vomiting", result["draft_narrative"])
                    self.assertNotIn("Nausea", result["draft_narrative"])
                    self.assertEqual(result["output_narrative"], result["draft_narrative"])
                    results.append(result)
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(self.initial_state, original)

    def test_failed_qc_has_identical_halt_state(self):
        results = []
        with patch("src.agents.utils.deidentifier.secrets.token_hex", return_value="a" * 32):
            for engine in ENGINES:
                orchestrator = self.orchestrator(engine, passes=2)
                orchestrator._nodes["qc_checker"] = lambda state: {
                    "compliance_score": 0.1, "errors": ["Source mismatch."]
                }
                results.append(orchestrator.execute(self.initial_state))
        self.assertTrue(all(result == results[0] for result in results))
        result = results[0]
        self.assertFalse(result["is_approved"])
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["loop_count"], 2)
        self.assertEqual(result["node_history"], [
            "deidentify", "extractor", "writer", "qc_checker", "writer",
            "qc_checker", "finalize", "output",
        ])
        self.assertEqual(len(result["errors"]), 2)
        self.assertIn("SYSTEM_HALT", result["errors"][-1])

    def test_passing_final_revision_is_approved(self):
        results = []
        with patch("src.agents.utils.deidentifier.secrets.token_hex", return_value="a" * 32):
            for engine in ENGINES:
                orchestrator = self.orchestrator(engine, passes=2)
                def qc(state):
                    return {"compliance_score": 1.0 if state["loop_count"] == 2 else 0.1,
                            "errors": [] if state["loop_count"] == 2 else ["Missing finding."]}
                orchestrator._nodes["qc_checker"] = qc
                results.append(orchestrator.execute(self.initial_state))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertTrue(results[0]["is_approved"])
        self.assertEqual(results[0]["loop_count"], 2)

    def test_node_exceptions_are_identical_sanitized_and_never_retried(self):
        for engine in ENGINES:
            for name in ("extractor", "writer", "qc_checker", "finalize"):
                with self.subTest(engine=engine, node=name):
                    orchestrator = self.orchestrator(engine)
                    def fail(state):
                        raise RuntimeError("Leonard Vance PHI must never be logged")
                    with patch.dict(orchestrator._nodes, {name: fail}), self.assertLogs("AegisCSR.graph") as logs:
                        with self.assertRaises(PipelineNodeError) as error:
                            orchestrator.execute(self.initial_state)
                    self.assertEqual(str(error.exception), f"Pipeline node failed: {name}")
                    self.assertNotIn("Vance", str(logs.output))
                    self.assertEqual(len(logs.output), 1)

    def test_invalid_node_outputs_are_rejected(self):
        for engine in ENGINES:
            for update in ({"compliance_score": float("nan")}, {"loop_count": True},
                           {"coded_terms": "not a list"}, {"raw_data": {}},
                           {"draft_narrative": None}, {"errors": [123]}):
                with self.subTest(engine=engine, update=update):
                    orchestrator = self.orchestrator(engine)
                    orchestrator._nodes["extractor"] = lambda state: update
                    with self.assertLogs("AegisCSR.graph"), self.assertRaises(PipelineNodeError):
                        orchestrator.execute(self.initial_state)

    def test_output_gateway_is_the_only_restoration_boundary(self):
        original = deepcopy(self.record)
        for engine in ENGINES:
            result = self.orchestrator(engine).run_record(self.record)
            self.assertIn("SUBJECT-001", result["output_narrative"])
            self.assertNotIn("SUBJECT-001", result["draft_narrative"])
            self.assertNotIn("SUBJECT-001", str(result["raw_data"]))
            self.assertNotIn("Vance", str(result))
            self.assertEqual(result["node_history"][-1], "restore_output")
            self.assertTrue(result["raw_data"]["subject_id"].startswith("SUBJ-ANON-"))
        self.assertEqual(original, self.record)

    def test_concurrent_record_runs_are_isolated(self):
        for engine in ENGINES:
            orchestrator = self.orchestrator(engine)
            records = [{**self.record, "subject_id": f"TRIAL-{i:04d}"} for i in range(12)]
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(orchestrator.run_record, records))
            for record, result in zip(records, results):
                self.assertIn(record["subject_id"], result["output_narrative"])
                for other in records:
                    if other != record:
                        self.assertNotIn(other["subject_id"], result["output_narrative"])

    def test_qc_checks_lab_value_not_just_name(self):
        state = initialize_state(self.initial_state)
        state.update(write_medical_narrative(state))
        state["draft_narrative"] += "\nAlanine aminotransferase increased (3.0x ULN)"
        result = quality_control_check(state)
        self.assertLess(result["compliance_score"], 1)
        self.assertTrue(any("Clinical Omission" in error for error in result["errors"]))

    def test_writer_does_not_invent_trial_or_relationship(self):
        state = initialize_state({"raw_data": {"subject_id": "001", "adverse_events": [{"description": "Rash"}]}})
        result = write_medical_narrative(state)["draft_narrative"]
        for fabricated in ("Placebo", "Phase IIb", "MASH", "Unrelated", "Mild", "Resolved"):
            self.assertNotIn(fabricated, result)
        self.assertIn("Not reported", result)

    def test_invalid_record_is_rejected_before_nodes(self):
        for data in ({}, {"subject_id": 1}, {"subject_id": "001", "age": True},
                     {"subject_id": "001", "clinical_notes": None},
                     {"subject_id": "001", "adverse_events": [{}]},
                     {"subject_id": "001", "labs": {"alt_peak_uln": "NaN"}}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.orchestrator("native").execute({"raw_data": data})

    def test_high_score_with_findings_is_not_approval(self):
        state = initialize_state(self.initial_state)
        state.update({"compliance_score": 1.0, "errors": ["Unresolved issue."]})
        self.assertEqual(route_after_qc(state), "rewrite")

    @unittest.skipUnless(HAS_LANGGRAPH, "Optional LangGraph dependency is not installed")
    def test_inherited_tracing_cannot_send_clinical_data(self):
        from langchain_core.tracers.context import tracing_v2_callback_var

        orchestrator = self.orchestrator("langgraph")
        inherited = tracing_v2_callback_var.set(object())
        try:
            with patch.dict(os.environ, {"LANGSMITH_TRACING": "true", "LANGCHAIN_TRACING_V2": "true",
                                         "LANGSMITH_API_KEY": "test-not-a-real-key"}):
                with patch("socket.socket.connect", side_effect=AssertionError("Network access forbidden")):
                    result = orchestrator.execute(self.initial_state)
        finally:
            tracing_v2_callback_var.reset(inherited)
        self.assertTrue(result["is_approved"])

    def test_explicit_native_mode_does_not_import_optional_engine(self):
        with patch("builtins.__import__", wraps=__import__) as imports:
            self.orchestrator("native").execute(self.initial_state)
        self.assertFalse(any(call.args[0].startswith(("langgraph", "langsmith")) for call in imports.call_args_list))

    def test_auto_fallback_only_for_absent_optional_engine(self):
        real_import = __import__
        def absent(name, *args, **kwargs):
            if name == "langgraph.graph":
                raise ModuleNotFoundError("Optional engine missing", name="langgraph")
            return real_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=absent):
            result = AegisStateGraphOrchestrator().execute(self.initial_state)
            self.assertTrue(result["is_approved"])
            with self.assertRaises(RuntimeError):
                self.orchestrator("langgraph")

    @unittest.skipUnless(HAS_LANGGRAPH, "Optional LangGraph dependency is not installed")
    def test_graph_compile_failure_is_not_silently_replayed(self):
        with patch("langgraph.graph.StateGraph.compile", side_effect=RuntimeError("Compile failure")):
            with self.assertRaisesRegex(RuntimeError, "Compile failure"):
                AegisStateGraphOrchestrator()
