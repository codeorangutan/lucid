import logging

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("importer.log", mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__) 
logger.info("Logging initialized: starting cognitive_importer.py")

# Suppress PyPDF2, pdfplumber, pdfminer, and fitz warnings about CropBox
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.getLogger("pdfplumber").setLevel(logging.ERROR)
logging.getLogger("PyPDF2").setLevel(logging.ERROR)
logging.getLogger("fitz").setLevel(logging.ERROR)

import warnings
warnings.filterwarnings("ignore", message="CropBox missing from /Page, defaulting to MediaBox")

import sqlite3
import re
import os
import fitz
import csv # PyMuPDF
from .parsing_helpers import (
    extract_text_blocks, parse_basic_info, parse_cognitive_scores,
    parse_asrs_with_bounding_boxes, parse_epworth, extract_dsm_diagnosis,
    find_npq_pages, extract_npq_questions_pymupdf,
    extract_subtest_section, parse_subtests_new, parse_npq_questions_from_text,
    parse_cognitive_subtests_from_pdf, extract_subtest_data,
    parse_all_cognitive_subtests_from_pdf,
    extract_npq_domain_scores_from_pdf, safe_float
)
from db import (
    create_test_session, insert_cognitive_scores, insert_subtest_results, insert_asrs_responses,
    insert_dsm_diagnosis, insert_epworth_responses, insert_npq_domain_scores, insert_npq_responses,
    insert_dsm_criteria_met, insert_epworth_summary
)
from .asrs_dsm_mapper import DSM5_ASRS_MAPPING

DB_PATH = "cognitive_analysis.db"

# ... rest of the file unchanged ...

def extract_npq_text(pdf_path):
    import pdfplumber
    lines = []
    npq_page_found = False
    
    with pdfplumber.open(pdf_path) as pdf:
        # First identify which page contains the NPQ section
        for i in range(len(pdf.pages)):
            text = pdf.pages[i].extract_text()
            if text and ("NeuroPsych Questionnaire" in text or "Domain Score Severity" in text):
                npq_page_found = True
                logger.debug(f"Found NPQ on page {i+1}")
                # Once we find the NPQ section, extract from this page and a few pages after
                for j in range(i, min(i+5, len(pdf.pages))):
                    page_text = pdf.pages[j].extract_text()
                    if page_text:
                        # Check if we've reached the end of NPQ section
                        if j > i and "NeuroPsych Questionnaire" not in page_text and "Domain Score" not in page_text:
                            # Additional check to see if this page likely contains NPQ content
                            if not any(domain in page_text for domain in ["Attention", "Anxiety", "Depression", "Memory"]):
                                break
                        
                        logger.debug(f"Extracting NPQ from page {j+1}")
                        page_lines = page_text.splitlines()
                        clean_lines = []
                        for line in page_lines:
                            line = line.strip()
                            if line:
                                clean_lines.append(line)
                                
                        lines.extend(clean_lines)
                break
                
    if not npq_page_found:
        # Fallback to scanning a broader range of pages
        with pdfplumber.open(pdf_path) as pdf:
            for i in range(5, min(13, len(pdf.pages))):  # Pages 6-13 (0-indexed)
                text = pdf.pages[i].extract_text()
                if text:
                    logger.debug(f"Fallback: Checking page {i+1} for NPQ content")
                    if "NeuroPsych Questionnaire" in text or "Domain Score Severity" in text:
                        logger.debug(f"Found NPQ content on page {i+1} during fallback")
                    page_lines = text.splitlines()
                    lines.extend(l.strip() for l in page_lines if l.strip())
    
    # Debug the first few lines to help diagnose issues
    logger.debug("First few NPQ extracted lines:")
    for idx, line in enumerate(lines[:20]):
        logger.debug(f"  {idx}: {line}")
        
    return lines

def parse_all_subtests(pdf_path, patient_id, debug=False):
    """
    Table-driven parser for all cognitive subtests using parsing_helpers.parse_all_cognitive_subtests_from_pdf.
    Returns a list of (patient_id, test_name, metric, score, standard, percentile) tuples.
    """
    from .parsing_helpers import parse_all_cognitive_subtests_from_pdf
    return parse_all_cognitive_subtests_from_pdf(pdf_path, patient_id, debug=debug)

# ... rest of the file unchanged ...

def import_pdf_to_db(pdf_path):
    """
    Parses a cognitive report PDF using parsing_helpers and imports the data into the unified SQLAlchemy database.
    Returns True on success, False on failure.
    """
    logger.info(f"Attempting to import PDF data for: {pdf_path}")

    # --- Stage 1: Extract text blocks ---
    lines = extract_text_blocks(pdf_path)
    if not lines:
        logger.error(f"Could not extract any text blocks from {pdf_path}.")
        return False
    raw_text = "\n".join(lines)
    
    # --- Stage 2: Parse Patient Info ---
    patient_info_tuple = parse_basic_info(raw_text)
    if not patient_info_tuple or not patient_info_tuple[0]:
        logger.error(f"Essential patient information (ID) could not be parsed from {pdf_path}.")
        return False
    patient_id, test_date, age, language = patient_info_tuple
    patient_info = {
        'patient_id': patient_id,
        'test_date': test_date,
        'age': age,
        'language': language
    }

    # --- Stage 3: Referral/Session Setup (unchanged) ---
    referral_id = patient_info.get('referral_id')
    if not referral_id:
        from db import Session, Referral
        with Session() as session:
            referral = session.query(Referral).filter_by(id_number=patient_info.get('patient_id')).first()
            if referral:
                referral_id = referral.id
            else:
                from datetime import datetime
                from db import save_referral
                referral_id = save_referral(
                    {'email': patient_info.get('email', ''),
                     'mobile': patient_info.get('mobile', ''),
                     'dob': patient_info.get('dob', ''),
                     'id_number': patient_info.get('patient_id', '')},
                    subject='[Auto-imported]',
                    body='',
                    referrer=None,
                    referrer_email=None,
                    referral_received_time=datetime.now(),
                    referral_confirmed_time=None
                )
    session_date = patient_info.get('test_date')
    from datetime import datetime
    if isinstance(session_date, str):
        try:
            session_date = datetime.strptime(session_date, '%B %d, %Y %H:%M:%S')
        except Exception:
            try:
                session_date = datetime.strptime(session_date, '%Y-%m-%d %H:%M:%S')
            except Exception:
                session_date = datetime.now()
    elif session_date is None:
        session_date = datetime.now()
    session_id = create_test_session(referral_id, session_date, status="parsed")

    # --- Stage 4: Parse and Insert Data ---
    # Cognitive Scores
    raw_score_tuples = parse_cognitive_scores(raw_text, patient_id)
    # Convert tuples to dicts, sanitize only numeric fields
    raw_score_dicts = [
        {
            'domain': t[1],
            'patient_score': safe_float(t[2]),
            'standard_score': safe_float(t[3]),
            'percentile': safe_float(t[4]),
            'validity_index': t[5] if len(t) > 5 else None
        }
        for t in raw_score_tuples
    ]
    insert_cognitive_scores(session_id, raw_score_dicts)

    # Epworth
    epworth_total, epworth_responses = parse_epworth(raw_text, patient_id)
    # Convert tuples to dicts for DB insert
    epworth_response_dicts = [
        {'situation': t[2], 'score': t[3]} for t in epworth_responses
    ]
    insert_epworth_responses(session_id, epworth_response_dicts)
    if epworth_total is not None:
        insert_epworth_summary(session_id, epworth_total)

    # Subtests
    logger.info(f"Parsing cognitive subtests from PDF: {pdf_path}")
    subtest_tuples = parse_all_subtests(pdf_path, patient_id)
    subtest_dicts = [
        {
            'subtest_name': t[1],
            'metric': t[2],
            'score': t[3],
            'standard_score': t[4],
            'percentile': t[5],
            'validity_flag': t[6] if len(t) > 6 else True
        }
        for t in subtest_tuples
    ]
    insert_subtest_results(session_id, subtest_dicts)

    # ASRS
    asrs_tuples = parse_asrs_with_bounding_boxes(pdf_path, patient_id)
    # Build a mapping from question_number to question_text using DSM5_ASRS_MAPPING
    question_number_to_text = {q_num: asrs_text for (_, asrs_text, q_num) in DSM5_ASRS_MAPPING}
    asrs_dicts = [
        {
            'question_number': t[1],
            'part': t[2],
            'response': t[3],
            'question_text': question_number_to_text.get(t[1], None),
            'patient_id': patient_id
        }
        for t in asrs_tuples
    ]
    insert_asrs_responses(session_id, asrs_dicts)

    # NPQ
    npq_pages = find_npq_pages(pdf_path)
    npq_questions = []
    npq_domain_scores = []
    if npq_pages:
        npq_questions = extract_npq_questions_pymupdf(pdf_path, npq_pages)
        npq_questions = [
            {
                'question_number': t[0],
                'question_text': t[1],
                'score': t[2],
                'severity': t[3],
                'domain': t[4] if len(t) > 4 else None
            }
            for t in npq_questions
        ]
        npq_domain_scores = extract_npq_domain_scores_from_pdf(pdf_path, npq_pages)
        npq_domain_scores = [
            {'domain': t[0], 'score': t[1], 'severity': t[2]}
            for t in npq_domain_scores
        ]
    else:
        npq_section_text = '\n'.join([lines[i] for i in npq_pages]) if npq_pages else raw_text
        npq_questions = parse_npq_questions_from_text(npq_section_text)
        npq_questions = [
            {
                'question_number': t[0],
                'question_text': t[1],
                'score': t[2],
                'severity': t[3],
                'domain': None
            }
            for t in npq_questions
        ]
    insert_npq_responses(session_id, npq_questions)
    insert_npq_domain_scores(session_id, npq_domain_scores)

    # DSM Diagnosis
    dsm = extract_dsm_diagnosis(asrs_dicts, patient_id)
    # Robustly normalize dsm to a list of dicts
    if isinstance(dsm, str):
        dsm = [{'diagnosis': dsm}]
    elif isinstance(dsm, dict):
        dsm = [dsm]
    elif isinstance(dsm, list):
        if all(isinstance(x, str) for x in dsm):
            dsm = [{'diagnosis': x} for x in dsm]
        elif all(isinstance(x, dict) for x in dsm):
            pass  # already correct
        else:
            logger.error(f"DSM diagnosis list contains unexpected types: {dsm}")
            dsm = []
    else:
        logger.error(f"DSM diagnosis is unexpected type: {type(dsm)} value: {dsm}")
        dsm = []
    if dsm:
        insert_dsm_diagnosis(session_id, dsm)
        # Robust conversion for dsm_criteria_data
        criteria_data = dsm[0].get('dsm_criteria_data', [])
        if criteria_data and isinstance(criteria_data, list):
            if all(isinstance(x, tuple) for x in criteria_data):
                criteria_data = [
                    {
                        'dsm_criterion': t[0],
                        'dsm_category': t[1],
                        'is_met': t[2],
                    }
                    for t in criteria_data
                ]
        insert_dsm_criteria_met(session_id, criteria_data)

    logger.info(f"Successfully imported all available data for session ID: {session_id}")
    return True

# ... rest of the file unchanged ...

def extract_subtest_section(pdf_path):
    """Extract subtest scores section using pdfplumber"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_text = []
            logger.debug("\nDEBUG: === Raw PDF Tables by Page ===")
            for page_num, page in enumerate(pdf.pages[:3], 1):
                tables = page.extract_tables()

                for table_num, table in enumerate(tables, 1):
                    logger.debug(f"\n=== Page {page_num}, Table {table_num} ===")
                    for row in table:
                        logger.debug([str(cell).strip() if cell else '' for cell in row])
                    logger.debug("-" * 80)
                    # Convert table to text
                    table_text = "\n".join(" ".join(str(cell).strip() if cell else '' for cell in row) for row in table)
                    all_text.append(table_text)
            
            combined_text = "\n".join(all_text)
            logger.debug("\nDEBUG: === Combined Text ===")
            logger.debug(combined_text)
            logger.debug("=" * 80)
            return combined_text
            
    except Exception as e:
        logger.error(f"Error extracting subtest section: {str(e)}")
        return ""

def parse_subtests_new(table, debug=False):
    """
    Parse subtest scores from a table (list of lists), using modular table-based logic.
    Delegates parsing to extract_subtest_data from parsing_helpers.py.
    Returns a list of (metric, score, std, perc) tuples.
    """
    from .parsing_helpers import extract_subtest_data
    import logging
    logger = logging.getLogger(__name__)
    try:
        logger.debug("Parsing subtests from table using extract_subtest_data.")
        subtests = extract_subtest_data(table, debug=debug)
        logger.info(f"Parsed {len(subtests)} subtest results from table.")
        return subtests
    except Exception as e:
        logger.error(f"Error parsing subtests from table: {e}")
        return []

# Main execution block
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python cognitive_importer.py path/to/file.pdf")
    else:
        try:
            import_pdf_to_db(sys.argv[1])
        except Exception as e:
            logger.exception("An error occurred during PDF import:")
            print(f"Error: {e}. Check importer.log for details.")
