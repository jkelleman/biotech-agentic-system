import unittest
from src.agents.utils.deidentifier import ClinicalDeidentifier

class TestClinicalDeidentifier(unittest.TestCase):
    def setUp(self):
        self.deidentifier = ClinicalDeidentifier()
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

if __name__ == "__main__":
    unittest.main()
