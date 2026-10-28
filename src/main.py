"""Local fictional-data demo. Never logs patient records or generated narratives."""

import logging
from pathlib import Path

from src.agents.graph import AegisStateGraphOrchestrator
from src.agents.state import ClinicalRecord
from src.runtime.config import RuntimeConfig

logger = logging.getLogger("AegisCSR.main")


def run_pipeline_demo() -> None:
    config = RuntimeConfig.from_file(Path(__file__).resolve().parents[1] / "config/runtime.json")
    record: ClinicalRecord = {
        "subject_id": "USUBJID-THR902-142",
        "patient_name": "Leonard Vance",
        "ssn": "000-12-3456",
        "phone": "555-019-2831",
        "age": 54,
        "sex": "Male",
        "treatment_arm": "THR-902 10mg Active Dose",
        "labs": {"alt_peak_uln": 4.2, "bili_peak_uln": 2.2},
        "adverse_events": [{
            "description": "Severe Acute Cholecystitis",
            "onset_day": 28,
            "severity": "Severe",
            "relation": "Possibly Related",
        }],
        "clinical_notes": (
            "Patient Vance contacted l.vance@clinic.org. "
            "Denies nausea but reports vomiting."
        ),
    }
    result = AegisStateGraphOrchestrator(config).run_record(record)
    # Explicit demo output only; production callers must govern this sensitive output.
    print(result["output_narrative"])
    logger.info("Workflow completed: %s", result["status"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
    run_pipeline_demo()
