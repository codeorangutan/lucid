import sqlite3
import re
import os
import fitz
import csv # PyMuPDF

DB_PATH = "cognitive_analysis.db"
PDF_PATH = "34766-20231015201357.pdf"

# --- DB Setup ---
def create_db(reset=False):
    if reset and os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except PermissionError:
            print(f"Warning: Could not remove {DB_PATH}. It may be in use.")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Create tables
    cur.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id INTEGER PRIMARY KEY,
        test_date TEXT,
        age INTEGER,
        language TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cognitive_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        domain TEXT,
        patient_score TEXT,
        standard_score INTEGER,
        percentile INTEGER,
        validity_index TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subtest_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        subtest_name TEXT,
        metric TEXT,
        score REAL,
    standard_score INTEGER,
    percentile INTEGER,
    FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
)""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS asrs_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        question_number INTEGER,
        part TEXT,
        response TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS dass21_scores(
        patient_id INTEGER,
        question_number INTEGER,
        response_score INTEGER,
        response_text TEXT,
        depression INTEGER,
        anxiety INTEGER,
        stress INTEGER,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dass21_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        question_number INTEGER,
        response_score INTEGER,
        response_text TEXT,
    FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
)""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS epworth_scores (
        patient_id INTEGER,
        epworth_score INTEGER,
        question_number INTEGER,
        response TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS test_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        section TEXT,
        status TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS npq_scores (
    patient_id INTEGER,
    domain TEXT,
    score INTEGER,
    severity TEXT,
    description TEXT,
    FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS npq_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER,
    domain TEXT,
    question_number INTEGER,
    question_text TEXT,
    score INTEGER,
    severity TEXT,
    FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )""")

    conn.commit()
    conn.close()

# --- Data Extraction ---
def extract_text_blocks(pdf_path):
    import fitz  # ensure imported

    doc = fitz.open(pdf_path)
    all_lines = []

    for page in doc:
        blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
        blocks = sorted(blocks, key=lambda b: (b[1], b[0]))  # sort top-down, then left-right
        for b in blocks:
            lines = b[4].splitlines()
            all_lines.extend(line.strip() for line in lines if line.strip())
            in_npq = False
            for line in lines:
                if "NeuroPsych Questionnaire" in line:
                    in_npq = True
                if in_npq:
                    print("[NPQ RAW]", line)

    return all_lines

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

def extract_npq_table(pdf_path):
    """Extract NPQ data using table extraction approach"""
    import pdfplumber
    
    with pdfplumber.open(pdf_path) as pdf:
        # Search for the NPQ section in the PDF
        npq_pages = []
        for i in range(len(pdf.pages)):
            text = pdf.pages[i].extract_text()
            if text and ("NeuroPsych Questionnaire" in text or "Domain Score Severity" in text):
                npq_pages.append(i)
                print(f"[DEBUG] Found NPQ on page {i+1}")
        
        if not npq_pages:
            print("[WARN] No NPQ pages found")
            return [], []
        
        # Extract tables from NPQ pages
        all_tables = []
        for page_idx in npq_pages:
            page = pdf.pages[page_idx]
            tables = page.extract_tables()
            if tables:
                print(f"[DEBUG] Found {len(tables)} tables on page {page_idx+1}")
                all_tables.extend(tables)
            else:
                print(f"[DEBUG] No tables found on page {page_idx+1}")
        
        # Process tables to extract domain data
        domain_data = []
        question_data = []
        
        for table_idx, table in enumerate(all_tables):
            print(f"[DEBUG] Processing table {table_idx+1} with {len(table)} rows")
            
            # Check if this is a domain table
            is_domain_table = False
            for row in table:
                if row and len(row) >= 3:
                    # Check if any cell contains "Domain", "Score", "Severity"
                    header_cells = [cell for cell in row if cell and isinstance(cell, str)]
                    if any("Domain" in cell for cell in header_cells) and any("Score" in cell for cell in header_cells):
                        is_domain_table = True
                        print(f"[DEBUG] Table {table_idx+1} is a domain table")
                        break
            
            if is_domain_table:
                # Process domain table
                for row in table:
                    if row and len(row) >= 3 and all(cell is not None for cell in row[:3]):
                        domain = row[0]
                        # Skip header row
                        if domain == "Domain" or "Domain" in domain:
                            continue
                        
                        try:
                            score = int(row[1]) if row[1] and row[1].isdigit() else None
                            severity = row[2] if row[2] else ""
                            
                            if domain and score is not None:
                                print(f"[DEBUG] Found domain: {domain}, score: {score}, severity: {severity}")
                                domain_data.append((domain, score, severity))
                        except (ValueError, TypeError) as e:
                            print(f"[WARN] Error parsing domain row: {row} - {e}")
            else:
                # This might be a question table
                for row in table:
                    if row and len(row) >= 4:
                        try:
                            # Check if first cell is a number (question number)
                            if row[0] and row[0].isdigit():
                                question_num = int(row[0])
                                question_text = row[1] if row[1] else ""
                                score = int(row[2]) if row[2] and row[2].isdigit() else None
                                severity = row[3] if row[3] else ""
                                
                                if question_text and score is not None:
                                    print(f"[DEBUG] Found question: {question_num}, {question_text}, score: {score}")
                                    question_data.append((question_num, question_text, score, severity))
                        except (ValueError, TypeError) as e:
                            print(f"[WARN] Error parsing question row: {row} - {e}")
        
        # If no tables were found or processed, try to extract using bounding boxes
        if not domain_data:
            print("[DEBUG] No domain data found in tables, trying bounding box extraction")
            domain_data, question_data = extract_npq_with_bounding_boxes(pdf, npq_pages)
    
    return domain_data, question_data

def extract_npq_with_bounding_boxes(pdf, npq_pages):
    """Extract NPQ data using bounding boxes for when table extraction fails"""
    domain_data = []
    question_data = []
    
    # Known domains for validation
    domains = [
        "Attention", "Impulsive", "Learning", "Memory", "Fatigue", "Sleep", 
        "Anxiety", "Panic", "Agoraphobia", "Obsessions & Compulsions", "Social Anxiety", 
        "PTSD", "Depression", "Bipolar", "Mood Stability", "Mania", "Aggression", 
        "Autism", "Asperger's", "Psychotic", "Somatic", "Suicide", "Pain", 
        "Substance Abuse", "MCI", "Concussion", "ADHD", "Average Symptom Score", "Anxiety/Depression"
    ]
    
    # Severity levels for validation
    severity_levels = ["Severe", "Moderate", "Mild", "Not a problem"]
    
    # Track the current domain for question parsing
    current_domain = None
    in_question_section = False
    
    for page_idx in npq_pages:
        page = pdf.pages[page_idx]
        print(f"[DEBUG] Processing page {page_idx+1} with bounding box method")
        
        # Extract all words with their positions
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
        
        # Group words by their y-position (same line)
        lines = {}
        for word in words:
            y = round(word["top"])
            if y not in lines:
                lines[y] = []
            lines[y].append(word)
        
        # Sort lines by y-position
        sorted_y = sorted(lines.keys())
        
        # Process each line
        for i, y in enumerate(sorted_y):
            line_words = sorted(lines[y], key=lambda w: w["x0"])
            line_text = " ".join(word["text"] for word in line_words)
            
            # Check for question section headers (e.g., "Attention Questions")
            question_section_match = re.search(r'^(\w+)\s+Questions$', line_text)
            if question_section_match:
                current_domain = question_section_match.group(1)
                print(f"[DEBUG] Found question section for domain: {current_domain}")
                continue
            
            # Check if this is a question line (starts with a number)
            if in_question_section and current_domain:
                question_match = re.match(r'^(\d+)\s+(.+)$', line_text)
                x_span = next((s for s in line_words if "X" in s["text"]), None)

                if question_match and x_span:
                    question_num = int(question_match.group(1))
                    question_text = question_match.group(2).strip()
                    
                    # Get the next line (potential answer)
                    if i + 1 < len(lines):
                        answer_y = sorted_y[i + 1]
                        answer_line = " ".join(word["text"] for word in sorted(lines[answer_y], key=lambda w: w["x0"]))
                        
                        # Try to match answer pattern (e.g., "3 - Moderate")
                        answer_match = re.match(r'^(\d+)\s*-\s*(.+)$', answer_line)
                        
                        if answer_match:
                            score = int(answer_match.group(1))
                            severity = answer_match.group(2).strip()
                            
                            print(f"[DEBUG] Found question: {question_num}, '{question_text}', score: {score}, severity: '{severity}'")
                            question_data.append((question_num, question_text, score, severity, current_domain))
            
            # Check if this line contains a domain
            domain_match = None
            for domain in domains:
                if domain in line_text:
                    domain_match = domain
                    break
            
            if domain_match and i + 2 < len(sorted_y):
                # Get the next two lines (potential score and severity)
                score_y = sorted_y[i + 1]
                severity_y = sorted_y[i + 2]
                
                score_line = " ".join(word["text"] for word in sorted(lines[score_y], key=lambda w: w["x0"]))
                severity_line = " ".join(word["text"] for word in sorted(lines[severity_y], key=lambda w: w["x0"]))
                
                # Try to extract score (should be just a number)
                score_match = re.search(r'^\s*(\d+)\s*$', score_line)
                
                # Check if severity is one of the expected values
                severity_match = None
                for level in severity_levels:
                    if level in severity_line:
                        severity_match = level
                        break
                
                if score_match and severity_match:
                    score = int(score_match.group(1))
                    severity = severity_match
                    
                    print(f"[DEBUG] Found domain via bounding boxes: {domain_match}, score: {score}, severity: {severity}")
                    domain_data.append((domain_match, score, severity))
    
    # Print summary of what we found
    print(f"[DEBUG] Found {len(domain_data)} domains via bounding boxes:")
    for domain, score, severity in domain_data:
        print(f"  - {domain}: {score}, {severity}")
    
    print(f"[DEBUG] Found {len(question_data)} questions via bounding boxes")
    
    return domain_data, question_data

def extract_npq_questions(pdf, npq_pages):
    """Extract NPQ question responses using the known structure after 'clinical examination.'"""
    question_data = []
    
    # Known domains for the questions (same order as they appear)
    question_domains = [
        "Attention Questions", "Impulsive Questions", "Learning Questions", 
        "Memory Questions", "Fatigue Questions", "Sleep Questions", "Anxiety Questions",
        "Panic Questions", "Agoraphobia Questions", "Obsessions & Compulsions Questions",
        "Social Anxiety Questions", "PTSD Questions", "Depression Questions",
        "Bipolar Questions", "Mood Stability Questions", "Mania Questions",
        "Aggression Questions", "Autism Questions", "Asperger's Questions",
        "Psychotic Questions", "Somatic Questions", "Suicide Questions",
        "Pain Questions", "Substance Abuse Questions", "MCI Questions",
        "Concussion Questions", "ADHD Questions"
    ]
    
    full_text = ""
    # Combine text from all NPQ pages
    for page_idx in npq_pages:
        page = pdf.pages[page_idx]
        text = page.extract_text()
        full_text += text + "\n"
    
    # Debug: Print a portion of the text to see what we're working with
    print("[DEBUG] NPQ Text Preview (first 500 chars):")
    print(full_text[:500])
    
    # Debug: Check for the marker
    start_marker = "clinical examination."
    if start_marker in full_text:
        print(f"[DEBUG] Found marker '{start_marker}'")
        start_pos = full_text.find(start_marker)
        print(f"[DEBUG] Marker position: {start_pos}")
        questions_text = full_text.split(start_marker)[1]
        
        # Debug: Print first part of questions text
        print("[DEBUG] Questions Text Preview (first 300 chars):")
        print(questions_text[:300])
        
        # Debug: Check for domain headers
        domain_found = False
        for domain in question_domains:
            if domain in questions_text:
                print(f"[DEBUG] Found domain header: {domain}")
                domain_found = True
        
        if not domain_found:
            print("[DEBUG] No domain headers found in the expected format")
            print("[DEBUG] Trying alternative approach...")
            
            # Look for patterns like "1 Difficulty concentrating 3 - A severe problem"
            pattern = re.compile(r'(\d+)\s+([^\d]+?)\s+(\d)\s+-\s+(.+?)(?=\d+\s|$)', re.DOTALL)
            matches = pattern.findall(questions_text)
            
            if matches:
                current_domain = "Unknown"  # Default if we can't determine domain
                
                # Try to find which domain we're in by looking for domain names nearby
                for match in matches:
                    # Extract question parts
                    qnum = int(match[0])
                    qtext = match[1].strip()
                    score = int(match[2])
                    severity = match[3].strip()
                    
                    print(f"[DEBUG] Found question {qnum}: {qtext[:20]}... -> {score} - {severity}")
                    question_data.append((qnum, qtext, score, severity, current_domain))
                
                print(f"[DEBUG] Found {len(matches)} questions via pattern matching")
        else:
            # Original approach - parse domain by domain
            current_domain = None
            
            # Split into lines and process
            lines = questions_text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Check for domain headers
                for domain in question_domains:
                    if domain in line:
                        current_domain = domain.replace(" Questions", "")
                        print(f"[DEBUG] Processing section: {current_domain}")
                        i += 1
                        break
                
                # If we have a domain, look for questions
                if current_domain and line:
                    # Check if line starts with a number (question)
                    if re.match(r'^\d+$', line):
                        question_num = int(line)
                        
                        # Next line should be question text
                        if i + 1 < len(lines):
                            question_text = lines[i + 1].strip()
                            
                            # Next line should be answer (format: "N - Severity")
                            if i + 2 < len(lines):
                                answer_line = lines[i + 2].strip()
                                answer_match = re.match(r'^(\d)\s*-\s*(.+)$', answer_line)
                                
                                if answer_match:
                                    score = int(answer_match.group(1))
                                    severity = answer_match.group(2).strip()
                                    
                                    print(f"[DEBUG] Found Q{question_num}: {question_text} -> {score} - {severity}")
                                    question_data.append((question_num, question_text, score, severity, current_domain))
                                    i += 3  # Move past question num, text, and answer
                                    continue
                
                i += 1
    else:
        print(f"[DEBUG] Marker '{start_marker}' not found in text")
        
        # Try to find alternative markers
        alternative_markers = [
            "interpreted by an experienced clinician",
            "Attention Questions",
            "Difficulty concentrating"
        ]
        
        for marker in alternative_markers:
            if marker in full_text:
                print(f"[DEBUG] Found alternative marker: '{marker}'")
                start_pos = full_text.find(marker)
                print(f"[DEBUG] Alternative marker position: {start_pos}")
                
                # Show some context around this marker
                context_start = max(0, start_pos - 50)
                context_end = min(len(full_text), start_pos + 100)
                print(f"[DEBUG] Context around marker: '{full_text[context_start:context_end]}'")
    
    print(f"[DEBUG] Total questions found: {len(question_data)}")
    if question_data:
        print("[DEBUG] Sample questions:")
        for q in question_data[:3]:
            print(f"  {q[0]}. {q[1]} ({q[2]} - {q[3]}) [{q[4]}]")
    
    return question_data

def parse_basic_info(text):
    patient_id = int(re.search(r"Patient ID:\s*(\d+)", text).group(1))
    age = int(re.search(r"Age:\s*(\d+)", text).group(1))
    test_date = re.search(r"Test Date:\s*([\w:/\\-]+)", text).group(1).strip()

    language = re.search(r"Language:\s*(.+)", text).group(1).strip()
    return patient_id, age, test_date, language

def parse_cognitive_scores(text, patient_id):
    scores = []
    # Adjusted regex to handle 'NA' and the specific Neurocognition Index format
    score_pattern = re.compile(r'^(.*?)\s+(?:NA\s+)?(\d+|NA)\s+(\d+)\s+(\d+)\s+(Yes|No)\s*X?$', re.MULTILINE)
    
    for match in score_pattern.finditer(text):
        print("Matched groups:", match.groups())
        domain = match.group(1).strip()
        patient_score = match.group(2)
        standard_score = match.group(3)
        percentile = match.group(4)
        validity_index = match.group(5)

        scores.append((
            patient_id, 
            domain, 
            patient_score, 
            standard_score, 
            percentile, 
            validity_index
        ))
    
    return scores

def parse_subtests(lines, patient_id):
    subtests = []
    current_subtest = None
    i = 0

    while i < len(lines):
        line = lines[i].replace('\xa0', ' ').strip()

        # Detect subtest heading
        if re.match(r".+Test\s*\(.*\)", line):
            current_subtest = line
            i += 1
            continue

        # Skip headers
        if line.lower().startswith("score") or line.lower().startswith("standard"):
            i += 1
            continue

        # Look ahead to see if next 3 lines are numbers
        if current_subtest and i + 3 < len(lines):
            try:
                metric = line.strip().rstrip("*")
                score = int(lines[i+1].strip())
                standard = int(lines[i+2].strip())
                percentile = int(lines[i+3].strip())
                subtests.append((patient_id, current_subtest, metric, score, standard, percentile))
                i += 4  # skip over the block
                continue
            except ValueError:
                pass  # Not a subtest block

        i += 1  # next line

    return subtests

def parse_subtests_hardcoded(lines, patient_id):
    subtests = []

    # Flattened tokens (strings and numbers)
    flat = []
    for line in lines:
        flat.extend(line.strip().split())

    # Predefined structure
    known_subtests = [
        ("Verbal Memory Test (VBM)", [
            "Correct Hits - Immediate", "Correct Passes - Immediate",
            "Correct Hits - Delay", "Correct Passes - Delay"
        ]),
        ("Visual Memory Test (VSM)", [
            "Correct Hits - Immediate", "Correct Passes - Immediate",
            "Correct Hits - Delay", "Correct Passes - Delay"
        ]),
        ("Finger Tapping Test (FTT)", [
            "Right Taps Average", "Left Taps Average"
        ]),
        ("Symbol Digit Coding (SDC)", [
            "Correct Responses", "Errors*"
        ]),
        ("Stroop Test (ST)", [
            "Simple Reaction Time*", "Complex Reaction Time Correct*",
            "Stroop Reaction Time Correct*", "Stroop Commission Errors*"
        ]),
        ("Shifting Attention Test (SAT)", [
            "Correct Responses", "Errors*", "Correct Reaction Time*"
        ]),
        ("Continuous Performance Test (CPT)", [
            "Correct Responses", "Omission Errors*", "Commission Errors*",
            "Choice Reaction Time Correct*"
        ]),
        ("Reasoning Test (RT)", [
            "Correct Responses", "Average Correct Reaction Time*",
            "Commission Errors*", "Omission Errors*"
        ]),
        ("Four Part Continuous Performance Test", [
            "Average Correct Reaction Time*", "Correct Responses",
            "Incorrect Responses*", "Average Incorrect Reaction Time*",
            "Omission Errors*"
        ]),
    ]

    test_queue = []
    for test_name, subscales in known_subtests:
        for metric in subscales:
            test_queue.append((test_name, metric))

    i = 0
    while i < len(flat) - 2:
        token = flat[i]
        try:
            score = int(flat[i])
            standard = int(flat[i + 1])
            percentile = int(flat[i + 2])

            if test_queue:
                test_name, metric = test_queue.pop(0)
                subtests.append((patient_id, test_name, metric, score, standard, percentile))

            i += 3
        except ValueError:
            i += 1  # Skip if not a number
    return subtests

import pdfplumber

def extract_subtest_data(table):
    subtests = []
    headers = [h.strip() if h else "" for h in table[0]]

    for row in table[1:]:
        if not row or all(cell is None for cell in row):
            continue

        try:
            if '\n' in row[0]:
                metrics = [m.strip() for m in row[0].split('\n') if m.strip()]
                scores = [s.strip() for s in row[1].split('\n') if s.strip()]
                standards = [s.strip() for s in row[2].split('\n') if s.strip()]
                percentiles = [p.strip() for p in row[3].split('\n') if p.strip()]
            else:
                metrics = [row[0].strip()]
                scores = [row[1].strip()]
                standards = [row[2].strip()]
                percentiles = [row[3].strip()]
            
            for i in range(len(metrics)):
                metric = metrics[i]
                score = float(scores[i])
                std = int(standards[i])
                perc = int(percentiles[i])
                subtests.append((metric, score, std, perc))

        except Exception as e:
            print(f"[WARN] Failed row parse: {row} → {e}")

    return subtests

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




def parse_asrs_from_spans(pdf_path, patient_id):
    doc = fitz.open(pdf_path)
    response_headers = ["Never", "Rarely", "Sometimes", "Often", "Very Often"]
    label_map = {}
    asrs = []
    current_part = None

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                texts = [s["text"].strip() for s in spans if s["text"].strip()]
                line_text = " ".join(texts)

                # Detect part A/B
                if "Part A" in line_text:
                    current_part = "A"
                elif "Part B" in line_text:
                    current_part = "B"

                # Label headers
                if all(r in texts for r in response_headers):
                    label_map = {
                        span["text"]: (span["bbox"][0] + span["bbox"][2]) / 2
                        for span in spans if span["text"] in response_headers
                    }

                # Question detection
                q_match = re.match(r"^(\d{1,2})\s", line_text)
                x_span = next((s for s in spans if "X" in s["text"]), None)

                if q_match and x_span and label_map:
                    question_num = int(q_match.group(1))
                    x_pos = (x_span["bbox"][0] + x_span["bbox"][2]) / 2
                    matched_response = min(label_map.items(), key=lambda kv: abs(kv[1] - x_pos))[0]

                    asrs.append({
                        "patient_id": patient_id,
                        "question": question_num,
                        "part": current_part,
                        "response": matched_response
                    })

    return asrs

def parse_asrs_with_bounding_boxes(pdf_path, patient_id):
    import fitz
    import os
    import csv

    bounding_boxes_path = os.path.join(os.path.dirname(__file__), "bounding_boxes.csv")

    # Load bounding box data from CSV
    box_data = []
    SCALE_MM_TO_PT = 72 / 25.4  # Use this if your CSV is in mm

    with open(bounding_boxes_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            box_data.append({
                "part": row["Part"],
                "question": int(row["Question"]),
                "response": row["Response"],
                "x0": float(row["x0"]) * SCALE_MM_TO_PT,
                "y0": float(row["y0"]) * SCALE_MM_TO_PT,
                "x1": float(row["x1"]) * SCALE_MM_TO_PT,
                "y1": float(row["y1"]) * SCALE_MM_TO_PT,
            })

    doc = fitz.open(pdf_path)
    responses = []

    try:
        page = doc[3]  # only process page 4 (index 3)
    except IndexError:
        print(f"[WARN] PDF does not have a page 4: {pdf_path}")
        return responses

    page = doc[3]  # only process page 4 (index 3)
    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span["text"].strip() == "X":
                    xmid = (span["bbox"][0] + span["bbox"][2]) / 2
                    ymid = (span["bbox"][1] + span["bbox"][3]) / 2

                    for box in box_data:
                        if box["x0"] <= xmid <= box["x1"] and box["y0"] <= ymid <= box["y1"]:
                            responses.append((patient_id, box["question"], box["part"], box["response"]))
                            break  # only match once

    print(f"[DEBUG] Parsed {len(responses)} ASRS responses using bounding boxes on page 4.")
    return responses


def parse_dass21(text, patient_id):
    # Summary scores
    match = re.search(r"DASS21 Scores\s+Depression:\s*(\d+)\s+Anxiety:\s*(\d+)\s+Stress:\s*(\d+)", text)
    summary = (patient_id, int(match.group(1)), int(match.group(2)), int(match.group(3))) if match else None

    # Individual items like:
    # 1 1 - Sometimes I found it hard to wind down
    item_matches = re.findall(r"^\s*(\d{1,2})\s+(\d)\s*-\s*([\w\s]+)$", text, re.MULTILINE)
    responses = []
    for qn, score, desc in item_matches:
        responses.append((patient_id, int(qn), int(score), desc.strip()))

    return summary, responses

def parse_epworth(text, patient_id):
    responses = []

    # Extract total Epworth score
    match = re.search(r"Epworth Score\s*=\s*(\d+)", text)
    score = int(match.group(1)) if match else None

    # Only match lines for questions 1–8
    pattern = re.findall(r"^\s*([1-8])\s+(.+?)\s+(\d)\s*-\s*(.+)$", text, re.MULTILINE)
    for qn, situation, val, resp in pattern:
        full_response = f"{val} - {resp.strip()}"
        responses.append((patient_id, score, int(qn), full_response))

    return score, responses

def parse_npq(lines, patient_id):
    """Parse NPQ data from extracted text lines"""
    import re
    global PDF_PATH  # Access global variable
    
    # Try our new block-based approach first
    domain_data, question_data = extract_npq_questions_by_blocks(PDF_PATH, patient_id)
    
    scores = []
    responses = []
    
    # Process domain scores
    for domain, score, severity in domain_data:
        scores.append((patient_id, domain, score, severity, ''))
    
    # Process question responses
    for qnum, qtext, score, severity, domain in question_data:
        responses.append((patient_id, domain, qnum, qtext, score, severity))
    
    return scores, responses

def parse_npq_questions(lines, patient_id):
    import re
    responses = []
    current_domain = None

    question_re = re.compile(r'^(\d{1,2})\s+(.*?)\s+(\d)\s*-\s+(.*)$')
    domain_re = re.compile(r'^(Attention|Impulsive|Learning|Memory|Fatigue|Sleep|Anxiety|Panic|Agoraphobia|Obsessions|Social Anxiety|PTSD|Depression|Bipolar|Mood Stability|Mania|Aggression|Autism|Asperger|Psychotic|Somatic|Suicide|Pain|Substance Abuse|MCI|Concussion)')

    for line in lines:
        line = line.strip()
        match = question_re.match(line)
        if match:
            try:
                qn, question, score, severity = match.groups()
                responses.append((patient_id, current_domain or "Unspecified", int(qn), question.strip(), int(score), severity.strip()))
            except Exception as e:
                print("[WARN] Failed to parse question line →", line, ":", e)
            continue

        # Update domain if line clearly identifies one
        if domain_re.match(line):
            current_domain = line.strip()
            continue

        # Optional: log unmatched lines
        print("[DEBUG] Unmatched NPQ question line:", line)

    return responses

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

def extract_npq_questions_by_blocks(pdf_path, patient_id):
    """Extract NPQ questions using text blocks from PyMuPDF"""
    import fitz  # PyMuPDF
    import re
    
    domain_data = []
    question_data = []
    
    # Known domains to match against
    domains = [
        "Attention", "Impulsive", "Learning", "Memory", "Fatigue", "Sleep", 
        "Anxiety", "Panic", "Agoraphobia", "Obsessions & Compulsions", "Social Anxiety", 
        "PTSD", "Depression", "Bipolar", "Mood Stability", "Mania", "Aggression", 
        "Autism", "Asperger's", "Psychotic", "Somatic", "Suicide", "Pain", 
        "Substance Abuse", "MCI", "Concussion", "ADHD", "Average Symptom Score", "Anxiety/Depression"
    ]
    
    # Track the current question domain
    current_domain = None
    
    try:
        # Open the PDF
        doc = fitz.open(pdf_path)
        
        # Identify NPQ pages
        npq_pages = []
        for i in range(len(doc)):
            page_text = doc[i].get_text()
            if "NeuroPsych Questionnaire" in page_text or "Domain Score Severity" in page_text:
                npq_pages.append(i)
                print(f"[DEBUG] Found NPQ on page {i+1}")
        
        if not npq_pages:
            print("[WARN] No NPQ pages found in the PDF")
            return [], []
        
        # First find domain scores
        domain_scores_found = False
        for page_idx in npq_pages:
            page = doc[page_idx]
            blocks = page.get_text("blocks")
            blocks = sorted(blocks, key=lambda b: (b[1], b[0]))  # top-down, left-right
            
            for block in blocks:
                block_text = block[4]
                
                # This is the domain scores block if it contains multiple domains and scores
                if not domain_scores_found and "Domain\nScore\nSeverity" in block_text:
                    print("[DEBUG] Found domain scores block")
                    domain_scores_found = True
                    
                    # Split the block text by lines and process each line
                    lines = [line.strip() for line in block_text.splitlines() if line.strip()]
                    
                    # Skip the header (Domain, Score, Severity, Description)
                    for line in lines[4:]:
                        parts = line.split()
                        if len(parts) >= 3:
                            # Check if first part is a domain name
                            domain_name = parts[0]
                            
                            # Handle multi-word domain names
                            if len(parts) > 3 and parts[1] not in ['0', '1', '2', '3'] and not parts[1].isdigit():
                                domain_name = f"{domain_name} {parts[1]}"
                                score_index = 2
                            else:
                                score_index = 1
                                
                            # Try to extract score and severity
                            if domain_name in domains or domain_name + "s" in domains:
                                try:
                                    # Get score (should be a number)
                                    if parts[score_index].isdigit():
                                        score = int(parts[score_index])
                                        
                                        # Get severity (rest of the line)
                                        severity = " ".join(parts[score_index + 1:])
                                        
                                        print(f"[DEBUG] Found domain: {domain_name}, score: {score}, severity: {severity}")
                                        domain_data.append((domain_name, score, severity))
                                except (ValueError, IndexError) as e:
                                    print(f"[WARN] Failed to parse domain data: {line} → {e}")
        
        # Now extract questions
        for page_idx in npq_pages:
            page = doc[page_idx]
            blocks = page.get_text("blocks")
            blocks = sorted(blocks, key=lambda b: (b[1], b[0]))  # top-down, left-right
            
            for block in blocks:
                block_text = block[4]
                lines = [line.strip() for line in block_text.splitlines() if line.strip()]
                
                # Check if this block starts with a domain header
                for domain in domains:
                    domain_header = f"{domain} Questions"
                    if lines and domain_header in lines[0]:
                        current_domain = domain
                        print(f"[DEBUG] Found question section: {current_domain}")
                        break
                
                # If we have a current domain, look for questions
                if current_domain and len(lines) > 1:
                    i = 0
                    while i < len(lines):
                        # Check if the line starts with a number (question number)
                        if i < len(lines) and lines[i] and lines[i][0].isdigit():
                            # Try to extract the question number
                            question_match = re.match(r'^(\d+)\s*(.*)$', lines[i])
                            
                            if question_match:
                                question_num = int(question_match.group(1))
                                question_text = question_match.group(2).strip()
                                
                                # Check if the next line is the answer
                                if i + 1 < len(lines) and lines[i + 1].strip().startswith(' '):
                                    answer_line = lines[i + 1].strip()
                                    
                                    # Extract score and severity
                                    answer_match = re.match(r'^\s*(\d+)\s*-\s*(.*)$', answer_line)
                                    if answer_match:
                                        score = int(answer_match.group(1))
                                        severity = answer_match.group(2).strip()
                                        
                                        print(f"[DEBUG] Found Q{question_num}: '{question_text}' -> {score} - {severity}")
                                        question_data.append((question_num, question_text, score, severity, current_domain))
                                        
                                        # Move to the line after the answer
                                        i += 2
                                        continue
                        
                        i += 1
        
        doc.close()
        
    except Exception as e:
        print(f"[ERROR] Error in NPQ extraction: {e}")
    
    print(f"[DEBUG] Total extracted: {len(domain_data)} domains, {len(question_data)} questions")
    return domain_data, question_data

# --- NPQ Question Extraction with PyMuPDF ---
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
        "Obsessions & Compulsions Questions": "Obsessions & Compulsions", # Check "&" if needed
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
        "Asperger's Questions": "Asperger's", # Check apostrophe if needed
        "ADHD Questions": "ADHD",
        "MCI Questions": "MCI",
        "Concussion Questions": "Concussion",
        "Anxiety/Depression Questions": "Anxiety/Depression" # If this header exists
        # Add any missing ones based on the PDF content if necessary
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
                                
                                # Basic validation of extracted values
                                if 0 <= score <= 4 and severity:  # Allow score 4 just in case, though usually 0-3
                                    print(f"[DEBUG]  Q{current_question_num}: '{current_question_text[:40]}...' -> {score} - {severity} [{current_domain}]")
                                    question_data.append((current_question_num, current_question_text, score, severity, current_domain))
                                    
                                    # Reset after capturing a complete question
                                    current_question_text = None
                                else:
                                    print(f"[WARN] Invalid score/severity parsed in line: '{line}'")
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

# --- Main ---
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

def import_pdf_to_db(pdf_path):
    """Import PDF data to database."""
    global PDF_PATH  # Define global variable
    PDF_PATH = pdf_path  # Set global variable
    lines = extract_text_blocks(pdf_path)
    text = "\n".join(lines)  # for regex-based stuff if still needed
    
    patient_id, test_date, age, language = parse_basic_info(text)
    scores = parse_cognitive_scores(text, patient_id)
    
    with sqlite3.connect(DB_PATH) as conn:
        # Early exit if patient already exists
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM patients WHERE patient_id = ?", (patient_id,))
        if cur.fetchone():
            print(f"[INFO] Patient ID {patient_id} already exists. Skipping import.")
            return
        
        try:
            insert_patient(conn, patient_id, test_date, age, language)
            insert_cognitive_scores(conn, scores)
            log_section_status(conn, patient_id, "Cognitive Scores", "parsed" if scores else "missing")

            #----gnitive Subtests ---#
            subtests = parse_subtests_hardcoded(lines, patient_id)
            if subtests:
                conn.executemany("""
                    INSERT INTO subtest_results (patient_id, subtest_name, metric, score, standard_score, percentile)
                    VALUES (?, ?, ?, ?, ?, ?)""", subtests)
            #log_section_status(conn, patient_id, "Subtests", "parsed" if subtests else "missing")

            # --- ASRS ---
            asrs = parse_asrs_with_bounding_boxes(pdf_path, patient_id)

            conn.executemany("""
                INSERT INTO asrs_responses (patient_id, question_number, part, response)
                VALUES (?, ?, ?, ?)
            """, asrs)
            log_section_status(conn, patient_id, "ASRS", "parsed" if asrs else "missing")
            
            # --- DASS21 ---
            dass_summary, dass_items = parse_dass21(text, patient_id)
            if dass_summary:
                conn.execute("INSERT INTO dass21_scores (patient_id, depression, anxiety, stress) VALUES (?, ?, ?, ?)", dass_summary)
            if dass_items:
                conn.executemany("INSERT INTO dass21_responses (patient_id, question_number, response_score, response_text) VALUES (?, ?, ?, ?)", dass_items)
            log_section_status(conn, patient_id, "DASS21", "parsed" if (dass_summary or dass_items) else "missing")
                
            # --- Epworth ---
            epworth_score, epworth = parse_epworth(text, patient_id)
            if epworth:
                conn.executemany("INSERT INTO epworth_scores (patient_id, epworth_score, question_number, response) VALUES (?, ?, ?, ?)", epworth)
            log_section_status(conn, patient_id, "Epworth", "parsed" if epworth else "missing")
            
            # --- NPQ ---
            # Use the new table extraction approach
            domain_data, question_data = extract_npq_table(pdf_path)
            
            # Convert domain_data to the expected format for npq_scores
            npq_scores = []
            for domain, score, severity in domain_data:
                npq_scores.append((patient_id, domain, score, severity, ""))
            
            print("NPQ scores (about to insert):", npq_scores)
            
            if npq_scores:
                conn.executemany("""
                    INSERT INTO npq_scores (patient_id, domain, score, severity, description)
                    VALUES (?, ?, ?, ?, ?)""", npq_scores)

            log_section_status(conn, patient_id, "NPQ", "parsed" if npq_scores else "missing")
            
            # --- NPQ Questions (New PyMuPDF approach) ---
            extract_and_insert_npq_questions(pdf_path, patient_id, conn)

            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Failed to import PDF: {e}")
            raise
    print(f"Imported data for Patient ID {patient_id}")

# Main execution block
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python cognitive_importer.py path/to/file.pdf [--reset]")
    else:
        if "--reset" in sys.argv:
            create_db(reset=True)
        else:
            create_db(reset=False)
        import_pdf_to_db(sys.argv[1])
