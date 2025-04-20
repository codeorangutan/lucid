import sqlite3
import re
import os
import fitz
import csv # PyMuPDF
from parsing_helpers import (
    extract_text_blocks, parse_basic_info, parse_cognitive_scores,
    parse_asrs_with_bounding_boxes, parse_epworth, extract_dsm_diagnosis,
    find_npq_pages, extract_npq_questions_pymupdf,
    extract_subtest_section, parse_subtests_new
)
from report_parser import parse_complete_cognitive_report
import logging

DB_PATH = "cognitive_analysis.db"
logger = logging.getLogger(__name__)

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
                print(f"[DEBUG] Found NPQ on page {i+1}")
                # Once we find the NPQ section, extract from this page and a few pages after
                for j in range(i, min(i+5, len(pdf.pages))):
                    page_text = pdf.pages[j].extract_text()
                    if page_text:
                        # Check if we've reached the end of NPQ section
                        if j > i and "NeuroPsych Questionnaire" not in page_text and "Domain Score" not in page_text:
                            # Additional check to see if this page likely contains NPQ content
                            if not any(domain in page_text for domain in ["Attention", "Anxiety", "Depression", "Memory"]):
                                break
                        
                        print(f"[DEBUG] Extracting NPQ from page {j+1}")
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
                    print(f"[DEBUG] Fallback: Checking page {i+1} for NPQ content")
                    if "NeuroPsych Questionnaire" in text or "Domain Score Severity" in text:
                        print(f"[DEBUG] Found NPQ content on page {i+1} during fallback")
                    page_lines = text.splitlines()
                    lines.extend(l.strip() for l in page_lines if l.strip())
    
    # Debug the first few lines to help diagnose issues
    print("[DEBUG] First few NPQ extracted lines:")
    for idx, line in enumerate(lines[:20]):
        print(f"  {idx}: {line}")
        
    return lines

def parse_all_subtests(pdf_path, patient_id):
    known_tests = [
        "Verbal Memory Test (VBM)",
        "Visual Memory Test (VSM)",
        "Finger Tapping Test (FTT)",
        "Symbol Digit Coding (SDC)",
        "Stroop Test (ST)",
        "Shifting Attention Test (SAT)",
        "Continuous Performance Test (CPT)",
        "Reasoning Test (RT)",
        "Four Part Continuous Performance Test"
    ]

    all_results = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            tables = page.extract_tables()

            for test_name in known_tests:
                if test_name in text:
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        if test_name.split()[0] not in table[0][0]:
                            continue  # crude match
                        parsed = extract_subtest_data(table)
                        for metric, score, std, perc in parsed:
                            all_results.append((patient_id, test_name, metric, score, std, perc))
    
    print(f"[DEBUG] Parsed {len(all_results)} subtest entries.")
    return all_results

# ... rest of the file unchanged ...

def insert_patient(conn, patient_id, test_date, age, language):
    conn.execute("""
        INSERT OR REPLACE INTO patients (patient_id, test_date, age, language)
        VALUES (?, ?, ?, ?)
    """, (patient_id, test_date, age, language))

def insert_cognitive_scores(conn, scores):
    conn.executemany("""
        INSERT INTO cognitive_scores (
            patient_id, domain, patient_score, 
            standard_score, percentile, validity_index
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, scores)

def log_section_status(conn, patient_id, section, status):
    conn.execute("""
        INSERT INTO test_log (patient_id, section, status)
        VALUES (?, ?, ?)
    """, (patient_id, section, status))

def insert_npq_questions(conn, patient_id, question_data):
    """
    Insert NPQ question responses into the database.
    
    Args:
        conn: Database connection
        patient_id: Patient ID
        question_data: List of tuples (question_num, question_text, score, severity, domain_name)
    
    Returns:
        int: Number of questions inserted
    """
    insert_count = 0
    
    try:
        # First, check if the table exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='npq_questions'")
        if not cursor.fetchone():
            # Create the table if it doesn't exist
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS npq_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT,
                domain TEXT,
                question_number INTEGER,
                question_text TEXT,
                score INTEGER,
                severity TEXT
            )""")
            conn.commit()
        
        # Insert the data
        if question_data:
            print(f"[INFO] Found {len(question_data)} NPQ question responses.")
            
            # Prepare the data for insertion
            insert_data = []
            for question_num, question_text, score, severity, domain_name in question_data:
                insert_data.append((patient_id, domain_name, question_num, question_text, score, severity))
            
            # Insert the data
            conn.executemany("""
                INSERT INTO npq_questions (patient_id, domain, question_number, question_text, score, severity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, insert_data)
            
            conn.commit()
            insert_count = len(insert_data)
            print(f"[INFO] Inserted {insert_count} NPQ question responses for patient {patient_id}")
        
    except Exception as e:
        print(f"[ERROR] Failed to insert NPQ questions: {e}")
        conn.rollback()
    
    return insert_count

def extract_and_insert_npq_questions(pdf_path, patient_id, conn):
    """
    Extract NPQ questions from a PDF and insert them into the database.
    
    Args:
        pdf_path (str): Path to the PDF file
        patient_id (str): Patient ID
        conn: Database connection
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Find NPQ pages
        npq_pages = find_npq_pages(pdf_path)
        
        if npq_pages:
            # Extract NPQ questions
            question_data = extract_npq_questions_pymupdf(pdf_path, npq_pages)
            
            if question_data:
                # Insert NPQ questions into database
                insert_count = insert_npq_questions(conn, patient_id, question_data)
                print(f"Inserted {insert_count} NPQ questions for patient {patient_id}")
                return True
            else:
                log_section_status(conn, patient_id, "NPQ Questions", "No data found")
                return False
        else:
            log_section_status(conn, patient_id, "NPQ Questions", "No NPQ pages found")
            return False
    except Exception as e:
        print(f"Error extracting NPQ questions: {e}")
        log_section_status(conn, patient_id, "NPQ Questions", f"Failed: {e}")
        return False

def insert_dsm_criteria_met(conn, patient_id, dsm_criteria_data):
    """
    Insert DSM criteria met into the database.
    
    Args:
        conn: Database connection
        patient_id: Patient ID
        dsm_criteria_data: List of tuples (dsm_criterion, dsm_category, is_met)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Prepare data for insertion
        data_to_insert = []
        for dsm_criterion, dsm_category, is_met in dsm_criteria_data:
            data_to_insert.append((
                patient_id,
                dsm_criterion,
                dsm_category,
                is_met
            ))
        
        # Insert data
        conn.executemany("""
            INSERT INTO dsm_criteria_met 
            (patient_id, dsm_criterion, dsm_category, is_met)
            VALUES (?, ?, ?, ?)
        """, data_to_insert)
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to insert DSM criteria met: {e}")
        return False

def insert_dsm_diagnosis(conn, patient_id, inattentive_met, hyperactive_met, diagnosis):
    """
    Insert DSM diagnosis information into the database.
    
    Args:
        conn: Database connection
        patient_id: Patient ID
        inattentive_met: Number of inattentive criteria met
        hyperactive_met: Number of hyperactive criteria met
        diagnosis: ADHD diagnosis text
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn.execute("""
            INSERT INTO asrs_dsm_diagnosis 
            (patient_id, inattentive_criteria_met, hyperactive_criteria_met, diagnosis)
            VALUES (?, ?, ?, ?)
        """, (patient_id, inattentive_met, hyperactive_met, diagnosis))
        return True
    except Exception as e:
        print(f"[ERROR] Failed to insert DSM diagnosis: {e}")
        return False

def import_pdf_to_db(pdf_path):
    """
    Parses a cognitive report PDF using report_parser and imports the data into the database.
    Returns True on success (or if patient already exists), False on failure.
    """
    logger.info(f"Attempting to import PDF data for: {pdf_path}")

    parsed_data = parse_complete_cognitive_report(pdf_path)

    if not parsed_data:
        logger.error(f"Parsing failed for {pdf_path}. Cannot import to database.")
        return False

    if not parsed_data.get('patient_info') or not parsed_data['patient_info'].get('patient_id'):
        logger.error(f"Essential patient info (ID) missing after parsing {pdf_path}. Cannot import.")
        return False

    patient_info = parsed_data['patient_info']
    patient_id = patient_info['patient_id']
    logger.info(f"Parsing successful for patient ID: {patient_id}. Proceeding with database import.")

    with sqlite3.connect(DB_PATH) as conn:
        if conn.execute("SELECT 1 FROM patients WHERE patient_id = ?", (patient_id,)).fetchone():
            logger.info(f"Patient ID {patient_id} already exists in the database. Skipping import.")
            return True
        try:
            conn.execute("BEGIN TRANSACTION")
            insert_patient(conn, patient_id, patient_info.get('test_date'), patient_info.get('age'), patient_info.get('language'))
            logger.info(f"Inserted patient info for ID: {patient_id}")

            cognitive_scores = parsed_data.get('cognitive_scores', [])
            if cognitive_scores:
                insert_cognitive_scores(conn, cognitive_scores)
                log_section_status(conn, patient_id, "Cognitive Scores", "imported")
                logger.info(f"Inserted {len(cognitive_scores)} cognitive score entries.")
            else:
                log_section_status(conn, patient_id, "Cognitive Scores", "missing_after_parse")
                logger.warning("No cognitive scores found in parsed data.")

            subtests = parsed_data.get('subtests', [])
            if subtests:
                num_columns = len(subtests[0])
                if num_columns == 7:
                    conn.executemany("INSERT INTO subtest_results (patient_id, subtest_name, metric, score, standard_score, percentile, validity_flag) VALUES (?, ?, ?, ?, ?, ?, ?)", subtests)
                elif num_columns == 6:
                    conn.executemany("INSERT INTO subtest_results (patient_id, subtest_name, metric, score, standard_score, percentile) VALUES (?, ?, ?, ?, ?, ?)", subtests)
                else:
                    logger.error(f"Unexpected number of columns ({num_columns}) in subtest data. Cannot insert.")
                    raise ValueError("Subtest data format mismatch")
                log_section_status(conn, patient_id, "Subtests", "imported")
                logger.info(f"Inserted {len(subtests)} subtest entries.")
            else:
                log_section_status(conn, patient_id, "Subtests", "missing_after_parse")
                logger.warning("No subtests found in parsed data.")

            asrs_responses = parsed_data.get('asrs', [])
            if asrs_responses:
                conn.executemany("INSERT INTO asrs_responses (patient_id, question_number, part, response) VALUES (?, ?, ?, ?)", asrs_responses)
                log_section_status(conn, patient_id, "ASRS", "imported")
                logger.info(f"Inserted {len(asrs_responses)} ASRS entries.")
            else:
                log_section_status(conn, patient_id, "ASRS", "missing_after_parse")
                logger.warning("No ASRS responses found in parsed data.")

            epworth_data = parsed_data.get('epworth')
            if epworth_data:
                # TODO: Replace with actual call to insert_epworth if available
                logger.info(f"Epworth data present for patient {patient_id}. Implement insertion logic as needed.")
                log_section_status(conn, patient_id, "Epworth", "imported_placeholder")
            else:
                log_section_status(conn, patient_id, "Epworth", "missing_after_parse")
                logger.warning("No Epworth data found in parsed data.")

            npq_questions = parsed_data.get('npq', [])
            if npq_questions:
                inserted_count = insert_npq_questions(conn, patient_id, npq_questions)
                if inserted_count == len(npq_questions):
                    log_section_status(conn, patient_id, "NPQ", "imported")
                    logger.info(f"Inserted {inserted_count} NPQ entries.")
                else:
                    log_section_status(conn, patient_id, "NPQ", "import_error")
                    logger.error(f"NPQ insertion issue: expected {len(npq_questions)}, inserted {inserted_count}.")
            else:
                log_section_status(conn, patient_id, "NPQ", "missing_after_parse")
                logger.warning("No NPQ questions found in parsed data.")

            dsm_criteria = parsed_data.get('dsm', [])
            if dsm_criteria:
                # TODO: Replace with actual call to insert_dsm_criteria_met if available
                logger.info(f"DSM criteria present for patient {patient_id}. Implement insertion logic as needed.")
                log_section_status(conn, patient_id, "DSM Criteria", "imported_placeholder")
            else:
                log_section_status(conn, patient_id, "DSM Criteria", "missing_after_parse")
                logger.warning("No DSM criteria data found in parsed data.")

            conn.commit()
            logger.info(f"Successfully imported all available data for patient ID: {patient_id}")
            return True
        except Exception as e:
            conn.rollback()
            logger.exception(f"Error during database import for patient ID {patient_id}: {e}. Transaction rolled back.")
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO test_log (patient_id, section, status) VALUES (?, ?, ?)", (patient_id, "Overall Import", f"failed: {type(e).__name__}"))
                conn.commit()
            except Exception as log_e:
                logger.error(f"Failed to log overall import failure after rollback: {log_e}")
            return False

def extract_subtest_section(pdf_path):
    """Extract subtest scores section using pdfplumber"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_text = []
            print("\nDEBUG: === Raw PDF Tables by Page ===")
            for page_num, page in enumerate(pdf.pages[:3], 1):
                tables = page.extract_tables()
                for table_num, table in enumerate(tables, 1):
                    print(f"\n=== Page {page_num}, Table {table_num} ===")
                    for row in table:
                        print([str(cell).strip() if cell else '' for cell in row])
                    print("-" * 80)
                    # Convert table to text
                    table_text = "\n".join(" ".join(str(cell).strip() if cell else '' for cell in row) for row in table)
                    all_text.append(table_text)
            
            combined_text = "\n".join(all_text)
            print("\nDEBUG: === Combined Text ===")
            print(combined_text)
            print("=" * 80)
            return combined_text
            
    except Exception as e:
        print(f"Error extracting subtest section: {str(e)}")
        return ""

def parse_subtests_new(cognitive_text, patient_id):
    """Parse subtest scores using the hierarchical structure of the tests"""
    subtests = []
    current_test = None
    
    # Split into lines and clean
    lines = [line.strip() for line in cognitive_text.split('\n') if line.strip()]
    
    print("\nDEBUG: === Processing Lines ===")
    try:
        for line in lines:
            print(f"LINE: {line}")
            # Try to match test names directly
            if any(test in line for test in [
                "Verbal Memory Test",
                "Visual Memory Test",
                "Finger Tapping Test",
                "Symbol Digit Coding",
                "Stroop Test",
                "Shifting Attention Test",
                "Continuous Performance Test",
                "Reasoning Test",
                "Four Part Continuous Performance Test"
            ]):
                current_test = line.split("Score")[0].strip() if "Score" in line else line.strip()
                print(f"DEBUG: Found test section: {current_test}")
                continue
            
            # Try to match score pattern for metrics
            if current_test:
                # Look for lines with 3-4 numbers (score, standard, percentile)
                numbers = [n for n in line.split() if n.replace('.', '').isdigit() or n == 'NA']
                if 3 <= len(numbers) <= 4:
                    # Extract the metric name (everything before the first number)
                    metric = line[:line.find(numbers[0])].strip()
                    if metric and len(metric) > 3:
                        try:
                            score = numbers[0] if numbers[0] == 'NA' else float(numbers[0])
                            std_score = int(numbers[-2])
                            percentile = int(numbers[-1])
                            
                            print(f"DEBUG: Found score - Test: {current_test}, Metric: {metric}, Score: {score}, Std: {std_score}, Perc: {percentile}")
                            
                            subtests.append((
                                patient_id,
                                current_test,
                                metric,
                                score if score != 'NA' else None,
                                std_score,
                                percentile
                            ))
                        except (ValueError, IndexError) as e:
                            print(f"Error parsing score line '{line}': {e}")
            elif len(line.split()) > 10:  # Long text line
                current_test = None
    
    except Exception as e:
        print(f"Error parsing subtests: {e}")
    
    return subtests

# Main execution block
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python cognitive_importer.py path/to/file.pdf")
    else:
        try:
            import_pdf_to_db(sys.argv[1])
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
