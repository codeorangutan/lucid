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

# ... (file truncated for brevity) ...

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
