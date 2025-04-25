import re
import os
import sqlite3
import logging
from typing import Optional
import PyPDF2
from config_utils import get_cns_vs_reports_db

def extract_patient_id_from_pdf(pdf_path: str) -> Optional[str]:
    """Extracts the patient ID from a CNSVS PDF report. Returns the patient ID as a string, or None if not found."""
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
        # Log the full path and existence for debugging
        logging.warning(f"[PDF DEBUG] Checking path: {pdf_path} Exists: {os.path.exists(pdf_path)} Size: {os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 'N/A'}")
        # Log the first 500 characters for debugging
        logging.warning(f"[PDF DEBUG] Extracted text (first 500 chars):\n{text[:500]}")
        # More robust regex: allow for any whitespace and possible line breaks
        match = re.search(r"Patient\s*ID\s*[:：]\s*(\d+)", text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1)
        else:
            return None
    except Exception as e:
        logging.error(f"Error extracting patient ID from {pdf_path}: {e}")
        return None

def save_pdf_to_db(pdf_path: str, patient_id: str, email_id: str, db_path: str = None) -> bool:
    """Stores the PDF and metadata in the database. Returns True if successful."""
    if db_path is None:
        db_path = get_cns_vs_reports_db()
    try:
        with open(pdf_path, 'rb') as f:
            pdf_blob = f.read()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cns_vs_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT,
                email_id TEXT,
                filename TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pdf_data BLOB
            )
        ''')
        cursor.execute(
            'INSERT INTO cns_vs_reports (patient_id, email_id, filename, pdf_data) VALUES (?, ?, ?, ?)',
            (patient_id, email_id, os.path.basename(pdf_path), pdf_blob)
        )
        conn.commit()
        conn.close()
        logging.info(f"Stored PDF {pdf_path} for patient {patient_id} in DB.")
        return True
    except Exception as e:
        logging.error(f"Error saving PDF {pdf_path} to DB: {e}")
        return False
