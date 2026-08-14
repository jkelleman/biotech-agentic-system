import unittest
from src.agents.graph import AegisStateGraphOrchestrator
from src.agents.state import AgentState

class TestAegisStateGraph(unittest.TestCase):
    def setUp(self):
        self.orchestrator = AegisStateGraphOrchestrator()
        self.initial_state: AgentState = {
            "raw_data": {
                "subject_id": "SUBJ-ANON-1001",
                "age": 54,
                "sex": "Male",
                "treatment_arm": "THR-902 Active Dose",
                "labs": {
                    "alt_peak_uln": 4.2,
                    "bili_peak_uln": 2.2
                },
                "adverse_events": [
                    {
                        "description": "Severe Acute Cholecystitis",
                        "onset_day": 28,
                        "severity": "Severe",
                        "relation": "Possibly Related"
                    }
                ]
            },
            "coded_terms": [],
            "draft_narrative": "",
            "compliance_score": 0.0,
            "loop_count": 0,
            "errors": [],
            "is_approved": False
        }

    def test_pipeline_execution(self):
        final_state = self.orchestrator.execute(self.initial_state)
        
        # Verify state updates
        self.assertTrue(final_state["is_approved"])
        self.assertAlmostEqual(final_state["compliance_score"], 1.0)
        self.assertGreater(final_state["loop_count"], 0)
        self.assertIn("SUBJ-ANON-1001", final_state["draft_narrative"])
        self.assertIn("Cholecystitis Acute", final_state["draft_narrative"])
        
    def test_pipeline_remediation_on_errors(self):
        # Mutate state raw data to trigger a validation error (e.g. omit an AE from the writer)
        # We can mock/stub the writer node behavior if we wanted, but our test_pipeline_execution
        # already demonstrates the full correct state. Let's make sure the validator catches
        # an ALT omission:
        self.initial_state["raw_data"]["labs"]["alt_peak_uln"] = 6.0
        # By default, ALT 6.0 is coded by the extractor, and then written by the writer.
        # But what if the writer output doesn't mention ALT or Alanine?
        # Let's test quality control check specifically:
        from src.agents.nodes.validator import quality_control_check
        test_state = self.initial_state.copy()
        test_state["draft_narrative"] = "Demographics: Patient is SUBJ-ANON-1001, 54, Male on Active Dose. Adverse Event: Severe Acute Cholecystitis."
        # No mention of ALT peak in the draft narrative!
        
        qc_res = quality_control_check(test_state)
        self.assertLess(qc_res["compliance_score"], 1.0)
        self.assertTrue(any("ALT" in err or "Clinical Omission" in err for err in qc_res["errors"]))

if __name__ == "__main__":
    unittest.main()
