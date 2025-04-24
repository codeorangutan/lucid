import sys
import os
from cognitive_importer import import_pdf_to_db, parse_basic_info, extract_text_blocks
from report_generator import create_fancy_report
from data_access import patient_exists_in_db, fetch_all_patient_data, check_data_completeness, debug_log

#Use is as follows python generate_report.py path/to/yourfile.pdf --import
#This will import the pdf to the database and generate a report

DB_PATH = "cognitive_analysis.db"


def extract_patient_id_from_pdf(pdf_path):
    lines = extract_text_blocks(pdf_path)  # direct function call
    text = "\n".join(lines)
    patient_id, *_ = parse_basic_info(text)
    return patient_id


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_report.py path/to/file.pdf [--import]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    force_import = "--import" in sys.argv

    # Extract patient ID from the PDF
    patient_id = extract_patient_id_from_pdf(pdf_path)
    print(f"[INFO] Processing data for patient ID: {patient_id}")
    
    # Check if the patient data needs to be imported
    if force_import or not patient_exists_in_db(patient_id, DB_PATH):
        print(f"[INFO] Patient {patient_id} data not found in database or force import requested. Importing from PDF...")
        debug_log(f"Triggering import for patient {patient_id}. Force Import: {force_import}, Patient Exists: {patient_exists_in_db(patient_id, DB_PATH)}")
        import_pdf_to_db(pdf_path)
        print(f"[INFO] Import complete for patient {patient_id}")
    else:
        print(f"[INFO] Using existing database data for patient {patient_id}")
        debug_log(f"Skipping import for patient {patient_id}. Force Import: {force_import}, Patient Exists: True")

    # Check data completeness
    completeness = check_data_completeness(patient_id, DB_PATH)
    debug_log(f"Data completeness for patient {patient_id}: {completeness}")
    
    # Check if we need to re-import due to missing essential data
    needs_reimport = not completeness["patient_info"] or not completeness["cognitive_scores"]
    if needs_reimport:
        if not force_import:
            print(f"[WARN] Essential data missing (Patient Info: {completeness['patient_info']}, Cognitive Scores: {completeness['cognitive_scores']}). Re-importing from PDF...")
            debug_log(f"Triggering re-import due to missing essential data for patient {patient_id}.")
            import_pdf_to_db(pdf_path)
            print(f"[INFO] Re-import complete for patient {patient_id}")
        else:
            debug_log(f"Essential data missing but force_import was already true, skipping redundant re-import check for patient {patient_id}.")
    else:
        debug_log(f"Essential data present, no re-import needed for patient {patient_id}.")

    # Now fetch the data (which should be in the database) and generate the report
    data = fetch_all_patient_data(patient_id, DB_PATH)
    
    # Verify that we have the necessary data before proceeding
    if not data["patient"]:
        print(f"[ERROR] No patient data found for ID {patient_id} after import attempt. Check the PDF and database.")
        sys.exit(1)
    
    # Generate the report
    output_path = os.path.splitext(pdf_path)[0] + "_report.pdf"
    create_fancy_report(data, output_path)
    print(f"[INFO] Report generated at {output_path}")


if __name__ == "__main__":
    main()
