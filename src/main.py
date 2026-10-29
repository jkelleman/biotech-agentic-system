import argparse
import logging
from typing import Optional
from src.agents.graph import AegisStateGraphOrchestrator
from src.runtime import RuntimeConfig

logger = logging.getLogger("AegisCSR.main")


def run_pipeline_demo(config: Optional[RuntimeConfig] = None) -> None:
    logger.info("Initializing AegisCSR Multi-Agent Pipeline Demo...")

    # Fictional values that resemble direct identifiers for the local demo.
    raw_patient_payload = {
        "subject_id": "USUBJID-THR902-142",
        "patient_name": "Leonard Vance",
        "ssn": "000-12-3456",
        "phone": "555-019-2831",
        "age": 54,
        "sex": "Male",
        "treatment_arm": "THR-902 10mg Active Dose",
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
        ],
        "clinical_notes": (
            "Patient Vance checked in with investigator via email: l.vance@clinic.org. "
            "Complaining of severe RUQ abdominal pain."
        )
    }

    orchestrator = AegisStateGraphOrchestrator(config)
    final_state = orchestrator.execute({"raw_data": raw_patient_payload})
    # This explicit local output is identifiable and requires a trusted destination.
    print(final_state["draft_narrative"])
    logger.info(f"Pipeline completed. Automated QC threshold met: {final_state['is_approved']}")
    logger.info(f"Final illustrative QC score: {final_state['compliance_score']:.2f}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description="Run the fictional local clinical narrative demo.")
    parser.add_argument("--config", help="Path to validated JSON runtime settings.")
    args = parser.parse_args()
    run_pipeline_demo(RuntimeConfig.from_file(args.config) if args.config else RuntimeConfig())
