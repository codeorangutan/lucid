import os
import logging
from pdf_report_utils import extract_patient_id_from_pdf, save_pdf_to_db

def process_reports_in_folder(reports_dir, db_path='cns_vs_reports.db'):
    logging.basicConfig(level=logging.INFO)
    for filename in os.listdir(reports_dir):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(reports_dir, filename)
            patient_id = extract_patient_id_from_pdf(pdf_path)
            if not patient_id:
                logging.warning(f"Could not extract patient ID from {filename}, skipping.")
                continue
            # Use filename as email_id fallback (or add logic to link to real email)
            email_id = filename.split('.')[0]
            success = save_pdf_to_db(pdf_path, patient_id, email_id, db_path)
            if success:
                logging.info(f"Processed {filename} -> patient_id {patient_id}")
            else:
                logging.error(f"Failed to save {filename} to DB.")

if __name__ == "__main__":
    process_reports_in_folder("reports")
