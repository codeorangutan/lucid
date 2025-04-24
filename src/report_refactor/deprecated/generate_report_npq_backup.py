import sys
import os
import sqlite3
from cognitive_importer import import_pdf_to_db, parse_basic_info, extract_text_blocks
from report_generator import create_fancy_report  # you'll implement this

#Use is as follows python generate_report.py path/to/yourfile.pdf --import
#This will import the pdf to the database and generate a report

DB_PATH = "cognitive_analysis.db"


def extract_patient_id_from_pdf(pdf_path):
    lines = extract_text_blocks(pdf_path)  # direct function call
    text = "\n".join(lines)
    patient_id, *_ = parse_basic_info(text)
    return patient_id



def fetch_all_patient_data(patient_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    patient = cur.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
    cognitive_scores = cur.execute("SELECT * FROM cognitive_scores WHERE patient_id = ?", (patient_id,)).fetchall()
    subtests = cur.execute("SELECT * FROM subtest_results WHERE patient_id = ?", (patient_id,)).fetchall()
    asrs = cur.execute("SELECT * FROM asrs_responses WHERE patient_id = ?", (patient_id,)).fetchall()
    dass_summary = cur.execute("SELECT * FROM dass21_scores WHERE patient_id = ?", (patient_id,)).fetchall()
    dass_items = cur.execute("SELECT * FROM dass21_responses WHERE patient_id = ?", (patient_id,)).fetchall()
    epworth = cur.execute("SELECT * FROM epworth_scores WHERE patient_id = ?", (patient_id,)).fetchall()
    npq_scores = cur.execute("SELECT * FROM npq_scores WHERE patient_id = ?", (patient_id,)).fetchall()
    npq_questions = cur.execute("SELECT * FROM npq_questions WHERE patient_id = ?", (patient_id,)).fetchall()

    conn.close()
    return {
        "patient": patient,
        "cognitive_scores": cognitive_scores,
        "subtests": subtests,
        "asrs": asrs,
        "dass_summary": dass_summary,
        "dass_items": dass_items,
        "epworth": epworth,
        "npq_scores": npq_scores,
        "npq_questions": npq_questions
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_report.py path/to/file.pdf [--import]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    should_import = "--import" in sys.argv

    if should_import:
        import_pdf_to_db(pdf_path)

    patient_id = extract_patient_id_from_pdf(pdf_path)
    data = fetch_all_patient_data(patient_id)

    output_path = os.path.splitext(pdf_path)[0] + "_report.pdf"
    create_fancy_report(data, output_path)
    print(f"[INFO] Report generated at {output_path}")


if __name__ == "__main__":
    main()
