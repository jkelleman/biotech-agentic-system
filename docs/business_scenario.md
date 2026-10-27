# Demonstration Scenario

## Intended use

AegisCSR explores how a structured clinical-trial record could be transformed into a draft safety narrative. The example uses a fictional Phase IIb MASH trial and an invented patient record. It is a software demonstration, not a clinical recommendation or a validated reporting workflow.

## Example record

The built-in record represents a fictional participant in a THR-beta agonist trial. It includes age, sex, treatment arm, an adverse event, and peak ALT and bilirubin values expressed as multiples of the upper limit of normal. The code uses these fields to produce a template narrative and exercise basic text-presence checks.

The scenario is deliberately small. It does not represent a complete CDISC dataset, capture a full adverse-event chronology, or include all information needed for a clinical safety narrative.

## Potential operational value

Structured extraction and templating may help reduce repetitive drafting work, but this repository does not measure time savings, cost, error rates, or submission timelines. Any business case should be evaluated on representative, appropriately governed data, with predefined measures and qualified clinical review.

## Data use

The demonstration data are defined in `src/main.py`; no external dataset is included. For a public CDISC sample-data source and the current integration limitations, see the [README](../README.md#public-sample-data).
