import sqlite3
import sys

DB_PATH = 'cns_vs_reports.db'

def delete_reports_for_patient(patient_id, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM cns_vs_reports WHERE patient_id = ?', (patient_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"Deleted {deleted} report(s) for patient_id {patient_id}.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python delete_patient_report.py <patient_id>")
        sys.exit(1)
    delete_reports_for_patient(sys.argv[1])
