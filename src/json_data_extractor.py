"""
Module: json_data_extractor.py
Purpose: Extract all patient data from the database as a structured JSON object for flexible report generation.
"""
import json
import logging
from report_refactor import data_access

def _rows_to_clean_dicts(rows, columns):
    """
    Helper: Convert list of tuples to list of dicts, omitting empty/None fields.
    """
    clean = []
    for row in rows:
        d = {k: v for k, v in zip(columns, row) if v not in (None, "", [])}
        if d:
            clean.append(d)
    return clean


def extract_patient_json(patient_id, db_path=None):
    """
    Extract all relevant patient data from the database as a single JSON-serializable dict.
    This can be used for report generation, API output, or debugging.
    Args:
        patient_id (str): The patient identifier (referrals.id_number).
        db_path (str, optional): Path to the database file. If None, uses default.
    Returns:
        dict: Structured patient data, or None if patient not found.
    """
    from report_refactor import data_access
    import sqlite3
    import os
    try:
        exists = data_access.patient_exists_in_db(patient_id, db_path)
        if not exists:
            logging.warning(f"Patient {patient_id} not found in database.")
            return None
        # Use sqlite3 to get column names for all relevant tables
        if db_path is None:
            from config_utils import get_lucid_data_db
            db_path = get_lucid_data_db()
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # Patient
        cur.execute("PRAGMA table_info(referrals)")
        patient_cols = [x[1] for x in cur.fetchall()]
        # Cognitive scores
        cur.execute("PRAGMA table_info(cognitive_scores)")
        cog_cols = [x[1] for x in cur.fetchall()]
        # Subtests
        cur.execute("PRAGMA table_info(subtest_results)")
        subtest_cols = [x[1] for x in cur.fetchall()]
        # ASRS
        cur.execute("PRAGMA table_info(asrs_responses)")
        asrs_cols = [x[1] for x in cur.fetchall()]
        # DASS
        cur.execute("PRAGMA table_info(dsm_diagnoses)")
        dass_sum_cols = [x[1] for x in cur.fetchall()]
        cur.execute("PRAGMA table_info(dsm_criteria_met)")
        dass_item_cols = [x[1] for x in cur.fetchall()]
        # Epworth
        cur.execute("PRAGMA table_info(epworth_responses)")
        epworth_resp_cols = [x[1] for x in cur.fetchall()]
        cur.execute("PRAGMA table_info(epworth_summary)")
        epworth_sum_cols = [x[1] for x in cur.fetchall()]
        # NPQ
        cur.execute("PRAGMA table_info(npq_domain_scores)")
        npq_score_cols = [x[1] for x in cur.fetchall()]
        cur.execute("PRAGMA table_info(npq_responses)")
        npq_quest_cols = [x[1] for x in cur.fetchall()]
        conn.close()
        # Fetch all data
        all_data = data_access.fetch_all_patient_data(patient_id, db_path)
        # Clean up each section
        patient = _rows_to_clean_dicts([all_data["patient"]], patient_cols)[0] if all_data["patient"] else {}
        cognitive_scores = _rows_to_clean_dicts(all_data["cognitive_scores"], cog_cols)
        subtests = _rows_to_clean_dicts(all_data["subtests"], subtest_cols)
        asrs = _rows_to_clean_dicts(all_data["asrs"], asrs_cols)
        dass_summary = _rows_to_clean_dicts(all_data["dass_summary"], dass_sum_cols)
        dass_items = _rows_to_clean_dicts(all_data["dass_items"], dass_item_cols)
        epworth = {
            "responses": _rows_to_clean_dicts(all_data["epworth"]["responses"], epworth_resp_cols) if isinstance(all_data["epworth"], dict) and "responses" in all_data["epworth"] else [],
            "summary": _rows_to_clean_dicts(all_data["epworth"]["summary"], epworth_sum_cols) if isinstance(all_data["epworth"], dict) and "summary" in all_data["epworth"] else []
        }
        npq_scores = _rows_to_clean_dicts(all_data["npq_scores"], npq_score_cols)
        npq_questions = _rows_to_clean_dicts(all_data["npq_questions"], npq_quest_cols)
        # Compose clean dict
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
    except Exception as e:
        logging.error(f"Error extracting patient data for {patient_id}: {e}")
        return None


def extract_patient_json_str(patient_id, db_path=None, indent=2):
    """
    Same as extract_patient_json, but returns a pretty-printed JSON string.
    """
    data = extract_patient_json(patient_id, db_path)
    if data is None:
        return None
    try:
        return json.dumps(data, indent=indent, default=str)
    except Exception as e:
        logging.error(f"Error serializing patient data to JSON: {e}")
        return None

# Minimal test stub (can be expanded in a test framework)
if __name__ == "__main__":
    import sys
    pid = sys.argv[1] if len(sys.argv) > 1 else input("Enter patient ID: ")
    json_str = extract_patient_json_str(pid)
    if json_str:
        print(json_str)
    else:
        print(f"No data found for patient {pid}.")
