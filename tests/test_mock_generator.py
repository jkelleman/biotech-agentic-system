import itertools
import random
import unittest

from src.agents.graph import AegisStateGraphOrchestrator
from src.runtime.config import RuntimeConfig
from src.utils.mock_generator import generate_clinical_records, generate_mock_cases
from tests.benchmark import validate_case


class TestMockClinicalGenerator(unittest.TestCase):
    def test_seeded_generation_is_reproducible_without_global_rng_changes(self):
        state = random.getstate()
        first = list(generate_mock_cases(20, seed=7))
        self.assertEqual(first, list(generate_mock_cases(20, seed=7)))
        self.assertNotEqual(first, list(generate_mock_cases(20, seed=8)))
        self.assertEqual(state, random.getstate())

    def test_large_volume_is_lazy_and_subject_ids_are_unique(self):
        stream = generate_clinical_records(1_000_000, seed=11)
        first = list(itertools.islice(stream, 100))
        self.assertEqual(len({record["subject_id"] for record in first}), 100)
        self.assertEqual(next(stream)["subject_id"], "SYN-11-00000100")
        self.assertEqual(list(generate_clinical_records(0)), [])

    def test_phi_variations_clinical_oracle_and_restoration(self):
        orchestrator = AegisStateGraphOrchestrator(RuntimeConfig(engine="native"))
        cases = list(generate_mock_cases(70, seed=2026, note_repetitions=3))
        phones = {case.record["phone"] for case in cases[:7]}
        self.assertEqual(len(phones), 7)
        for case in cases:
            with self.subTest(subject=case.record["subject_id"]):
                result = orchestrator.run_record(case.record)
                validate_case(case, result)
                self.assertIn(".example.invalid", case.record["email"])
                self.assertTrue(case.record["ssn"].startswith("000-"))
        self.assertEqual(
            {float(case.record["labs"]["alt_peak_uln"]) for case in cases},
            {0, 2.99, 3, 3.01, 6.2},
        )

    def test_note_volume_changes_text_not_clinical_ground_truth(self):
        small = next(generate_mock_cases(1, note_repetitions=1))
        large = next(generate_mock_cases(1, note_repetitions=20))
        self.assertGreater(len(large.record["clinical_notes"]), len(small.record["clinical_notes"]) * 5)
        self.assertEqual(small.expected_terms, large.expected_terms)
        self.assertEqual(large.record["clinical_notes"].count("Patient denies nausea"), 20)

    def test_invalid_settings_are_rejected_immediately(self):
        for kwargs in ({"count": -1}, {"count": True}, {"count": 1.5},
                       {"seed": True}, {"note_repetitions": 0}, {"note_repetitions": 1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                generate_clinical_records(**kwargs)
