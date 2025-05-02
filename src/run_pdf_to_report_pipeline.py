"""
Wrapper script to parse a PDF, upload to DB, generate JSON, and create a draft report PDF.
- Modular, robust, and testable (TDD-ready)
- Uses subprocess for isolation and error capture
- Logs actions and errors

Usage:
    python run_pdf_to_report_pipeline.py --pdf <PDF_PATH> --patient_id <PATIENT_ID>

Assumes:
- cognitive_importer.py parses PDF and uploads to DB
- generate_report_json.py generates JSON from DB
- report_pdf_playwright.py generates the report PDF from JSON
"""
import argparse
import subprocess
import sys
import os
import logging

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('run_pdf_to_report_pipeline.log')
    ]
)
logger = logging.getLogger(__name__)

# --- Argument Parsing ---
def parse_args():
    parser = argparse.ArgumentParser(description="Run PDF → DB → JSON → Report pipeline.")
    parser.add_argument('--pdf', required=True, help='Path to the cognitive assessment PDF')
    parser.add_argument('--patient_id', required=True, help='Patient ID (matches DB and JSON)')
    parser.add_argument('--json_script', default='generate_report_json.py', help='Script for JSON generation')
    parser.add_argument('--report_script', default='../report_engine/report_pdf_playwright.py', help='Script for report PDF generation')
    parser.add_argument('--json_dir', default='../json', help='Directory for JSON output')
    parser.add_argument('--dry_run', action='store_true', help='Simulate steps without executing')
    return parser.parse_args()

# --- Step 1: Parse PDF and Upload to DB ---
def parse_pdf_and_upload(pdf_path, patient_id):
    from report_refactor.data_access import patient_exists_in_db
    logger.info(f"[STEP 1] Checking for existing patient in DB: {patient_id}")
    if patient_exists_in_db(patient_id):
        logger.warning(f"Patient {patient_id} already exists in DB. Skipping import to prevent duplication.")
        return False
    logger.info(f"[STEP 1] Parsing PDF and uploading to DB: {pdf_path}")
    # Use module call with correct working directory for relative imports
    cmd = [sys.executable, '-m', 'report_refactor.cognitive_importer', os.path.relpath(pdf_path, 'src')]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd='src')
    if result.returncode != 0:
        logger.error(f"PDF parsing/upload failed: {result.stderr}")
        raise RuntimeError(f"PDF parsing/upload failed: {result.stderr}")
    logger.info(f"PDF parsed and uploaded to DB successfully.")
    return True

# --- Step 2: Generate JSON from DB ---
def generate_json(patient_id, json_script, json_dir):
    logger.info(f"[STEP 2] Generating JSON for patient {patient_id}")
    json_path = os.path.join(json_dir, f"{patient_id}.json")
    # Use module call with correct working directory for relative imports
    cmd = [sys.executable, '-m', 'generate_report.generate_report_json', '--patient-id', patient_id, '--output', json_path]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd='src')
    if result.returncode != 0:
        logger.error(f"JSON generation failed: {result.stderr}")
        raise RuntimeError(f"JSON generation failed: {result.stderr}")
    logger.info(f"JSON generated at {json_path}")
    return json_path

# --- Step 3: Generate Draft Report PDF ---
def generate_report_pdf(patient_id, json_path, report_script, html_template, output_pdf):
    logger.info(f"[STEP 3] Generating draft report PDF for patient {patient_id}")
    # Run Playwright script from project root, with project-root-relative paths
    cmd = [
        sys.executable, report_script,
        '--html', html_template,
        '--json', json_path,
        '--output', output_pdf
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=None)  # cwd=None = project root
    if result.returncode != 0:
        logger.error(f"Report PDF generation failed: {result.stderr}")
        raise RuntimeError(f"Report PDF generation failed: {result.stderr}")
    logger.info(f"Draft report PDF generated at {output_pdf}.")

# --- Main Pipeline ---
def main():
    args = parse_args()
    if args.dry_run:
        logger.info("[DRY RUN] Would parse PDF, generate JSON, and create report PDF.")
        return
    imported = parse_pdf_and_upload(args.pdf, args.patient_id)
    if not imported:
        logger.info(f"Skipping downstream steps for patient {args.patient_id} (already exists in DB). Pipeline halted.")
        return
    # Generate JSON path relative to project root
    json_path = os.path.join('json', f'{args.patient_id}.json')
    generate_json(args.patient_id, args.json_script, args.json_dir)
    html_template = os.path.join('templates', 'report_template_sum_valid.html')
    output_pdf = os.path.join('output', f'report_{args.patient_id}_sum_valid.pdf')
    report_script = os.path.join('src', 'report_engine', 'report_pdf_playwright.py')
    generate_report_pdf(args.patient_id, json_path, report_script, html_template, output_pdf)
    logger.info("Pipeline completed successfully.")

if __name__ == "__main__":
    main()
