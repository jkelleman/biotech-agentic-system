import unittest

from src.agents.nodes.extractor import extract_and_code_data
from src.agents.utils.phenotyping import clinical_terms, event_term, lab_value, laboratory_terms


class TestPhenotyping(unittest.TestCase):
    def test_inclusive_thresholds(self):
        for field, threshold in (("alt_peak_uln", 3.0), ("bili_peak_uln", 2.0)):
            for value, expected in ((threshold - 0.0001, 0), (threshold, 1), (threshold + 0.0001, 1)):
                with self.subTest(field=field, value=value):
                    self.assertEqual(len(laboratory_terms({field: value})), expected)
        self.assertEqual(laboratory_terms({}), [])
        self.assertEqual(len(laboratory_terms({"alt_peak_uln": "3.0", "bili_peak_uln": "2"})), 2)

    def test_invalid_labs_fail_explicitly_without_echo(self):
        for value in (None, True, [], {}, "SECRET", "NaN", "inf", float("nan"), -1):
            with self.subTest(value=value), self.assertRaises(ValueError) as error:
                lab_value(value)
            self.assertNotIn("SECRET", str(error.exception))

    def test_whole_words_only(self):
        self.assertEqual(clinical_terms("salt alternative liverwort headaches"), [])
        self.assertIsNotNone(event_term("Patient slipped"))
        self.assertIn("Alanine", clinical_terms("ALT increased")[0])

    def test_negated_historical_and_uncertain_mentions(self):
        for text in (
            "Patient denies nausea", "No nausea or vomiting", "Without headache",
            "Nausea is absent", "Nausea was not reported", "Cholecystitis ruled out",
            "History of nausea", "Family history of cholecystitis",
            "Possible nausea", "Monitor for vomiting", "Rule out cholecystitis",
            "No evidence of liver injury", "Patient is free of nausea",
            "Nausea and vomiting absent", "Nausea, vomiting and headache were denied",
        ):
            with self.subTest(text=text):
                self.assertEqual(clinical_terms(text), [])
                self.assertIsNone(event_term(text))

    def test_clause_boundaries_and_explicit_assertions(self):
        for text in (
            "Denies nausea but reports vomiting.",
            "No nausea. Vomiting occurred.",
            "No nausea; vomiting occurred.",
            "Denies nausea and reports vomiting.",
        ):
            with self.subTest(text=text):
                terms = clinical_terms(text)
                self.assertEqual(len(terms), 1)
                self.assertIn("Vomiting", terms[0])

    def test_pseudo_negation_and_deduplication(self):
        self.assertEqual(len(clinical_terms("Not only nausea, nausea persisted.")), 1)
        self.assertEqual(len(clinical_terms("No change in nausea.")), 1)
        self.assertEqual(len(clinical_terms("Nausea, NAUSEA, nausea")), 1)

    def test_normal_alt_and_chronic_events_are_not_upgraded(self):
        self.assertEqual(clinical_terms("ALT normal"), [])
        self.assertNotIn("Acute", event_term("Chronic cholecystitis"))
        self.assertNotIn("Cholecystitis", event_term("Gallbladder polyp"))

    def test_notes_are_extracted_without_fabricated_diagnosis(self):
        result = extract_and_code_data({
            "raw_data": {
                "subject_id": "S1",
                "clinical_notes": "Patient denies nausea but reports vomiting. ALT elevated.",
                "adverse_events": [{"description": "Liver enzyme abnormality"}],
            }
        })
        self.assertTrue(any("Vomiting" in term for term in result["coded_terms"]))
        self.assertFalse(any("Nausea" in term or "Drug-induced" in term for term in result["coded_terms"]))
