import argparse
import subprocess
import logging
import sys
import os


def parse_args():
    parser = argparse.ArgumentParser(description="Utility to delete a patient and run PDF-to-report pipeline.")
    parser.add_argument(
        "--patient_id",
        type=int,
        required=True,
        help="Patient ID to process (e.g., --patient_id 6888)",
    )
    parser.add_argument(
        "--inputs_dir",
        type=str,
        default="inputs",
        help="Directory where input PDFs are stored (default: inputs)",
    )
    return parser.parse_args()


def run_command(command, cwd=None):
    logging.info(f"Running: {' '.join(command)}")
    try:
        result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
        logging.info(result.stdout)
        if result.stderr:
            logging.warning(result.stderr)
        return result.returncode
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {' '.join(command)}")
        logging.error(e.stdout)
        logging.error(e.stderr)
        return e.returncode


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    args = parse_args()
    patient_id = args.patient_id
    inputs_dir = args.inputs_dir

    # Step 1: Delete patient
    delete_cmd = [
        sys.executable,
        os.path.join("utilities", "delete_patient.py"),
        str(patient_id),
        "--json",
    ]
    rc1 = run_command(delete_cmd)
    if rc1 != 0:
        logging.error("Aborting due to failure in delete_patient.py")
        sys.exit(rc1)

    # Step 2: Run PDF to report pipeline
    pdf_path = os.path.join(inputs_dir, f"{patient_id}.pdf")
    if not os.path.exists(pdf_path):
        logging.error(f"PDF not found: {pdf_path}")
        sys.exit(1)
    pipeline_cmd = [
        sys.executable,
        os.path.join("src", "run_pdf_to_report_pipeline.py"),
        "--pdf", pdf_path,
        "--patient_id", str(patient_id),
    ]
    rc2 = run_command(pipeline_cmd)
    if rc2 != 0:
        logging.error("Pipeline failed.")
        sys.exit(rc2)
    logging.info("Completed successfully.")


if __name__ == "__main__":
    main()
