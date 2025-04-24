import fitz  # PyMuPDF
import re
import os   # For file path operations if needed
import pdfplumber  # For finding NPQ pages

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

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python test_npq_extraction.py <pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    # Find NPQ pages
    npq_pages = find_npq_pages(pdf_path)
    
    if not npq_pages:
        print("[ERROR] No NPQ pages found in the PDF")
        sys.exit(1)
    
    # Extract NPQ questions
    question_data = extract_npq_questions_pymupdf(pdf_path, npq_pages)
    
    # Print summary of extracted data
    print("\n===== NPQ Question Extraction Summary =====")
    print(f"Total questions found: {len(question_data)}")
    
    # Group by domain for better readability
    domains = {}
    for q in question_data:
        domain = q[4]
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(q)
    
    # Print summary by domain
    for domain, questions in domains.items():
        print(f"\n{domain} ({len(questions)} questions):")
        for q in questions[:3]:  # Show first 3 questions per domain
            print(f"  Q{q[0]}: '{q[1][:40]}...' -> {q[2]} - {q[3]}")
        if len(questions) > 3:
            print(f"  ... and {len(questions) - 3} more questions")
