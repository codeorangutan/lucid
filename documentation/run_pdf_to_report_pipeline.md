# Pipeline Wrapper Script Documentation

## File: `src/run_pdf_to_report_pipeline.py`

### Overview
This script provides a robust, modular wrapper to automate the following pipeline:

1. **Parse a cognitive assessment PDF and upload structured data to the database.**
2. **Generate a JSON file for a specified patient from the database.**
3. **Produce a draft PDF report using the generated JSON and the report engine.**

Each step leverages existing scripts in the codebase, ensuring no duplication and adherence to DRY and ETC principles.

---

## Usage

```bash
python src/run_pdf_to_report_pipeline.py --pdf <PDF_PATH> --patient_id <PATIENT_ID>
```

### Optional Arguments
- `--json_script`: Specify the JSON generation script (default: `generate_report_json.py`)
- `--report_script`: Specify the report generation script (default: `../report_engine/report_pdf_playwright.py`)
- `--json_dir`: Directory for JSON output (default: `../json`)
- `--dry_run`: Simulate steps without executing

---

## Pipeline Steps

### 1. Parse PDF and Upload to DB
- Calls `report_refactor.cognitive_importer` as a module.
- Expects the PDF path as argument.
- On success, the database is updated with structured patient data.

### 2. Generate JSON from DB
- Calls the specified JSON generation script (default: `generate_report_json.py`).
- Expects the patient ID and output path as arguments.
- Produces a JSON file in the designated directory.

### 3. Generate Draft Report PDF
- Calls the specified report script (default: `report_pdf_playwright.py`).
- Expects the JSON file as argument.
- Produces a formatted PDF draft report.

---

## Logging & Error Handling
- All steps log actions and errors to both console and `run_pdf_to_report_pipeline.log`.
- The script raises exceptions and halts on fatal errors for transparency and debugging.

---

## Test-Driven Development (TDD) & Modularity
- Each step is implemented as a separate function for easy testing and extension.
- The script can be run in `--dry_run` mode for safe validation.

---

## Example
```bash
python src/run_pdf_to_report_pipeline.py --pdf ./40436_comprehensive.pdf --patient_id 40436
```

---

## Change Log
- v1.0: Initial version. Automates PDF → DB → JSON → Report pipeline.

---

## Author & Maintenance
- Script and documentation generated with assistance from Cascade AI and the Codeium engineering team.
- For updates or issues, contact the project maintainer.
