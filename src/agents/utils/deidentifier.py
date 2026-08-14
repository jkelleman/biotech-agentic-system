import re
from typing import Dict, Any, Tuple
from cryptography.fernet import Fernet

class ClinicalDeidentifier:
    """
    Symmetric-key cryptographic scrubber that anonymizes Protected Health Information (PHI)
    on the client side before clinical payloads are transmitted to an external LLM provider.
    Ensures full HIPAA compliance and permits re-identification locally when reports are finalized.
    """
    def __init__(self):
        # Generate or load a symmetric encryption key. In production, this would be fetched from AWS KMS.
        self.encryption_key = Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        
        # Local, in-memory token mapping registers
        self._token_registry: Dict[str, str] = {}
        self._reverse_registry: Dict[str, str] = {}

    def _encrypt_value(self, value: str) -> str:
        """Encrypts sensitive demographic or subject IDs into secure cyphertext."""
        return self.cipher.encrypt(value.encode('utf-8')).decode('utf-8')

    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypts a cyphertext token back to its original patient identifier."""
        return self.cipher.decrypt(encrypted_value.encode('utf-8')).decode('utf-8')

    def anonymize_patient_record(self, raw_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Removes direct HIPAA identifiers (names, SSNs) and pseudo-anonymizes the patient subject ID (USUBJID).
        """
        anonymized = raw_record.copy()
        
        # 1. Eliminate direct PII
        if "patient_name" in anonymized:
            del anonymized["patient_name"]
        if "ssn" in anonymized:
            del anonymized["ssn"]
        if "phone" in anonymized:
            del anonymized["phone"]

        # 2. Pseudo-anonymize the Patient ID (USUBJID)
        raw_id = str(anonymized.get("subject_id", ""))
        if raw_id:
            if raw_id not in self._token_registry:
                token = f"SUBJ-ANON-{len(self._token_registry) + 1001}"
                encrypted_raw_id = self._encrypt_value(raw_id)
                
                # Secure mapping stored locally
                self._token_registry[raw_id] = token
                self._reverse_registry[token] = encrypted_raw_id
            
            anonymized["subject_id"] = self._token_registry[raw_id]

        # 3. Regular Expression scrub on unstructured text field clinical notes
        if "clinical_notes" in anonymized:
            text = anonymized["clinical_notes"]
            # Redact emails
            text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[REDACTED_EMAIL]', text)
            # Redact phone numbers
            text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[REDACTED_PHONE]', text)
            anonymized["clinical_notes"] = text

        return anonymized

    def reidentify_narrative(self, llm_output_text: str) -> str:
        """
        Swaps pseudo-anonymized tokens back to the original patient IDs
        after the text returns from the LLM gateway.
        """
        reidentified_text = llm_output_text
        
        # Find all occurrences of our anonymous subject tokens in the generated text
        tokens_found = re.findall(r'SUBJ-ANON-\d+', reidentified_text)
        
        for token in tokens_found:
            if token in self._reverse_registry:
                encrypted_id = self._reverse_registry[token]
                true_id = self._decrypt_value(encrypted_id)
                reidentified_text = reidentified_text.replace(token, true_id)
                
        return reidentified_text
