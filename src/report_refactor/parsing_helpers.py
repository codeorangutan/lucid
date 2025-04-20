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
        # Ensure lines is still an empty list if an error occurs before extraction
        lines = []

    # --- Debugging print statements (already added) ---
    print(f"Extracted {len(lines)} lines from {pdf_path}:")
    for idx, line in enumerate(lines):
        print(f"  [{idx}] {repr(line)}")
    # -------------------------------------------------

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
        tuple: (total_score, interpretation), responses
            - total_score: The total Epworth score (sum of all individual scores)
            - interpretation: The interpretation of the total score
            - responses: List of tuples (patient_id, question_number, situation, score, description)
    """
    responses = []
    
    # Only match lines for questions 1–8
    pattern = re.findall(r"^\s*([1-8])\s+(.+?)\s+(\d)\s*-\s*(.+)$", text, re.MULTILINE)
    
    # Use a dictionary to store the latest response for each question number
    question_responses = {}
    total_score = 0
    
    for qn, situation, val, desc in pattern:
        qn_int = int(qn)
        score_int = int(val)
        description = desc.strip()
        
        # Store the response
        question_responses[qn_int] = (patient_id, qn_int, situation.strip(), score_int, description)
        
    # Convert dictionary to list, ensuring each question appears only once
    responses = list(question_responses.values())
    
    # Calculate total score as the sum of all individual scores
    if responses:
        total_score = sum(response[3] for response in responses)
    
    # Debug information
    if len(pattern) > 8:
        logger.debug(f"Found {len(pattern)} Epworth questions (expected 8). Deduplicated to {len(responses)}.")
    
    # Check if the calculated total matches the reported total
    reported_match = re.search(r"Epworth Score\s*=\s*(\d+)", text)
    reported_score = int(reported_match.group(1)) if reported_match else None
    
    if reported_score is not None and total_score != reported_score and len(responses) == 8:
        logger.warning(f"Calculated Epworth total ({total_score}) doesn't match reported total ({reported_score})")
    
    # Use calculated total if we have all 8 questions, otherwise use reported total if available
    final_total = total_score if len(responses) == 8 else reported_score
    
    # Add interpretation based on total score
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
    
    return (final_total, interpretation), responses

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
        tuple: (inattentive_criteria_met, hyperactive_criteria_met, diagnosis, dsm_criteria_data)
            - inattentive_criteria_met: Number of inattentive criteria met (0-9)
            - hyperactive_criteria_met: Number of hyperactive criteria met (0-9)
            - diagnosis: ADHD diagnosis text
            - dsm_criteria_data: List of tuples (dsm_criterion, dsm_category, is_met)
    """
    try:
        # Import ASRS_DSM_mapper functionality - already handled at top level with try/except
        # from asrs_dsm_mapper import RESPONSE_SCORES, LOWER_THRESHOLD_QUESTIONS, is_met, DSM5_ASRS_MAPPING
        
        # Convert asrs_responses to a dictionary format expected by ASRS_DSM_mapper
        responses_dict = {}
        for _, question_num, _, response in asrs_responses:
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
        
        return (met_inattentive, met_hyperactive, diagnosis, dsm_criteria_data)
    except Exception as e:
        logger.error(f"Failed to extract DSM diagnosis: {e}")
        return (0, 0, "Error in Diagnosis", [])
