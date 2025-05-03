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
    insert_dsm_criteria_met, insert_epworth_summary, get_or_create_patient, get_session
)
from .asrs_dsm_mapper import DSM5_ASRS_MAPPING
from config_utils import get_lucid_data_db
DB_PATH = get_lucid_data_db()

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
    logger.info(f"Parsed basic info - Patient ID: {patient_id}, Extracted Test Date: '{test_date}', Age: {age}, Language: {language}")
    patient_info = {
        'patient_id': patient_id,
        'test_date': test_date,
        'age': age,
        'language': language
    }

    # --- Stage 2.5: Get or create normalized patient and get patient_fk_id ---
    # Calculate yob from dob if present, else from age and current year
    yob = None
    dob = patient_info.get('dob') if 'dob' in patient_info else None
    if dob:
        try:
            yob = int(str(dob)[:4])  # Assume dob is YYYY-MM-DD or similar
            logger.info(f"Calculated yob from dob: {yob}")
        except Exception as e:
            logger.warning(f"Could not parse yob from dob '{dob}': {e}")
    if yob is None and age:
        try:
            from datetime import datetime
            current_year = datetime.now().year
            yob = current_year - int(age)
            logger.info(f"Calculated yob from age {age} and year {current_year}: {yob}")
        except Exception as e:
            logger.warning(f"Could not calculate yob from age '{age}': {e}")
    if yob is None:
        logger.warning("No DOB or age available to calculate yob; using None.")
    try:
        with get_session() as session:
            patient_fk_id = get_or_create_patient(session, str(patient_id), yob, None, None)
    except Exception as e:
        logger.error(f"Failed to get or create patient in normalized model: {e}")
        return False
    logger.info(f"Using patient_fk_id (system_patient_id): {patient_fk_id}, yob: {yob}")

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
            'validity_index': t[5] if len(t) > 5 else None,
            'patient_id': patient_id,
            'patient_fk_id': patient_fk_id
        }
        for t in raw_score_tuples
    ]
    insert_cognitive_scores(session_id, raw_score_dicts, patient_fk_id=patient_fk_id)

    # Epworth
    epworth_total, epworth_responses = parse_epworth(raw_text, patient_id)
    epworth_response_dicts = [
        {'situation': t[2], 'score': t[3], 'patient_id': patient_id, 'patient_fk_id': patient_fk_id} for t in epworth_responses
    ]
    insert_epworth_responses(session_id, epworth_response_dicts, patient_fk_id=patient_fk_id)
    # Robust: Always sum scores from parsed responses for total
    calculated_total = sum(int(resp['score']) for resp in epworth_response_dicts if resp['score'] is not None)
    # Determine interpretation comment (was previously called severity)
    if calculated_total <= 5:
        interpretation = "Low level of normal daytime sleepiness."
    elif calculated_total <= 10:
        interpretation = "Normal level of daytime sleepiness."
    elif calculated_total <= 12:
        interpretation = "Mild excessive daytime sleepiness."
    elif calculated_total <= 15:
        interpretation = "Moderate excessive daytime sleepiness."
    elif calculated_total <= 24:
        interpretation = "Severe excessive daytime sleepiness."
    else:
        interpretation = "Invalid/unknown Epworth score."
    if calculated_total > 0:
        insert_epworth_summary(session_id, {'total_score': calculated_total, 'interpretation': interpretation, 'patient_id': patient_id, 'patient_fk_id': patient_fk_id}, patient_fk_id=patient_fk_id)
        logger.info(f"Inserted Epworth summary with interpretation: {interpretation}")
    else:
        logger.warning(f"Epworth summary not inserted: no valid scores found for patient {patient_id}, session {session_id}")

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
            'validity_flag': t[6] if len(t) > 6 else True,
            'patient_id': patient_id,
            'patient_fk_id': patient_fk_id
        }
        for t in subtest_tuples
    ]
    insert_subtest_results(session_id, subtest_dicts, patient_fk_id=patient_fk_id)

    # ASRS
    asrs_tuples = parse_asrs_with_bounding_boxes(pdf_path, patient_id)
    question_number_to_text = {int(q_num): asrs_text for (_, asrs_text, q_num) in DSM5_ASRS_MAPPING}
    logger.info(f"ASRS question_number_to_text mapping: {question_number_to_text}")
    asrs_dicts = [
        {
            'question_number': t[1],
            'part': t[2],
            'response': t[3],
            'question_text': question_number_to_text.get(int(t[1]), None),
            'patient_id': patient_id,
            'patient_fk_id': patient_fk_id
        }
        for t in asrs_tuples
    ]
    logger.info(f"ASRS dicts to insert: {asrs_dicts}")
    insert_asrs_responses(session_id, asrs_dicts, patient_fk_id=patient_fk_id)

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
                'domain': t[4] if len(t) > 4 else None,
                'patient_id': patient_id,
                'patient_fk_id': patient_fk_id
            }
            for t in npq_questions
        ]
        npq_domain_scores = extract_npq_domain_scores_from_pdf(pdf_path, npq_pages)
        npq_domain_scores = [
            {
                'domain': t[0],
                'score': t[1],
                'severity': t[2],
                'patient_id': patient_id,
                'patient_fk_id': patient_fk_id
            }
            for t in npq_domain_scores
        ]
    insert_npq_responses(session_id, npq_questions, patient_fk_id=patient_fk_id)
    insert_npq_domain_scores(session_id, npq_domain_scores, patient_fk_id=patient_fk_id)

    # DSM
    logger.info(f"ASRS dicts for DSM extraction: {asrs_dicts}")
    dsm_result = extract_dsm_diagnosis(asrs_dicts, patient_id)
    logger.info(f"DSM extraction result: {dsm_result}")
    if dsm_result:
        # Insert DSM diagnosis
        dsm_diag = {
            'inattentive_criteria_met': dsm_result['inattentive_criteria_met'],
            'hyperactive_criteria_met': dsm_result['hyperactive_criteria_met'],
            'diagnosis': dsm_result['diagnosis'],
            'patient_id': patient_id,
            'patient_fk_id': patient_fk_id
        }
        insert_dsm_diagnosis(session_id, [dsm_diag], patient_fk_id=patient_fk_id)
        # Insert DSM criteria met
        criteria_data = []
        for crit_name, domain, met in dsm_result['dsm_criteria_data']:
            criteria_data.append({
                'dsm_criterion': crit_name,
                'dsm_category': domain,
                'is_met': met,
                'patient_id': patient_id,
                'patient_fk_id': patient_fk_id
            })
        if criteria_data:
            insert_dsm_criteria_met(session_id, criteria_data, patient_fk_id=patient_fk_id)
        logger.info(f"Inserted DSM diagnosis and {len(criteria_data)} criteria met records.")
    else:
        logger.warning(f"No DSM diagnosis extracted for patient {patient_id}.")

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
