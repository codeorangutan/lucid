import sys
import os
from .report_generator import create_fancy_report
from report_refactor.data_access import patient_exists_in_db, fetch_all_patient_data, check_data_completeness, debug_log
from db import Referral, get_session
from config_utils import get_lucid_data_db

def extract_patient_id_from_pdf(pdf_path):
    from report_refactor.cognitive_importer import parse_basic_info, extract_text_blocks
    lines = extract_text_blocks(pdf_path)
    text = "\n".join(lines)
    patient_id, *_ = parse_basic_info(text)
    return patient_id

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate cognitive/ADHD report from database or PDF.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--patient-id', type=str, help='Patient ID to generate report for (preferred)')
    group.add_argument('--referral-id', type=str, help='Referral ID to generate report for (will resolve to patient_id)')
    group.add_argument('--pdf', type=str, help='Path to PDF to import and generate report')
    parser.add_argument('--import', dest='force_import', action='store_true', help='Force import from PDF (if using --pdf)')
    parser.add_argument('--output', type=str, help='Output PDF path (default: auto-named)')
    args = parser.parse_args()

    # Determine patient_id
    patient_id = None
    pdf_path = None
    if args.patient_id:
        patient_id = args.patient_id
    elif args.referral_id:
        # Fetch patient_id from referral_id using DB
        session = get_session(DB_PATH)
        referral = session.query(Referral).filter_by(id=args.referral_id).first()
        if not referral:
            print(f"[ERROR] No referral found for ID {args.referral_id}")
            sys.exit(1)
        patient_id = referral.id_number
        session.close()
    elif args.pdf:
        pdf_path = args.pdf
        from report_refactor.cognitive_importer import import_pdf_to_db
        patient_id = extract_patient_id_from_pdf(pdf_path)
    else:
        print("[ERROR] Must specify --patient-id, --referral-id, or --pdf")
        sys.exit(1)

    debug_log(f"Processing report for patient_id: {patient_id}")

    # --- Temporarily Comment Out PDF Logic ---
    # if pdf_path:
    #     force_import = args.force_import
    #     if force_import or not patient_exists_in_db(patient_id, DB_PATH): # Note: DB_PATH was used here, might need fixing later if uncommented
    #         print(f"[INFO] Importing PDF for patient {patient_id}...")
    #         # Ensure import_pdf_to_db uses the correct path if uncommented
    #         # from report_refactor.cognitive_importer import import_pdf_to_db
    #         import_pdf_to_db(pdf_path) # This import might be the culprit
    #     else:
    #         print(f"[INFO] Using existing DB data for patient {patient_id}")
    #     # Optionally check completeness and re-import if needed
    #     completeness = check_data_completeness(patient_id, DB_PATH) # Note: DB_PATH was used here
    #     needs_reimport = not completeness["patient_info"] or not completeness["cognitive_scores"]
    #     if needs_reimport and not force_import:
    #         print(f"[WARN] Essential data missing. Re-importing PDF...")
    #         import_pdf_to_db(pdf_path)
    # ----------------------------------------

    # Fetch all data from DB
    correct_db_path = get_lucid_data_db() # Get fresh path directly from config
    print(f"DEBUG: Value of DB_PATH before calling fetch_all_patient_data: {correct_db_path}")
    data = fetch_all_patient_data(patient_id, correct_db_path) # Pass the fresh path
    if not data["patient"]:
        print(f"[ERROR] No patient data found for ID {patient_id}.")
        sys.exit(1)
    # Output path
    if args.output:
        output_path = args.output
    elif pdf_path:
        output_path = os.path.splitext(pdf_path)[0] + "_report.pdf"
    else:
        output_path = f"report_{patient_id}.pdf"
    create_fancy_report(data, output_path)
    print(f"[INFO] Report generated at {output_path}")

if __name__ == "__main__":
    main()
