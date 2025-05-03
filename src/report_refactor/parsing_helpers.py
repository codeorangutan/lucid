import logging
logger = logging.getLogger(__name__)
logger.info("MODULE FINGERPRINT: parsing_helpers.py loaded from src/report_refactor at 2025-04-23T21:46:28+08:00")

import fitz  # PyMuPDF
import re
import os
import csv
import pdfplumber
import logging
from typing import List, Tuple, Dict, Any, Optional

# Use explicit relative import for DSM logic
from .asrs_dsm_mapper import RESPONSE_SCORES, LOWER_THRESHOLD_QUESTIONS, is_met, DSM5_ASRS_MAPPING

# Setup logging
logger = logging.getLogger(__name__)
# Configure logging further if needed (e.g., level, handler)
# logging.basicConfig(level=logging.INFO) # Example configuration

# --- Core Extraction Logic ---

def extract_text_blocks(pdf_path: str) -> List[str]:
    lines = []
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc):
            # Extract text blocks with layout information
            blocks = page.get_text("blocks")
            for b in blocks:
                # b contains (x0, y0, x1, y1, "text", block_no, block_type)
                # We just want the text for now
                lines.append(b[4].strip()) # Get the text content (index 4) and strip whitespace
        doc.close()
    except Exception as e:
        logger.error(f"Error extracting text blocks from {pdf_path}: {e}")
        lines = []

    # --- Debugging print statements replaced with logging ---
    logger.debug(f"Extracted {len(lines)} lines from {pdf_path} (showing first 10):")
    for idx, line in enumerate(lines[:10]):
        logger.debug(f"  [{idx}] {repr(line)}")
    # ------------------------------------------------------

    return lines # No need for 'or []' if initialized as [] and handled in except

def parse_basic_info(text):
    patient_id = int(re.search(r"Patient ID:\s*(\d+)", text).group(1))
    
    # Extract test date with a more comprehensive pattern to capture the full date
    test_date = re.search(r"Test Date:\s*([\w\s,:/\\-]+\d{2}:\d{2}:\d{2})", text)
    if test_date:
        test_date = test_date.group(1).strip()
    else:
        # Fallback to the original pattern if the full date isn't found
        test_date = re.search(r"Test Date:\s*([\w:/\\-]+)", text).group(1).strip()
    
    # Extract age
    age = int(re.search(r"Age:\s*(\d+)", text).group(1))
    
    language = re.search(r"Language:\s*(.+)", text).group(1).strip()
    
    # Return in the correct order: patient_id, test_date, age, language
    return patient_id, test_date, age, language

def parse_cognitive_scores(text, patient_id):
    scores = []
    # Adjusted regex to handle 'NA' and the specific Neurocognition Index format
    score_pattern = re.compile(r'^(.*?)\s+(?:NA\s+)?(\d+|NA)\s+(\d+)\s+(\d+)\s+(Yes|No)\s*X?$', re.MULTILINE)
    
    for match in score_pattern.finditer(text):
        logger.debug("Matched groups: %s", match.groups())
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


def parse_asrs_with_bounding_boxes(pdf_path, patient_id):
    # import fitz # Already imported at top
    # import os # Already imported at top
    # import csv # Already imported at top

    bounding_boxes_path = os.path.join(os.path.dirname(__file__), "bounding_boxes.csv")

    # Load bounding box data from CSV
    box_data = []
    SCALE_MM_TO_PT = 72 / 25.4  # Use this if your CSV is in mm

    try:
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
    except FileNotFoundError:
        logger.error(f"Bounding boxes file not found at: {bounding_boxes_path}")
        return [] # Cannot proceed without bounding boxes
    except Exception as e:
        logger.error(f"Error reading bounding boxes file: {e}")
        return []

    doc = fitz.open(pdf_path)
    responses = []

    try:
        # Ensure page index 3 exists before trying to access it
        if len(doc) > 3:
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
        else:
             logger.warning(f"PDF does not have a page 4 (index 3): {pdf_path}. Cannot parse ASRS with bounding boxes.")

    except Exception as e:
        logger.error(f"Error processing PDF for ASRS bounding box parsing: {e}")

    logger.info(f"Parsed {len(responses)} ASRS responses using bounding boxes on page 4.")
    return responses


def parse_epworth(text, patient_id):
    """
    Parse Epworth Sleepiness Scale data from text.
    
    Returns:
        dict: {'total_score': int, 'interpretation': str}, responses
            - total_score: The total Epworth score (sum of all individual scores)
            - interpretation: The interpretation of the total score
            - responses: List of tuples (patient_id, question_number, situation, score, description)
    """
    responses = []
    try:
        # Only match lines for questions 1–8
        pattern = re.findall(r"^\s*([1-8])\s+(.+?)\s+(\d)\s*-\s*(.+)$", text, re.MULTILINE)
        # Only process the first 8 Epworth questions
        for match in pattern[:8]:
            question_number = int(match[0])
            situation = match[1].strip()
            score = int(match[2])
            description = match[3].strip()
            responses.append((patient_id, question_number, situation, score, description))
        final_total = sum([r[3] for r in responses]) if responses else 0
        interpretation = ""
        if final_total is not None:
            if final_total <= 5:
                interpretation = "Lower Normal Daytime Sleepiness"
            elif final_total <= 10:
                interpretation = "Higher Normal Daytime Sleepiness"
            elif final_total <= 15:
                interpretation = "Mild Excessive Daytime Sleepiness"
            elif final_total <= 17:
                interpretation = "Moderate Excessive Daytime Sleepiness"
            else:
                interpretation = "Severe Excessive Daytime Sleepiness"
        return {'total_score': final_total, 'interpretation': interpretation}, responses
    except Exception as e:
        logger.error(f"Failed to parse Epworth Sleepiness Scale: {e}")
        return {'total_score': 0, 'interpretation': 'Error'}, []


def find_npq_pages(pdf_path):
    """Find pages that contain NPQ content"""
    npq_pages = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i in range(len(pdf.pages)):
                text = pdf.pages[i].extract_text()
                if text and ("NeuroPsych Questionnaire" in text or "Domain Score Severity" in text):
                    npq_pages.append(i)
                    logger.debug(f"Found NPQ on page {i+1}")
    except Exception as e:
        logger.error(f"Error opening or processing PDF for NPQ page finding: {e}")
        return [] # Return empty list on error
    
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
    logger.info("[DEBUG] FINGERPRINT: Entered extract_npq_questions_pymupdf in cognitive_importer at 2025-04-23T21:57:28+08:00")
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
        logger.warning("No NPQ page indices provided for question extraction.")
        return []
    
    try:
        doc = fitz.open(pdf_path)
        for page_idx in npq_pages_indices:
            if page_idx >= len(doc):
                logger.warning(f"Page index {page_idx} out of range for PDF.")
                continue
            
            logger.debug(f"Extracting NPQ questions from page {page_idx+1}")
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
                                logger.debug(f"Switched to NPQ domain: {current_domain}")
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
                                # Save the previous question if we have all its parts
                                if current_question_num is not None and current_question_text is not None:
                                     # Need score/severity which should come *after* the text
                                     pass # Wait for score/severity line
                                
                                # Start a new question
                                current_question_num = int(num_match.group(1))
                                current_question_text = "" # Reset text for the new question
                                continue # Move to the next line for the text
                            
                            # Check if this line is the score/severity
                            sev_match = severity_pattern.match(line)
                            if sev_match and current_question_num is not None and current_question_text is not None:
                                score = int(sev_match.group(1))
                                severity_desc = sev_match.group(2).strip()
                                
                                # Now we have all parts, record the question
                                question_data.append((
                                    current_question_num,
                                    current_question_text.strip(), 
                                    score, 
                                    severity_desc,
                                    current_domain
                                ))
                                logger.debug(f"  Recorded NPQ Q{current_question_num} in {current_domain}")
                                
                                # Reset for the next potential question
                                current_question_num = None
                                current_question_text = None
                                continue # Move to the next line
                                
                            # Otherwise, assume it's part of the question text
                            if current_question_num is not None:
                                current_question_text += " " + line # Append text

    except Exception as e:
        logger.error(f"Error during NPQ question extraction: {e}")
        # Potentially return partial data or empty list depending on desired robustness
        # return question_data 
        return [] # Return empty on error

    logger.info(f"Extracted {len(question_data)} NPQ questions.")
    return question_data

def parse_npq_questions_from_text(npq_section_text: str):
    """
    Fallback NPQ question parser: Extracts (question_number, question_text, score, severity) from section text.
    Handles lines like:
    '1. Trouble concentrating 2 Severe'
    '2. Forgetfulness 1 Mild'
    Returns a list of tuples.
    """
    logger.info("UNIQUE FINGERPRINT: fallback parser parse_npq_questions_from_text invoked.")
    logger.info("[DEBUG] Entered parse_npq_questions_from_text for NPQ fallback parsing.")
    import re
    results = []
    # Regex: question number, dot, question text, score, severity (score is 0-3, severity is word)
    pattern = re.compile(r'^(\d{1,2})[\).\s]+(.+?)\s+(\d)\s+(Mild|Moderate|Severe|None)\b', re.IGNORECASE)
    for line in npq_section_text.splitlines():
        match = pattern.match(line.strip())
        if match:
            qnum = int(match.group(1))
            qtext = match.group(2).strip()
            score = int(match.group(3))
            severity = match.group(4).capitalize()
            results.append((qnum, qtext, score, severity))
    return results

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

def parse_subtests_new(cognitive_text, patient_id):
    """Parse subtest scores using the hierarchical structure of the tests"""
    subtests = []
    current_test = None
    
    # Split into lines and clean
    lines = [line.strip() for line in cognitive_text.split('\n') if line.strip()]
    
    logger.debug("\nDEBUG: === Processing Lines ===")
    try:
        for line in lines:
            logger.debug(f"LINE: {line}")
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
                logger.debug(f"DEBUG: Found test section: {current_test}")
                continue
            
            # Try to match score pattern for metrics
            if current_test:
                # Look for lines with 3-4 numbers (score, standard, percentile)
                numbers = [n for n in line.split() if n.replace('.', '').isdigit() or n == 'NA']
                if 3 <= len(numbers) <= 4:
                    # Extract the metric name (everything before the first number)
                    metric_match = re.match(r"^(.*?)(?=\s+(?:NA|\d))", line)
                    metric = metric_match.group(1).strip() if metric_match else "Unknown Metric"
                    
                    # Additional check to avoid grabbing parts of the previous line or instructions
                    if metric and len(metric) > 2 and not metric.isdigit(): 
                        try:
                            score_val = numbers[0] if numbers[0] == 'NA' else float(numbers[0])
                            # Determine standard score and percentile based on number count
                            if len(numbers) == 4: # Score, ?, Std, Perc
                                std_score = int(numbers[2])
                                percentile = int(numbers[3])
                            elif len(numbers) == 3: # Score, Std, Perc
                                std_score = int(numbers[1])
                                percentile = int(numbers[2])
                            else: # Should not happen based on len check, but defensively
                                raise IndexError("Unexpected number of values found.")

                            logger.debug(f"DEBUG: Found score - Test: {current_test}, Metric: {metric}, Score: {score_val}, Std: {std_score}, Perc: {percentile}")
                            
                            subtests.append((
                                patient_id,
                                current_test,
                                metric,
                                score_val if score_val != 'NA' else None,
                                std_score,
                                percentile
                            ))
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error parsing score line '{line}': {e}. Numbers found: {numbers}")
                    else:
                         logger.debug(f"Skipping potential score line, metric invalid: '{line}' -> Metric: '{metric}'")
                         
            # Reset current_test if we encounter a line that looks like instructions or is very long
            # Example heuristic: More than 10 words and no clear score pattern might indicate a break
            elif len(line.split()) > 10 and not re.search(r'\d+\s+\d+$', line):
                 logger.debug(f"Resetting current_test due to line: {line}")
                 current_test = None
    
    except Exception as e:
        logger.error(f"Error parsing subtests: {e}")
    
    logger.info(f"Parsed {len(subtests)} subtest results.")
    return subtests

def extract_dsm_diagnosis(asrs_responses, patient_id):
    """
    Extract DSM diagnosis information from ASRS responses using ASRS_DSM_mapper logic.
    
    Args:
        asrs_responses: List of tuples (patient_id, question_number, part, response)
        patient_id: Patient ID
        
    Returns:
        dict: {
            'inattentive_criteria_met': int,
            'hyperactive_criteria_met': int,
            'diagnosis': str,
            'dsm_criteria_data': list
        }
    """
    try:
        # Import ASRS_DSM_mapper functionality - already handled at top level with try/except
        # from asrs_dsm_mapper import RESPONSE_SCORES, LOWER_THRESHOLD_QUESTIONS, is_met, DSM5_ASRS_MAPPING
        
        # Convert asrs_responses to a dictionary format expected by ASRS_DSM_mapper
        responses_dict = {}
        for item in asrs_responses:
            # Support both tuple and dict formats
            if isinstance(item, dict):
                question_num = item.get('question_number')
                response = item.get('response')
            else:
                _, question_num, _, response = item
            responses_dict[question_num] = response
        
        # Count met criteria for inattention (A1-A9) and hyperactivity (B1-B9)
        met_inattentive = 0
        met_hyperactive = 0
        dsm_criteria_data = []
        
        # Check inattention criteria (questions 1-9)
        for i in range(9):
            dsm_crit, asrs_text, q_num = DSM5_ASRS_MAPPING[i]
            resp = responses_dict.get(q_num, "N/A")
            criterion_met = is_met(resp, q_num)
            if criterion_met:
                met_inattentive += 1
            
            dsm_criteria_data.append((
                dsm_crit,
                "Inattention",
                1 if criterion_met else 0
            ))
        
        # Check hyperactivity criteria (questions 10-18)
        for i in range(9, 18):
            dsm_crit, asrs_text, q_num = DSM5_ASRS_MAPPING[i]
            resp = responses_dict.get(q_num, "N/A")
            criterion_met = is_met(resp, q_num)
            if criterion_met:
                met_hyperactive += 1
            
            dsm_criteria_data.append((
                dsm_crit,
                "Hyperactivity/Impulsivity",
                1 if criterion_met else 0
            ))
        
        # Determine diagnosis based on criteria met
        if met_inattentive >= 5 and met_hyperactive >= 5:
            diagnosis = "Combined Presentation"
        elif met_inattentive >= 5:
            diagnosis = "Predominantly Inattentive Presentation"
        elif met_hyperactive >= 5:
            diagnosis = "Predominantly Hyperactive-Impulsive Presentation"
        else:
            diagnosis = "No ADHD Diagnosis Made"
        
        return {
            'inattentive_criteria_met': met_inattentive,
            'hyperactive_criteria_met': met_hyperactive,
            'diagnosis': diagnosis,
            'dsm_criteria_data': dsm_criteria_data
        }
    except Exception as e:
        logger.error(f"Failed to extract DSM diagnosis: {e}")
        return {
            'inattentive_criteria_met': 0,
            'hyperactive_criteria_met': 0,
            'diagnosis': "Error in Diagnosis",
            'dsm_criteria_data': []
        }

def parse_cognitive_subtests_from_pdf(pdf_path: str, debug: bool = False) -> list[dict]:
    """
    Extracts cognitive subtests from a PDF using integrated logic.
    (Currently only extracts text, parsing logic to be added).
    Returns data formatted as a list of dictionaries.
    """
    lines = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Limit pages similar to original logic (e.g., first 5)
            num_pages = min(5, len(pdf.pages))
            for i in range(num_pages):
                page = pdf.pages[i]
                # Use layout=True for better table/column structure preservation if needed
                page_text = page.extract_text(x_tolerance=1, y_tolerance=1, layout=False)
                if page_text:
                    # Add page markers for context if needed during debugging
                    # lines.append(f"\n=== PAGE {i + 1} TEXT CONTENT ===\n")
                    lines.extend(page_text.splitlines())

        if not lines:
            if debug: logger.debug(f"Warning: No text extracted from the first {num_pages} pages of {pdf_path}")
            return []

        if debug: logger.debug(f"Extracted {len(lines)} lines from {pdf_path}")

    except Exception as e:
        logger.error(f"Error opening or reading PDF {pdf_path}: {e}")
        return []

    # --- Parsing logic will be added here in the next step --- #
    parsed_subtests = [] # Placeholder for results

    # --- Final formatting will be added later --- #
    formatted_results = [] # Placeholder

    # --- Start of integrated parsing logic (adapted from parse_text_file) ---
    results = {}
    current_test = None
    current_data = []
    current_section = None
    parsing_data = False
    in_domain_scores = False # Flag to skip domain score sections

    # Regex patterns
    # Matches typical test headers like "Test Name (ACR)" possibly followed by Score/Std/Percentile or Validity info
    test_pattern = re.compile(r"^(.*?(?:Test|Index|Assessment|Scale)\s+\([A-Z]{2,6}\))(?:\s*Score\s+Standard\s+Percentile)?(?:\s*\(?(?:Invalid|Possibly Invalid)\)?)?$", re.IGNORECASE)
    # Matches data rows like "Measure Name   10   100   50"
    data_row_pattern = re.compile(r"^([^0-9\n\-\.]{3,}?)\s+(-?\d+\.?\d*|-|NA|N/A|\.\d+)\s+(-?\d+\.?\d*|-|NA|N/A|\.\d+)\s+(-?\d+\.?\d*|-|NA|N/A|\.\d+)(?:\s*$|\s+.*$)", re.IGNORECASE)
    # Matches lines with data followed by text e.g. "Measure Name   10   100   50 Some Text"
    mixed_line_pattern = re.compile(r"^([^0-9\n\-\.]{3,}?)\s+(-?\d+\.?\d*|-|NA|N/A|\.\d+)\s+(-?\d+\.?\d*|-|NA|N/A|\.\d+)\s+(-?\d+\.?\d*|-|NA|N/A|\.\d+)([A-Za-z].*$)", re.IGNORECASE)
    # Matches section headers like "Part 1" or "Section 2"
    section_pattern = re.compile(r"^(Part\s+\d+|Section\s+\d+)$", re.IGNORECASE)
    # Matches the start of the cognitive domain scores section
    domain_scores_pattern = re.compile(r"^Domain\s+Scores", re.IGNORECASE)
    # Matches typical lines indicating the end of domain scores or start of other sections
    domain_end_pattern = re.compile(r"^(?:VI\*\*\s*-\s*Validity Indicator:|Description of Cognitive Domains|Interpretation Guidelines|Overall Test Session Comments)", re.IGNORECASE)
    # Matches typical description lines to ignore
    description_pattern = re.compile(r"^(?:The\s+)?[A-Za-z]+\s+(?:test|memory|measures|is a|provides|yields)", re.IGNORECASE)
    # Matches the typical table header for data rows
    header_pattern = re.compile(r"^Measure\s+(?:Raw\s*)?Score\s+(?:Scaled\s*|Standard\s*)Score\s+Percentile", re.IGNORECASE)
    # Used later for validity checking within the formatted results
    validity_in_name_pattern = re.compile(r"(?:Invalid|Possibly Invalid)", re.IGNORECASE)

    # Known test names mapping (lowercase key for matching, original case value for output)
    # This helps standardize names like "Symbol Digit Coding Test (SDC)"
    known_tests = {
        "symbol digit coding test (sdc)": "Symbol Digit Coding Test (SDC)",
        "symbol digit coding (sdc)": "Symbol Digit Coding Test (SDC)",
        "stroop test (st)": "Stroop Test (ST)",
        "shifting attention test (sat)": "Shifting Attention Test (SAT)",
        "continuous performance test (cpt)": "Continuous Performance Test (CPT)",
        "four part continuous performance test (fpcpt)": "Four Part Continuous Performance Test (FPCPT)",
        "four part continuous performance test (fpcpt-ii)": "Four Part Continuous Performance Test (FPCPT)",
        "verbal learning test (vlt)": "Verbal Learning Test (VLT)",
        "visual learning test (vslt)": "Visual Learning Test (VSLT)",
        "reasoning test (rt)": "Reasoning Test (RT)",
        "working memory index (wmi)": "Working Memory Index (WMI)"
        # Add other known variations as needed
    }

    if debug:
        logger.debug(f"\nProcessing text ({len(lines)} lines) from: {pdf_path}")

    # --- Main parsing loop --- #
    for i, line in enumerate(lines):
        line = line.strip()
        line_lower = line.lower()
        if debug:
            logger.debug(f"Line {i}: '{line}' (current_test={current_test}, parsing_data={parsing_data}, in_domain_scores={in_domain_scores})")

        # Log detection of test headers
        match = test_pattern.match(line)
        if match:
            test_name = match.group(1).strip()
            if debug:
                logger.debug(f"Detected test header at line {i}: '{test_name}'")

        # Log detection of data rows
        if data_row_pattern.match(line):
            if debug:
                logger.debug(f"Detected data row at line {i}: '{line}' (current_test={current_test})")

        # Log section headers
        if section_pattern.match(line):
            if debug:
                logger.debug(f"Detected section header at line {i}: '{line}'")

        # Log when skipping domain scores
        if domain_scores_pattern.match(line):
            if debug:
                logger.debug(f"Detected start of domain scores at line {i}: '{line}'")
        if domain_end_pattern.match(line):
            if debug:
                logger.debug(f"Detected end of domain scores at line {i}: '{line}'")

        # Log when skipping description lines
        if description_pattern.match(line):
            if debug:
                logger.debug(f"Skipping description line at line {i}: '{line}'")

        # Log when header row detected
        if header_pattern.match(line):
            if debug:
                logger.debug(f"Detected table header at line {i}: '{line}'")

        # Handle domain scores section skipping
        if not in_domain_scores and domain_scores_pattern.search(line_lower):
            in_domain_scores = True
            if debug: logger.debug(f"Line {i+1}: Entering domain scores section based on '{line}'")
            parsing_data = False # Stop parsing previous test data if we hit this section
            if current_test and current_data: # Save any pending test data
                results[current_test] = current_data
                if debug: logger.debug(f"Saved previous test (due to domain scores): {current_test} with {len(current_data)} data rows")
                current_test, current_data, current_section = None, [], None # Reset
            continue
        if in_domain_scores and domain_end_pattern.search(line_lower):
            in_domain_scores = False
            if debug: logger.debug(f"Line {i+1}: Exiting domain scores section based on '{line}'")
            continue
        if in_domain_scores:
            continue # Skip lines within the domain scores section

        # Ignore known headers or descriptive lines that don't contain actual data
        if header_pattern.match(line) or description_pattern.match(line):
            if debug: logger.debug(f"Line {i+1}: Skipping header/description line: '{line}'")
            continue

        # Check for test headers first (most specific pattern)
        test_match = test_pattern.match(line)
        if test_match:
            # Save previous test data before starting a new one
            if current_test and current_data:
                results[current_test] = current_data
                if debug: logger.debug(f"Saved previous test: {current_test} with {len(current_data)} data rows")

            test_name_raw = test_match.group(1).strip()
            test_name_key = test_name_raw.lower()
            # Standardize the test name using the known_tests mapping
            current_test = known_tests.get(test_name_key, test_name_raw)
            current_data = [] # Reset data for the new test
            current_section = None # Reset section for the new test
            parsing_data = True # Indicate that we are now looking for data rows for this test
            if debug: logger.debug(f"Line {i+1}: Found test header: '{current_test}' from line '{line}'")
            continue # Move to next line after finding a header

        # If we are potentially parsing a test's data (parsing_data is True)
        if parsing_data and current_test:
            # Check for section headers (e.g., Part 1)
            section_match = section_pattern.match(line)
            if section_match:
                current_section = section_match.group(0).strip()
                if debug: logger.debug(f"Line {i+1}: Found section: {current_section} for test {current_test}")
                continue # Move to next line

            # Check for standard data rows
            data_match = data_row_pattern.match(line)
            if data_match:
                measure = data_match.group(1).strip()
                # Standardize missing values like '-' or 'NA' to None for consistency
                score = data_match.group(2).strip().upper().replace('NA', '-').replace('N/A', '-')
                standard = data_match.group(3).strip().upper().replace('NA', '-').replace('N/A', '-')
                percentile = data_match.group(4).strip().upper().replace('NA', '-').replace('N/A', '-')

                # Basic validity check for the measure name (skip if too short/numeric/irrelevant)
                if len(measure) < 2 or measure.isdigit() or measure.lower() in ["score", "standard", "percentile", "scaled score", "raw score", "standard score"]:
                    if debug: logger.debug(f"Line {i+1}: Skipping likely non-measure data line: '{line}'")
                    continue

                data_dict = {
                    "Measure": measure,
                    "Score": score if score != '-' else None,
                    "Standard": standard if standard != '-' else None,
                    "Percentile": percentile if percentile != '-' else None
                }
                if current_section:
                    data_dict["Section"] = current_section
                current_data.append(data_dict)
                if debug: logger.debug(f"Line {i+1}: Found data row for {current_test}: {data_dict}")
                continue # Move to next line

            # Check for mixed lines (data + potentially ignorable text)
            mixed_match = mixed_line_pattern.match(line)
            if mixed_match:
                measure = mixed_match.group(1).strip()
                score = mixed_match.group(2).strip().upper().replace('NA', '-').replace('N/A', '-')
                standard = mixed_match.group(3).strip().upper().replace('NA', '-').replace('N/A', '-')
                percentile = mixed_match.group(4).strip().upper().replace('NA', '-').replace('N/A', '-')
                # remaining_text = mixed_match.group(5).strip() # Can be logged if needed

                # Apply similar validity check for the measure name
                if len(measure) < 2 or measure.isdigit() or measure.lower() in ["score", "standard", "percentile", "scaled score", "raw score", "standard score"]:
                    if debug: logger.debug(f"Line {i+1}: Skipping likely non-measure mixed line: '{line}'")
                    continue

                data_dict = {
                    "Measure": measure,
                    "Score": score if score != '-' else None,
                    "Standard": standard if standard != '-' else None,
                    "Percentile": percentile if percentile != '-' else None
                }
                if current_section:
                    data_dict["Section"] = current_section
                current_data.append(data_dict)
                if debug: logger.debug(f"Line {i+1}: Found mixed data row for {current_test}: {data_dict}")
                # Let loop continue, don't add `continue` here as the rest of the line might be relevant
                # or the next line might continue the same logical block.

    # --- End of parsing loop --- #

    # Save the last processed test's data if any exists
    if current_test and current_data:
        results[current_test] = current_data
        if debug: logger.debug(f"Saved final test: {current_test} with {len(current_data)} data rows")

    # --- Formatting logic will be added here --- #
    # Convert intermediate results to the final list of dictionaries
    formatted_results = []
    validity_in_name_pattern = re.compile(r"(?:Invalid|Possibly Invalid)", re.IGNORECASE)

    if debug and not results:
        logger.debug("No test results were parsed.")

    for test_name, measures in results.items():
        # Determine test validity
        is_valid = 1  # Default to valid (True)
        validity_explicitly_stated = False

        # 1. Check for explicit "Validity" measure
        for measure in measures:
            measure_name_lower = measure.get("Measure", "").lower()
            if measure_name_lower == "validity":
                validity_info = str(measure.get('Score', "")).lower()
                if "invalid" in validity_info:
                    is_valid = 0
                    if debug: logger.debug(f"Marking '{test_name}' as INVALID based on explicit validity measure: '{measure.get('Score')}'")
                else:
                    # If validity is explicitly stated as anything else (e.g., 'Valid', 'Acceptable'), assume valid
                    is_valid = 1
                validity_explicitly_stated = True
                break # Stop after finding the explicit validity measure

        # 2. If not explicitly stated, check if test name contains invalid keywords
        if not validity_explicitly_stated and validity_in_name_pattern.search(test_name):
            is_valid = 0
            if debug: logger.debug(f"Marking '{test_name}' as INVALID based on keywords in its name.")

        if debug:
             logger.debug(f"Final validity for '{test_name}': {'VALID' if is_valid == 1 else 'INVALID'}")

        # Format each measure into a dictionary entry
        for measure in measures:
            # Skip the Validity measure itself from the final output
            if measure.get("Measure", "").lower() == "validity":
                continue

            # Skip entries where essential scores are missing (use the None values we stored)
            score = measure.get("Score")
            standard = measure.get("Standard")
            percentile = measure.get("Percentile")

            # We might still want to record the measure even if scores are missing, depending on requirements.
            # Let's include them but allow filtering later if needed.
            # if score is None and standard is None and percentile is None:
            #     if debug: logger.debug(f"Skipping measure '{measure.get('Measure')}' for test '{test_name}' due to all scores being None.")
            #     continue

            # Construct the metric name, including section if present
            metric = measure.get("Measure", "Unknown Measure")
            if "Section" in measure:
                metric = f"{metric} - {measure['Section']}"

            # Append the dictionary to the final list
            formatted_results.append({
                # 'patient_id' is handled during DB insertion relative to session_id
                'subtest_name': test_name,
                'metric': metric,
                'score': score, # Keep as is (string or None)
                'standard_score': standard, # Keep as is (string or None)
                'percentile': percentile, # Keep as is (string or None)
                'is_valid': is_valid # Store validity (0 or 1)
            })

    if debug:
        logger.debug(f"Formatted {len(formatted_results)} cognitive subtest entries.")

    if debug:
        logger.debug(f"Returning {len(formatted_results)} formatted subtest results from {pdf_path}")
    return formatted_results

def parse_text_file_lines(lines):
    """
    Parse cognitive test data from a list of text lines (from PDF) using a robust line-by-line approach.
    Returns a dictionary of test results keyed by test name.
    """
    results = {}
    current_test = None
    current_data = []
    current_section = None
    parsing_data = False
    in_domain_scores = False
    # Patterns
    test_pattern = re.compile(r"^(.*?(?:Test|Index)\s+\([A-Z]{2,5}\))(?:\s*(?:Score\s+Standard\s+Percentile))?(?:\s*(?:Invalid|Possibly Invalid))?$")
    data_row_pattern = re.compile(r"^([^0-9\n]{3,}?)\s+(-?\d+|-|NA|0)\s+(-?\d+|-|NA|0)\s+(-?\d+|-|NA|0)(?:\s*$|\s+.*$)")
    mixed_line_pattern = re.compile(r"^([^0-9\n]{3,}?)\s+(-?\d+|-|NA|0)\s+(-?\d+|-|NA|0)\s+(-?\d+|-|NA|0)([A-Za-z].*$)")
    section_pattern = re.compile(r"^Part\s+\d+$")
    domain_scores_pattern = re.compile(r"^Domain\s+ScoresPatient")
    domain_end_pattern = re.compile(r"^VI\*\* - Validity Indicator:")
    description_pattern = re.compile(r"^(?:The\s+)?[A-Za-z]+\s+(?:test|memory|measures|is a)")
    # Known test names
    known_tests = {
        "Symbol Digit Coding Test (SDC)": "Symbol Digit Coding Test (SDC)",
        "Symbol Digit Coding (SDC)": "Symbol Digit Coding Test (SDC)",
        "Stroop Test (ST)": "Stroop Test (ST)",
        "Shifting Attention Test (SAT)": "Shifting Attention Test (SAT)",
        "Continuous Performance Test (CPT)": "Continuous Performance Test (CPT)",
        "Four Part Continuous Performance Test (FPCPT)": "Four Part Continuous Performance Test (FPCPT)"
    }
    # First scan for test headers and validity
    test_validity = {}
    for line in lines:
        line = line.strip()
        if "Test" in line and "(" in line and ")" in line:
            is_invalid = False
            if "Invalid" in line or "Possibly Invalid" in line:
                is_invalid = True
            test_match = test_pattern.match(line)
            if test_match:
                test_name = test_match.group(1).strip()
                if test_name in known_tests:
                    test_name = known_tests[test_name]
                test_validity[test_name] = is_invalid
    # Now process lines
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("=== PAGE") and "TEXT CONTENT" in line:
            continue
        if domain_scores_pattern.match(line):
            in_domain_scores = True
            continue
        if in_domain_scores and domain_end_pattern.match(line):
            in_domain_scores = False
            continue
        if in_domain_scores:
            continue
        if "Symbol Digit Coding" in line and "(SDC)" in line:
            if current_test and current_data:
                results[current_test] = current_data
            current_test = "Symbol Digit Coding Test (SDC)"
            current_data = []
            current_section = None
            parsing_data = True
            continue
        test_match = test_pattern.match(line)
        if test_match:
            test_name = test_match.group(1).strip()
            if current_test and current_data:
                results[current_test] = current_data
            if test_name in known_tests:
                current_test = known_tests[test_name]
            else:
                current_test = test_name
            current_data = []
            current_section = None
            parsing_data = True
            continue
        if current_test == "Four Part Continuous Performance Test (FPCPT)" and section_pattern.match(line):
            current_section = line.strip()
            continue
        if parsing_data:
            mixed_match = mixed_line_pattern.match(line)
            if mixed_match:
                measure = mixed_match.group(1).strip()
                score_str = mixed_match.group(2)
                standard_str = mixed_match.group(3)
                percentile_str = mixed_match.group(4)
                if measure.lower() in ['score', 'standard', 'percentile']:
                    continue
                try: score = int(score_str) if score_str not in ['-', 'NA'] else score_str
                except ValueError: score = score_str
                try: standard = int(standard_str) if standard_str not in ['-', 'NA'] else standard_str
                except ValueError: standard = standard_str
                try: percentile = int(percentile_str) if percentile_str not in ['-', 'NA'] else percentile_str
                except ValueError: percentile = percentile_str
                data_entry = {"Measure": measure, "Score": score, "Standard": standard, "Percentile": percentile}
                if current_section:
                    data_entry["Section"] = current_section
                current_data.append(data_entry)
                parsing_data = False
                continue
            if description_pattern.match(line):
                parsing_data = False
                continue
            data_match = data_row_pattern.match(line)
            if data_match:
                measure = data_match.group(1).strip()
                score_str = data_match.group(2)
                standard_str = data_match.group(3)
                percentile_str = data_match.group(4)
                if measure.lower() in ['score', 'standard', 'percentile']:
                    continue
                try: score = int(score_str) if score_str not in ['-', 'NA'] else score_str
                except ValueError: score = score_str
                try: standard = int(standard_str) if standard_str not in ['-', 'NA'] else standard_str
                except ValueError: standard = standard_str
                try: percentile = int(percentile_str) if percentile_str not in ['-', 'NA'] else percentile_str
                except ValueError: percentile = percentile_str
                data_entry = {"Measure": measure, "Score": score, "Standard": standard, "Percentile": percentile}
                if current_section:
                    data_entry["Section"] = current_section
                current_data.append(data_entry)
                continue
    # Save last test
    if current_test and current_data:
        results[current_test] = current_data
    # Add missing measures
    add_missing_measures(results)
    # Add validity info
    for test_name, is_invalid in test_validity.items():
        if test_name in results:
            results[test_name].append({
                "Measure": "Validity",
                "Score": "Invalid" if is_invalid else "Valid",
                "Standard": "-",
                "Percentile": "-"
            })
    return results


def get_cognitive_subtests(pdf_path, patient_id, debug=False):
    """
    Extract cognitive subtests from a PDF file using robust text parsing logic.
    Returns a list of tuples: (patient_id, subtest_name, metric, score, standard_score, percentile, is_valid)
    """
    lines = extract_text_blocks(pdf_path)
    if not lines:
        logger.error("Failed to extract text from PDF.")
        return []
    results = parse_text_file_lines(lines)
    formatted_results = []
    for test_name, measures in results.items():
        is_valid = 1
        for measure in measures:
            if measure["Measure"] == "Validity" and measure["Score"] == "Invalid":
                is_valid = 0
        if is_valid == 1 and ("Invalid" in test_name or "Possibly Invalid" in test_name):
            is_valid = 0
        for measure in measures:
            if measure["Score"] == "-" or measure["Standard"] == "-" or measure["Percentile"] == "-":
                continue
            if measure["Measure"] == "Validity":
                continue
            metric = measure["Measure"]
            if "Section" in measure:
                metric = f"{metric} - {measure['Section']}"
            formatted_results.append((
                patient_id,
                test_name,
                metric,
                measure["Score"],
                measure["Standard"],
                measure["Percentile"],
                is_valid
            ))
    if debug:
        logger.info(f"Extracted {len(formatted_results)} cognitive subtest entries")
    return formatted_results

def extract_subtest_data(table, debug=False):
    """
    Extract subtest data from a pdfplumber table.
    Returns a list of (test_name, metric, score, std, perc) tuples.
    Skips header rows, section headers, and rows with missing/non-numeric data.
    """
    subtests = []
    known_headers = {"score", "standard", "percentile", "raw", "measure", "metric"}
    known_section_prefixes = ("part ", "section ")
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
    
    # Check if this is a Four Part CPT table
    is_four_part_cpt = False
    if table and len(table) > 0 and table[0] and len(table[0]) > 0 and table[0][0]:
        first_cell = str(table[0][0]).strip()
        is_four_part_cpt = "Four Part Continuous Performance Test" in first_cell
    
    current_test_name = None
    current_part = None  # Track the current part for Four Part CPT
    
    for row in table[1:]:
        if not row or all(cell is None or str(cell).strip() == '' for cell in row):
            if debug:
                logger.debug(f"Skipping empty or all-None row: {row}")
            continue
        
        first_cell = str(row[0]).strip() if row[0] is not None else ""
        
        # Skip if row is a column header row
        if all(str(cell).strip().lower() in known_headers for cell in row if cell is not None and str(cell).strip() != ""):
            if debug:
                logger.debug(f"Skipping full header row: {row}")
            continue
        
        # Update current_test_name if this row is a test name row
        if any(first_cell.startswith(test) for test in known_tests):
            current_test_name = first_cell
            if debug:
                logger.debug(f"Test name updated: {current_test_name}")
            continue  # Do not treat this as data
        
        # For Four Part CPT, track the part headers (Part 1, Part 2, etc.)
        if is_four_part_cpt and first_cell.lower().startswith("part "):
            current_part = first_cell
            if debug:
                logger.debug(f"Found Part marker in Four Part CPT: {current_part}")
            continue  # Skip part header row
        
        # Skip if first cell is a known header or section
        if first_cell.lower() in known_headers or any(first_cell.lower().startswith(prefix) for prefix in known_section_prefixes):
            if debug:
                logger.debug(f"Skipping header/section row: {row}")
            continue
        
        try:
            if '\n' in first_cell:
                metrics = [m.strip() for m in first_cell.split('\n') if m.strip()]
                scores = [s.strip() for s in str(row[1]).split('\n') if s.strip()]
                standards = [s.strip() for s in str(row[2]).split('\n') if s.strip()]
                percentiles = [p.strip() for p in str(row[3]).split('\n') if p.strip()]
            else:
                metrics = [first_cell]
                scores = [str(row[1]).strip() if row[1] is not None else ""]
                standards = [str(row[2]).strip() if row[2] is not None else ""]
                percentiles = [str(row[3]).strip() if row[3] is not None else ""]
            
            for i in range(len(metrics)):
                metric = metrics[i]
                try:
                    score = float(scores[i]) if scores[i] else None
                    std = int(standards[i]) if standards[i] else None
                    perc = int(percentiles[i]) if percentiles[i] else None
                    
                    # For Four Part CPT, append the part to the metric if available
                    if is_four_part_cpt and current_part and not metric.endswith(current_part):
                        metric = f"{metric} {current_part}"
                        if debug:
                            logger.debug(f"Enhanced metric with part: '{metric}'")
                    
                    if current_test_name:
                        subtests.append((current_test_name, metric, score, std, perc))
                    else:
                        subtests.append((metric, score, std, perc))
                except Exception as e:
                    if debug:
                        logger.debug(f"Skipping metric row due to conversion error: metric={metric}, score={scores[i]}, std={standards[i]}, perc={percentiles[i]} | {e}")
                    continue
        except Exception as e:
            logger.warning(f"[WARN] Failed row parse: {row} 0b6 {e}")
    
    return subtests

def parse_all_subtests(pdf_path, patient_id, debug=False):
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
            text = page.extract_text() or ""
            tables = page.extract_tables()
            for test_name in known_tests:
                if test_name in text:
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        if test_name.split()[0] not in (table[0][0] or ""):
                            continue  # crude match
                        parsed = extract_subtest_data(table, debug=debug)
                        for idx, row in enumerate(parsed):
                            # row can be (test_name, metric, score, std, perc) or (metric, score, std, perc)
                            if len(row) == 5:
                                test_name_row, metric, score, std, perc = row
                                # Prefer row's test_name if present, else fallback to loop test_name
                                use_test_name = test_name_row if test_name_row else test_name
                            elif len(row) == 4:
                                metric, score, std, perc = row
                                use_test_name = test_name
                            else:
                                logger.warning(f"Unexpected row length from extract_subtest_data: {row}")
                                continue
                            all_results.append({
                                'patient_id': patient_id,
                                'subtest_name': use_test_name,
                                'metric': metric,
                                'score': score,
                                'standard_score': std,
                                'percentile': perc,
                                'is_valid': 1
                            })
    if debug:
        logger.debug(f"[DEBUG] Parsed {len(all_results)} subtest entries.")
    return all_results

def parse_cognitive_subtests_from_pdf(pdf_path: str, debug: bool = False) -> list[dict]:
    try:
        import re
        m = re.search(r"(\d+)", os.path.basename(pdf_path))
        patient_id = int(m.group(1)) if m else None
    except Exception:
        patient_id = None
    results = parse_all_subtests(pdf_path, patient_id, debug=debug)
    if debug:
        logger.debug(f"[DEBUG] parse_cognitive_subtests_from_pdf found {len(results)} subtests.")
    return results

def parse_all_cognitive_subtests_from_pdf(pdf_path, patient_id, debug=False):
    """
    Extract all cognitive subtest results from a PDF using table-driven parsing.
    Returns a list of tuples:
      (patient_id, test_name, metric, score, standard, percentile)
    """
    import pdfplumber
    import logging
    logger = logging.getLogger(__name__)
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
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                tables = page.extract_tables()
                if debug:
                    logger.debug(f"Page {page_num+1}: {len(tables)} tables found.")
                for test_name in known_tests:
                    if test_name in text:
                        for table in tables:
                            if not table or len(table) < 2:
                                continue
                            if test_name.split()[0] not in (table[0][0] or ""):
                                continue
                            # Use robust extract_subtest_data logic
                            try:
                                subtest_rows = extract_subtest_data(table, debug=debug)
                                for idx, row in enumerate(subtest_rows):
                                    # row can be (test_name, metric, score, std, perc) or (metric, score, std, perc)
                                    if len(row) == 5:
                                        test_name_row, metric, score, std, perc = row
                                        # Prefer row's test_name if present, else fallback to loop test_name
                                        use_test_name = test_name_row if test_name_row else test_name
                                    elif len(row) == 4:
                                        metric, score, std, perc = row
                                        use_test_name = test_name
                                    else:
                                        logger.warning(f"Unexpected row length from extract_subtest_data: {row}")
                                        continue
                                    all_results.append((patient_id, use_test_name, metric, score, std, perc))
                                    if debug:
                                        logger.debug(f"Appended: {patient_id}, {use_test_name}, {metric}, {score}, {std}, {perc}")
                            except Exception as e:
                                logger.warning(f"Failed to parse table for {test_name} on page {page_num+1}: {e}")
        if debug:
            logger.info(f"Total subtest results parsed: {len(all_results)}")
        return all_results
    except Exception as e:
        logger.error(f"Error parsing cognitive subtests from PDF: {e}")
        return []

def extract_npq_domain_scores_from_pdf(pdf_path, npq_pages_indices):
    """
    Extracts NPQ Domain Scores from tables within a PDF using pdfplumber.
    Looks for tables containing 'Domain', 'Score', and 'Severity' headers.

    Args:
        pdf_path (str): Path to the PDF file.
        npq_pages_indices (List[int]): List of 0-based page indices containing NPQ content.

    Returns:
        List[Tuple[str, int, str]]: A list of tuples, where each tuple contains:
                                     (domain_name, score, severity)
    """
    import pdfplumber
    import logging
    logger = logging.getLogger(__name__)
    domain_data = []
    if not npq_pages_indices:
        logger.warning("No NPQ page indices provided for domain score extraction.")
        return []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_tables = []
            for page_idx in npq_pages_indices:
                if page_idx >= len(pdf.pages):
                    logger.warning(f"Page index {page_idx} out of range for PDF during domain score extraction.")
                    continue
                page = pdf.pages[page_idx]
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)
            for table in all_tables:
                if table and len(table) > 0:
                    header_row = table[0]
                    if header_row and len(header_row) >= 3:
                        header_cells = [str(cell).strip().lower() if cell else "" for cell in header_row]
                        if "domain" in header_cells[0] and "score" in header_cells[1]:
                            for row in table[1:]:
                                if not row or len(row) < 3 or not row[0]:
                                    continue
                                domain = str(row[0]).strip()
                                score_str = str(row[1]).strip() if row[1] else ""
                                severity = str(row[2]).strip() if row[2] else ""
                                if domain.lower() == "domain" or not score_str.isdigit():
                                    continue
                                try:
                                    score = int(score_str)
                                    domain_data.append((domain, score, severity))
                                except (ValueError, TypeError):
                                    continue
    except Exception as e:
        logger.error(f"Error extracting NPQ domain scores: {e}")
        return []
    return domain_data

# --- Utility: Safe conversion for numeric fields ---
def safe_float(val):
    try:
        if val is None:
            return None
        val = str(val).strip()
        if val.upper() in ("NA", "N/A", "--", ""):
            return None
        return float(val)
    except (ValueError, TypeError):
        return None

def sanitize_cognitive_scores(raw_scores):
    """
    Sanitize cognitive scores for DB upload.
    Args:
        raw_scores (list of dict): Extracted from PDF.
    Returns:
        list of dict: Ready for DB upload.
    """
    results = []
    for d in raw_scores:
        out = d.copy()
        out['patient_score'] = safe_float(d.get('patient_score'))
        out['standard_score'] = safe_float(d.get('standard_score'))
        out['percentile'] = safe_float(d.get('percentile'))
        # Add any other numeric fields here as needed
        results.append(out)
    return results
