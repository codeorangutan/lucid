import sqlite3
import sys

DB_PATH = 'cns_vs_reports.db'

def query_reports_for_patient(patient_id, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, patient_id, email_id, filename, created_at FROM cns_vs_reports WHERE patient_id = ?', (patient_id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        print(f"No reports found for patient_id {patient_id}.")
    else:
        print(f"Reports for patient_id {patient_id}:")
        for row in rows:
            print(f"ID: {row[0]}, Patient ID: {row[1]}, Email ID: {row[2]}, Filename: {row[3]}, Created At: {row[4]}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python query_patient_reports.py <patient_id>")
        sys.exit(1)
    query_reports_for_patient(sys.argv[1])
