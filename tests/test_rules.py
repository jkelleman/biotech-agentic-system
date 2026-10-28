import unittest

from src.agents.utils.rules import affirmed_terms, lab_findings, validate_labs


class TestClinicalRules(unittest.TestCase):
    def test_negation_and_clause_boundaries(self):
        examples = (
            ("Patient denies nausea.", []),
            ("No nausea or vomiting.", []),
            ("Without headache; nausea is absent.", []),
            ("Possible nausea. Family history of vomiting.", []),
            ("Nausea was ruled out.", []),
            ("Nausea not ruled out.", []),
            ("Nausea and vomiting were denied.", []),
            ("Nausea is possible.", []),
            ("Denies nausea but reports vomiting.", ["Vomiting"]),
            ("No headache. Patient developed nausea.", ["Nausea"]),
            ("No nausea, reports vomiting.", ["Vomiting"]),
            ("Not only nausea but vomiting.", ["Nausea", "Vomiting"]),
        )
        for text, expected in examples:
            with self.subTest(text=text):
                self.assertEqual([term.rsplit(": ", 1)[1] for term in affirmed_terms(text)], expected)

    def test_word_boundaries_and_deduplication(self):
        self.assertEqual(affirmed_terms("alternative healthy salt altered ALTitude"), [])
        self.assertEqual(len(affirmed_terms("Nausea and NAUSEA; nausea.")), 1)
        self.assertEqual(len(affirmed_terms("nausea, vomiting, headache")), 3)

    def test_no_invented_lab_abnormality_or_diagnostic_specificity(self):
        self.assertEqual(affirmed_terms("ALT normal. Liver enzymes were normal."), [])
        self.assertEqual(affirmed_terms("No elevated ALT."), [])
        self.assertEqual(affirmed_terms("ALT measured today."), [])
        self.assertEqual(affirmed_terms("Liver enzymes increased."),
                         ["Investigations: Hepatic enzymes increased"])
        self.assertEqual(affirmed_terms("Elevated ALT."),
                         ["Investigations: Alanine aminotransferase increased"])
        self.assertEqual(affirmed_terms("Cholecystitis."),
                         ["Gastrointestinal disorders: Cholecystitis"])

    def test_long_note_deduplicates_without_losing_negation_scope(self):
        text = ("Patient denies nausea but reports vomiting. " * 5000)
        self.assertEqual(affirmed_terms(text), ["Gastrointestinal disorders: Vomiting"])

    def test_threshold_boundaries(self):
        for field, threshold in (("alt_peak_uln", 3), ("ast_peak_uln", 3), ("bili_peak_uln", 2)):
            with self.subTest(field=field):
                self.assertEqual(lab_findings({field: threshold - 0.001}), [])
                self.assertEqual(len(lab_findings({field: threshold})), 1)
                self.assertEqual(len(lab_findings({field: str(threshold + 0.001)})), 1)
        self.assertEqual(lab_findings({}), [])

    def test_invalid_labs_fail_explicitly(self):
        for value in (True, None, "", "3x ULN", float("nan"), "inf", -1, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_labs({"alt_peak_uln": value})
        with self.assertRaises(ValueError):
            validate_labs([])
