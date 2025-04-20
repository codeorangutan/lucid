import sqlite3
import fitz  # PyMuPDF
import re
import pdfplumber
import os

# Database path
DB_PATH = 'cognitive_analysis.db'

# PDF path
PDF_PATH = "g:\\My Drive\\Programming\\Report_Reformat\\SQL_Data Extractor_from_PDF\\40277.pdf"

def find_npq_pages(pdf_path):
    """Find pages that contain NPQ content"""
    npq_pages = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for i in range(len(pdf.pages)):
            text = pdf.pages[i].extract_text()
            if text and ("NeuroPsych Questionnaire" in text or "Domain Score Severity" in text):
                npq_pages.append(i)
                print(f"[DEBUG] Found NPQ on page {i+1}")
    
    return npq_pages

def extract_npq_questions_pymupdf(pdf_path, npq_pages_indices):
    """
    Extracts NPQ question responses using PyMuPDF and regex.
    Handles cases where question number, text, score, and severity are on separate lines.

    Args:
        pdf_path (str): Path to the PDF file.
        npq_pages_indices (list): List of 0-based page indices containing NPQ content.

    Returns:
        list: A list of tuples, where each tuple contains:
              (question_num, question_text, score, severity, domain_name)
    """
    question_data = []
    
    # Regex patterns
    question_num_pattern = re.compile(r'^(\d{1,2})$')  # Just the question number
    severity_pattern = re.compile(r'^\s*(\d)\s*-\s*(.*)$')  # Score and severity description
    
    # Markers for different question sections -> Maps Header to Domain Name for DB
    # **Crucially, ensure these EXACTLY match the headers in your PDF**
    domain_questions_markers = {
        "Attention Questions": "Attention",
        "Impulsive Questions": "Impulsive",
        "Learning Questions": "Learning",
        "Memory Questions": "Memory",
        "Anxiety Questions": "Anxiety",
        "Panic Questions": "Panic",
        "Agoraphobia Questions": "Agoraphobia",
        "Obsessions & Compulsions Questions": "Obsessions & Compulsions",
        "Social Anxiety Questions": "Social Anxiety",
        "Depression Questions": "Depression",
        "Mood Stability Questions": "Mood Stability",
        "Mania Questions": "Mania",
        "Aggression Questions": "Aggression",
        "Psychotic Questions": "Psychotic",
        "Somatic Questions": "Somatic",
        "Fatigue Questions": "Fatigue",
        "Sleep Questions": "Sleep",
        "Suicide Questions": "Suicide",
        "Pain Questions": "Pain",
        "Substance Abuse Questions": "Substance Abuse",
        "PTSD Questions": "PTSD",
        "Bipolar Questions": "Bipolar",
        "Autism Questions": "Autism",
        "Asperger's Questions": "Asperger's",
        "ADHD Questions": "ADHD",
        "MCI Questions": "MCI",
        "Concussion Questions": "Concussion",
        "Anxiety/Depression Questions": "Anxiety/Depression"
    }
    
    current_domain = None  # Track which section we are in
    current_question_num = None  # Track current question number
    current_question_text = None  # Track current question text
    
    if not npq_pages_indices:
        print("[WARN] No NPQ page indices provided for question extraction.")
        return []
    
    try:
        doc = fitz.open(pdf_path)
        for page_idx in npq_pages_indices:
            if page_idx >= len(doc):
                print(f"[WARN] Page index {page_idx} out of range for PDF.")
                continue
            
            print(f"[DEBUG] Extracting NPQ questions from page {page_idx+1}")
            page = doc[page_idx]
            # Extract text blocks, sorted vertically then horizontally
            blocks = page.get_text("blocks")
            blocks.sort(key=lambda b: (b[1], b[0]))  # Sort top-down, left-right
            
            for block in blocks:
                # block format: (x0, y0, x1, y1, "text content", block_no, block_type)
                if len(block) >= 7 and block[6] == 0:  # It's a text block
                    block_text_lines = block[4].splitlines()
                    
                    for line in block_text_lines:
                        line = line.strip()
                        if not line: continue
                        
                        # Check if line is a domain header first
                        is_header = False
                        for header, domain_name in domain_questions_markers.items():
                            # Use exact match for headers
                            if line == header:
                                current_domain = domain_name
                                print(f"[DEBUG] Switched to NPQ domain: {current_domain}")
                                is_header = True
                                # Reset question tracking when switching domains
                                current_question_num = None
                                current_question_text = None
                                break  # Found header, stop checking headers for this line
                        
                        if is_header:
                            continue  # Don't process the header line itself as a question
                        
                        # If we are within a known domain, try matching the question pattern
                        if current_domain:
                            # Check if this line is a question number
                            num_match = question_num_pattern.match(line)
                            if num_match:
                                # Save the current question if we have one and are moving to a new one
                                current_question_num = int(num_match.group(1))
                                current_question_text = None  # Reset for new question
                                continue
                            
                            # Check if this line is a severity rating (after we've seen a question number)
                            severity_match = severity_pattern.match(line)
                            if severity_match and current_question_num is not None and current_question_text is not None:
                                score = int(severity_match.group(1))
                                severity = severity_match.group(2).strip()
                                
                                print(f"[DEBUG] Q{current_question_num}: '{current_question_text[:40]}...' -> {score} - {severity} [{current_domain}]")
                                question_data.append((current_question_num, current_question_text, score, severity, current_domain))
                                
                                # Reset after capturing a complete question
                                current_question_text = None
                                continue
                            
                            # If we have a question number but no text yet, this must be the question text
                            if current_question_num is not None and current_question_text is None:
                                current_question_text = line
                                continue
                            
                            # If we reach here, it's some other text we don't need to process
                
        doc.close()
    except Exception as e:
        print(f"[ERROR] General error during NPQ question extraction: {e}")
    
    print(f"[INFO] Found {len(question_data)} NPQ question responses.")
    return question_data

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
                print(f"No NPQ question data found for patient {patient_id}")
                return False
        else:
            print(f"No NPQ pages found in PDF for patient {patient_id}")
            return False
    except Exception as e:
        print(f"Error extracting NPQ questions: {e}")
        return False

def main():
    # Connect to the database
    conn = sqlite3.connect(DB_PATH)
    
    # Extract and insert NPQ questions
    patient_id = "40277"
    success = extract_and_insert_npq_questions(PDF_PATH, patient_id, conn)
    
    # Check the results
    if success:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM npq_questions WHERE patient_id = ?", (patient_id,))
        count = cursor.fetchone()[0]
        print(f"Successfully inserted {count} NPQ questions for patient {patient_id}")
    else:
        print(f"Failed to extract and insert NPQ questions for patient {patient_id}")
    
    # Close the connection
    conn.close()

if __name__ == "__main__":
    main()
