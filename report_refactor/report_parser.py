# src/report_refactor/report_parser.py

import logging
from typing import Dict, Any, List, Tuple, Optional
import os # Added for path joining

# Use explicit relative import
from .parsing_helpers import (
    extract_text_blocks, parse_basic_info, parse_cognitive_scores,
    parse_asrs_with_bounding_boxes, parse_epworth, extract_dsm_diagnosis,
    find_npq_pages, extract_npq_questions_pymupdf,
    extract_subtest_section, parse_subtests_new
)
try:
    from pdf_cognitive_parser import get_cognitive_subtests as pdf_get_cognitive_subtests
    PDF_PARSER_AVAILABLE = True
except ImportError:
    PDF_PARSER_AVAILABLE = False
    print("Warning: pdf_cognitive_parser.py not found. Subtest extraction may be limited.")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def parse_complete_cognitive_report(pdf_path: str) -> Optional[Dict[str, Any]]:
    """
    Orchestrates the complete parsing of a cognitive report PDF.

    This function calls various specialized parsing functions to extract
    all relevant information in a single pass, without interacting
    with the database.

    Args:
        pdf_path: The file path to the cognitive report PDF.

    Returns:
        A dictionary containing all extracted data structured by section
        (e.g., 'patient_info', 'cognitive_scores', 'subtests', 'asrs', 'npq', 'epworth', 'dsm'),
        or None if the PDF cannot be processed or essential data is missing.
    """
    logger.info(f"Starting complete parsing for PDF: {pdf_path}")
    parsed_data = {
        'patient_info': None,
        'cognitive_scores': [],
        'subtests': [],
        'asrs': [],
        'epworth': None,
        'npq': [],
        'dsm': []
    }

    try:
        # --- Stage 1: Basic Text Extraction ---
        lines = extract_text_blocks(pdf_path)
        if not lines:
            print(f"[DEBUG] extract_text_blocks returned: {lines}")
            logger.warning(f"Could not extract any text blocks from {pdf_path}.")
            return None
        raw_text = "\n".join(lines)
        logger.info(f"Extracted {len(lines)} text blocks.")

        # --- Stage 2: Parse Sections ---

        # Patient Info (Essential)
        patient_info_tuple = parse_basic_info(raw_text)
        if not patient_info_tuple or not patient_info_tuple[0]:
             logger.error(f"Essential patient information (ID) could not be parsed from {pdf_path}.")
             return None # Cannot proceed without patient ID
        patient_id, test_date, age, language = patient_info_tuple
        parsed_data['patient_info'] = {
            'patient_id': patient_id,
            'test_date': test_date,
            'age': age,
            'language': language
        }
        logger.info(f"Parsed Patient Info: ID {patient_id}")

        # Cognitive Scores
        parsed_data['cognitive_scores'] = parse_cognitive_scores(raw_text, patient_id)
        logger.info(f"Parsed {len(parsed_data['cognitive_scores'])} Cognitive Scores.")

        # Subtests (implementing the priority logic)
        cognitive_subtests = []
        # First try our new PDF parser (highest priority)
        if PDF_PARSER_AVAILABLE:
            logger.info("Attempting subtest extraction with pdf_cognitive_parser...")
            try:
                # Assuming pdf_get_cognitive_subtests returns list of tuples matching DB schema directly or needs minimal formatting
                cognitive_subtests = pdf_get_cognitive_subtests(pdf_path, patient_id, debug=False) # Set debug as needed
                if cognitive_subtests:
                    logger.info(f"Successfully extracted {len(cognitive_subtests)} subtests using pdf_cognitive_parser.")
                else:
                    logger.warning("pdf_cognitive_parser ran but returned no subtests.")
            except Exception as e:
                logger.warning(f"Error using pdf_cognitive_parser for subtests: {e}.")
                cognitive_subtests = []
        else:
            logger.info("Falling back to traditional text-based subtest extraction...")
            try:
                subtest_text = extract_subtest_section(pdf_path) # Assumes this function exists and works
                # Ensure parse_subtests_new returns data in the correct tuple format for the DB
                cognitive_subtests = parse_subtests_new(subtest_text, patient_id) # Assumes this exists
                if cognitive_subtests:
                    logger.info(f"Extracted {len(cognitive_subtests)} subtests using traditional method.")
                else:
                    logger.warning("Traditional subtest extraction returned no results.")
            except Exception as e:
                logger.warning(f"Error extracting subtests with traditional method: {e}")
                cognitive_subtests = []
        parsed_data['subtests'] = cognitive_subtests

        # ASRS
        # Assuming parse_asrs_with_bounding_boxes returns data ready for DB
        parsed_data['asrs'] = parse_asrs_with_bounding_boxes(pdf_path, patient_id)
        logger.info(f"Parsed {len(parsed_data['asrs'])} ASRS items.")

        # Epworth
        # Assuming parse_epworth returns data ready for DB
        parsed_data['epworth'] = parse_epworth(raw_text, patient_id) # Returns a tuple/dict? Adjust as needed
        logger.info(f"Parsed Epworth: {parsed_data['epworth']}") # Log appropriately based on return type

         # NPQ
        try:
             npq_pages = find_npq_pages(pdf_path) # Find relevant pages first
             if npq_pages:
                 # Assuming extract_npq_questions_pymupdf returns list of tuples ready for DB
                 parsed_data['npq'] = extract_npq_questions_pymupdf(pdf_path, npq_pages, patient_id)
                 logger.info(f"Parsed {len(parsed_data['npq'])} NPQ items.")
             else:
                 logger.warning("Could not find NPQ pages.")
        except Exception as e:
             logger.warning(f"Error during NPQ parsing: {e}")
             parsed_data['npq'] = []

        # --- Stage 3: Post-processing / Derived Data ---
        # DSM Diagnosis (uses parsed ASRS data)
        if parsed_data['asrs']:
           # Assuming extract_dsm_diagnosis returns data ready for DB
           parsed_data['dsm'] = extract_dsm_diagnosis(parsed_data['asrs'], patient_id)
           logger.info(f"Derived {len(parsed_data['dsm'])} DSM criteria results.")
        else:
           logger.info("Skipping DSM diagnosis as no ASRS data was parsed.")
           parsed_data['dsm'] = []

        # --- Final Validation ---
        # Already checked for patient_id earlier. Add more checks if needed.
        # Example: Check if at least some core data was found?
        # core_data_found = any([parsed_data['cognitive_scores'], parsed_data['subtests'], parsed_data['asrs']])
        # if not core_data_found:
        #     logger.warning(f"No core cognitive data (scores, subtests, ASRS) found in {pdf_path}.")
            # Decide if this constitutes a failure

        logger.info(f"Completed parsing stages for PDF: {pdf_path}")
        return parsed_data

    except FileNotFoundError:
        logger.error(f"PDF file not found: {pdf_path}")
        return None
    except Exception as e:
        logger.exception(f"An unexpected error occurred during parsing of {pdf_path}: {e}")
        # Optionally return partial data or None depending on desired robustness
        # return parsed_data # Return whatever was parsed before the error
        return None # Return None on any error

# Example usage (for testing this module directly)
if __name__ == '__main__':
    # You can add test code here, e.g.:
    # test_pdf = "path/to/your/test.pdf"
    # data = parse_complete_cognitive_report(test_pdf)
    # if data:
    #     print("Successfully parsed data:")
    #     import json
    #     print(json.dumps(data, indent=2))
    # else:
    #     print("Parsing failed.")
    pass
