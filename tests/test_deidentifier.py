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

    def test_nested_identifier_values_are_scrubbed_without_mutation(self):
        self.raw_record.update({
            "email": "l.vance+trial@clinic.org",
            "date_of_birth": "1972-06-05",
            "contact": {"address": "123 Main Street", "phone": "+1 (212) 555-0199 ext. 42"},
            "adverse_events": [{"description": "Vance has nausea; SSN 000-12-3456"}],
            "clinical_notes": (
                "Leonard Vance (USUBJID-THR902-142), born 1972-06-05, "
                "123 Main Street; l.vance+trial@clinic.org; +1 (212) 555-0199 ext. 42"
            ),
        })
        original = deepcopy(self.raw_record)
        safe = self.deidentifier.anonymize_patient_record(self.raw_record)
        self.assertEqual(self.raw_record, original)
        rendered = str(safe)
        for secret in ("Leonard", "Vance", "1972-06-05", "123 Main Street",
                       "000-12-3456", "l.vance", "212", "USUBJID-THR902-142"):
            self.assertNotIn(secret, rendered)
        restored = self.deidentifier.reidentify_narrative(safe["clinical_notes"])
        self.assertIn(self.raw_record["subject_id"], restored)
        self.assertNotIn("Vance", restored)

    def test_phone_formats_and_email_patterns(self):
        for phone in ("2125550199", "212-555-0199", "(212) 555-0199",
                      "+1 212 555 0199", "+44 020 794 0958", "212.555.0199 x123"):
            with self.subTest(phone=phone):
                safe = self.deidentifier.anonymize_patient_record({
                    "subject_id": "001", "clinical_notes": f"Contact {phone} or a+b@sub.example.org."
                })
                self.assertNotIn(phone, safe["clinical_notes"])
                self.assertIn("[REDACTED_PHONE]", safe["clinical_notes"])
                self.assertIn("[REDACTED_EMAIL]", safe["clinical_notes"])

    def test_subject_references_are_replaced_without_prefix_collisions(self):
        safe = self.deidentifier.anonymize_patient_record({
            "subject_id": "001", "clinical_notes": "Subject 001, not 0012."
        })
        token = safe["subject_id"]
        self.assertEqual(safe["clinical_notes"], f"Subject {token}, not 0012.")
        restored = self.deidentifier.reidentify_narrative(f"{token}, {token}.")
        self.assertEqual(restored, "001, 001.")
        with self.assertRaises(ValueError):
            self.deidentifier.reidentify_narrative(token + "0")

    def test_age_aggregation(self):
        safe = self.deidentifier.anonymize_patient_record({
            "subject_id": "001", "age": 97, "clinical_notes": "97-year-old patient."
        })
        self.assertEqual(safe["age"], "90+")
        self.assertEqual(safe["clinical_notes"], "90+ years old patient.")

    def test_concurrent_assignments_and_exact_restoration(self):
        ids = ["001"] * 50 + [f"subject-{index}" for index in range(50)]
        def anonymize(subject):
            return self.deidentifier.anonymize_patient_record({"subject_id": subject})["subject_id"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            tokens = list(pool.map(anonymize, ids))
        self.assertEqual(len(set(tokens[:50])), 1)
        self.assertEqual(len(set(tokens)), 51)
        for subject, token in zip(ids, tokens):
            self.assertEqual(self.deidentifier.reidentify_narrative(token), subject)
        self.assertTrue(all(isinstance(key, bytes) for key in self.deidentifier._token_registry))

    def test_closed_and_foreign_vault_fail_closed(self):
        token = self.deidentifier.anonymize_patient_record(self.raw_record)["subject_id"]
        with ClinicalDeidentifier() as other:
            with self.assertRaises(ValueError):
                other.reidentify_narrative(token)
        self.deidentifier.close()
        with self.assertRaises(RuntimeError):
            self.deidentifier.reidentify_narrative(token)
        with self.assertRaises(RuntimeError):
            self.deidentifier.anonymize_patient_record(self.raw_record)

    def test_reserved_markers_and_invalid_ids_are_rejected(self):
        for subject in ("", None, 123, "SUBJ-ANON-" + "0" * 32):
            with self.subTest(subject=subject), self.assertRaises(ValueError):
                self.deidentifier.anonymize_patient_record({"subject_id": subject})

    def test_conflicting_nested_subjects_are_rejected(self):
        with self.assertRaises(ValueError):
            self.deidentifier.anonymize_patient_record({
                "subject_id": "001", "nested": {"subject_id": "002"}
            })

    def test_selected_identifier_containing_subject_is_redacted_as_a_whole(self):
        record = {
            "subject_id": "SYN-001",
            "medical_record_number": "MRN-SYN-001",
            "address": "Subject SYN-001 Example Lane",
            "clinical_notes": "SYN-001; MRN-SYN-001; Subject SYN-001 Example Lane.",
        }
        safe = self.deidentifier.anonymize_patient_record(record)
        restored = self.deidentifier.reidentify_narrative(safe["clinical_notes"])
        self.assertEqual(
            restored, "SYN-001; [REDACTED_IDENTIFIER]; [REDACTED_IDENTIFIER].",
        )

    def test_name_inside_unselected_email_does_not_break_email_redaction(self):
        safe = self.deidentifier.anonymize_patient_record({
            "subject_id": "001", "patient_name": "Leonard Vance",
            "clinical_notes": "Contact vance+study@hospital.example or Leonard.Vance@other.example.",
        })
        self.assertEqual(safe["clinical_notes"], "Contact [REDACTED_EMAIL] or [REDACTED_EMAIL].")

if __name__ == "__main__":
    unittest.main()
