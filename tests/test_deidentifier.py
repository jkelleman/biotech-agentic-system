import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from src.agents.utils.deidentifier import ClinicalDeidentifier

class TestClinicalDeidentifier(unittest.TestCase):
    def setUp(self):
        self.deidentifier = ClinicalDeidentifier()
        self.addCleanup(self.deidentifier.close)
        self.raw_record = {
            "subject_id": "USUBJID-THR902-142",
            "patient_name": "Leonard Vance",
            "ssn": "000-12-3456",
            "phone": "555-019-2831",
            "age": 54,
            "clinical_notes": "Please contact Leonard Vance at l.vance@clinic.org or 555-019-2831."
        }

    def test_anonymization(self):
        safe_record = self.deidentifier.anonymize_patient_record(self.raw_record)
        
        # Verify direct PII is removed
        self.assertNotIn("patient_name", safe_record)
        self.assertNotIn("ssn", safe_record)
        self.assertNotIn("phone", safe_record)
        
        # Verify subject ID has been replaced with a token
        self.assertNotEqual(safe_record["subject_id"], "USUBJID-THR902-142")
        self.assertTrue(safe_record["subject_id"].startswith("SUBJ-ANON-"))
        
        # Verify clinical notes have email and phone redacted
        self.assertNotIn("l.vance@clinic.org", safe_record["clinical_notes"])
        self.assertNotIn("555-019-2831", safe_record["clinical_notes"])
        self.assertIn("[REDACTED_EMAIL]", safe_record["clinical_notes"])
        self.assertIn("[REDACTED_PHONE]", safe_record["clinical_notes"])

    def test_reidentification(self):
        safe_record = self.deidentifier.anonymize_patient_record(self.raw_record)
        anon_id = safe_record["subject_id"]
        
        # Simulate LLM returning a narrative with the anonymized token
        generated_narrative = f"The patient {anon_id} was treated and discharged."
        
        # Reidentify
        restored = self.deidentifier.reidentify_narrative(generated_narrative)
        
        # Original subject ID should be restored
        self.assertIn("USUBJID-THR902-142", restored)
        self.assertNotIn(anon_id, restored)

    def test_selected_identifiers_are_scrubbed_recursively_without_mutation(self):
        record = {
            **self.raw_record,
            "nested": {
                "PatientName": "Leonard Vance",
                "MRN": "MRN-001",
                "visits": [{"notes": "Vance, LEONARD: MRN-001 / USUBJID-THR902-142"}],
            },
            "clinical_notes": "Leonard Vance (Vance) SSN 000-12-3456. USUBJID-THR902-142.",
        }
        original = deepcopy(record)
        safe = self.deidentifier.anonymize_patient_record(record)
        serialized = str(safe)
        for value in ("Leonard", "Vance", "MRN-001", "000-12-3456", record["subject_id"]):
            self.assertNotIn(value.lower(), serialized.lower())
        self.assertIn(safe["subject_id"], safe["clinical_notes"])
        self.assertEqual(record, original)
        self.assertNotIn("MRN", safe["nested"])

    def test_common_phone_formats_and_emails(self):
        for phone in (
            "4155552671", "415-555-2671", "415.555.2671", "415 555 2671",
            "(415) 555-2671", "+1 (415) 555-2671", "+1-415-555-2671",
            "415-555-2671 ext. 123", "4155552671 x123", "+442079460958",
            "+44 20 7946 0958",
        ):
            with self.subTest(phone=phone):
                safe = self.deidentifier.anonymize_patient_record({
                    "subject_id": "S1", "clinical_notes": f"Contact {phone}, a+b@example.co.uk."
                })
                self.assertEqual(safe["clinical_notes"], "Contact [REDACTED_PHONE], [REDACTED_EMAIL].")

    def test_custom_field_and_age_aggregation(self):
        with ClinicalDeidentifier(identifier_fields=["screening_id"]) as deidentifier:
            safe = deidentifier.anonymize_patient_record({
                "subject_id": "S1", "screening_id": "SCREEN-99",
                "clinical_notes": "SCREEN-99", "age": 95,
            })
            self.assertNotIn("screening_id", safe)
            self.assertNotIn("SCREEN-99", safe["clinical_notes"])
            self.assertEqual(safe["age"], "90+")

    def test_unicode_case_variants_cannot_bypass_redaction(self):
        safe = self.deidentifier.anonymize_patient_record({
            "subject_id": "S1", "patient_name": "Ipek", "clinical_notes": "Ipek ıpek İpek"
        })
        self.assertEqual(safe["clinical_notes"], " ".join(["[REDACTED_IDENTIFIER]"] * 3))
        safe = self.deidentifier.anonymize_patient_record({
            "subject_id": "S1", "patient_name": "Straße", "clinical_notes": "Straße STRASSE"
        })
        self.assertEqual(safe["clinical_notes"], " ".join(["[REDACTED_IDENTIFIER]"] * 2))

    def test_thread_safe_stable_and_unpredictable_tokens(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            records = list(executor.map(
                self.deidentifier.anonymize_patient_record,
                [{"subject_id": f"S{i % 10}"} for i in range(200)],
            ))
        tokens = [record["subject_id"] for record in records]
        self.assertEqual(len(set(tokens)), 10)
        for i, token in enumerate(tokens):
            self.assertRegex(token, r"^SUBJ-ANON-[a-f0-9]{32}$")
            self.assertEqual(self.deidentifier.reidentify_narrative(token), f"S{i % 10}")
        self.assertTrue(all(isinstance(key, bytes) for key in self.deidentifier._token_registry))
        self.assertNotIn(b"S1", self.deidentifier._reverse_registry.values())

    def test_vault_isolation_unknown_tokens_and_cleanup(self):
        token = self.deidentifier.anonymize_patient_record({"subject_id": "S1"})["subject_id"]
        with ClinicalDeidentifier() as other:
            with self.assertRaises(ValueError):
                other.reidentify_narrative(token)
            self.assertNotEqual(token, other.anonymize_patient_record({"subject_id": "S1"})["subject_id"])
        self.deidentifier.close()
        self.assertEqual(self.deidentifier._reverse_registry, {})
        with self.assertRaises(RuntimeError):
            self.deidentifier.reidentify_narrative(token)
        with self.assertRaises(RuntimeError):
            self.deidentifier.anonymize_patient_record({"subject_id": "S1"})

    def test_restoration_is_whole_token_and_nonrecursive(self):
        first = self.deidentifier.anonymize_patient_record({"subject_id": "S1"})["subject_id"]
        second = self.deidentifier.anonymize_patient_record({"subject_id": first})["subject_id"]
        self.assertEqual(self.deidentifier.reidentify_narrative(f"{second}, {first}; {first}."), f"{first}, S1; S1.")
        for malformed in (first + "a", first + "-suffix", "SUBJ-ANON-foreign"):
            with self.subTest(token=malformed), self.assertRaises(ValueError):
                self.deidentifier.reidentify_narrative(malformed)

    def test_malformed_data_fails_closed(self):
        for record in ([], {"subject_id": None}, {"subject_id": 123}, {"subject_id": " "}, {"value": object()}):
            with self.subTest(record=record), self.assertRaises(ValueError):
                self.deidentifier.anonymize_patient_record(record)

if __name__ == "__main__":
    unittest.main()
