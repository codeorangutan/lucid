"""
Script to remove all database entries for a given patient_id that do NOT match a specified session_id.
This is useful for cleaning up duplicate or orphaned sessions for a patient.

Usage:
    python remove_duplicate_sessions.py --patient_id <PATIENT_ID> --session_id <SESSION_ID> [--db <DB_PATH>]

- Only keeps rows where patient_id AND session_id match in all relevant tables.
- Removes all other rows for that patient_id with a different session_id.
- Supports dry run mode for safety.
"""
import argparse
import sqlite3
import sys
import os

def get_lucid_data_db():
    # Try to use the same logic as the rest of the pipeline for DB location
    # 1. Check environment variable
    db_path = os.environ.get('LUCID_DATA_DB')
    if db_path and os.path.exists(db_path):
        return db_path
    # 2. Check default locations (project root or src)
    candidates = [
        os.path.join(os.getcwd(), 'lucid_data.db'),
        os.path.join(os.getcwd(), 'src', 'lucid_data.db'),
        os.path.join(os.path.dirname(__file__), '..', 'lucid_data.db'),
        os.path.join(os.path.dirname(__file__), '..', '..', 'lucid_data.db'),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError('Could not locate lucid_data.db. Please specify with --db or set LUCID_DATA_DB env variable.')

def remove_duplicate_sessions(patient_id, session_id, db_path=None, dry_run=False):
    if db_path is None:
        db_path = get_lucid_data_db()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # List of tables and their session_id/patient_id columns
    tables = [
        ("cognitive_scores", "session_id", "patient_id"),
        ("subtest_results", "session_id", "patient_id"),
        ("asrs_responses", "session_id", "patient_id"),
        ("dsm_diagnoses", "session_id", "patient_id"),
        ("epworth_responses", "session_id", "patient_id"),
        ("epworth_summary", "session_id", "patient_id"),
        ("npq_domain_scores", "session_id", "patient_id"),
        ("npq_responses", "session_id", "patient_id"),
        ("dsm_criteria_met", "session_id", "patient_id"),
        ("referrals", "referral_id", "id_number")  # referrals uses id_number for patient_id and referral_id for session
    ]

    for table, session_col, patient_col in tables:
        # Check if session_col actually exists in the table
        cur.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cur.fetchall()]
        if session_col not in columns:
            print(f"[SKIP] Table {table} does not have column {session_col}, skipping.")
            continue
        # Check for rows to delete
        query = f"SELECT * FROM {table} WHERE {patient_col} = ? AND {session_col} != ?"
        rows = cur.execute(query, (patient_id, session_id)).fetchall()
        if rows:
            print(f"[INFO] {len(rows)} rows in {table} for patient {patient_id} with {session_col} != {session_id} will be removed.")
            if not dry_run:
                del_query = f"DELETE FROM {table} WHERE {patient_col} = ? AND {session_col} != ?"
                cur.execute(del_query, (patient_id, session_id))
        else:
            print(f"[OK] No duplicates in {table} for patient {patient_id}.")

    if not dry_run:
        conn.commit()
        print("[DONE] Duplicate sessions removed.")
    else:
        print("[DRY RUN] No changes made.")
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Remove duplicate sessions for a patient.")
    parser.add_argument("--patient_id", required=True, help="Patient ID to clean up")
    parser.add_argument("--session_id", required=True, help="Session ID to keep")
    parser.add_argument("--db", default=None, help="Path to DB (optional)")
    parser.add_argument("--dry_run", action="store_true", help="Preview deletions without applying them")
    args = parser.parse_args()
    remove_duplicate_sessions(args.patient_id, args.session_id, args.db, args.dry_run)

if __name__ == "__main__":
    main()
