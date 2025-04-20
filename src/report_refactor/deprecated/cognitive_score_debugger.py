#!/usr/bin/env python3
"""
Cognitive Score Debugger - Simplified version
"""

import os
import re
import pdfplumber
import logging
from pathlib import Path
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

def extract_cognitive_section(pdf_path):
    """Extract cognitive scores section using pdfplumber"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_text = []
            for page in pdf.pages[:3]:  # Only look at first 3 pages
                text = page.extract_text()
                if text:
                    all_text.append(text)
            
            full_text = "\n".join(all_text)
            
            # Find the cognitive section
            start_markers = ["Domain Scores", "Neurocognition Index"]
            end_markers = ["Clinical Examination", "DASS21 Scores"]
            
            # Find start of section
            start_pos = -1
            for marker in start_markers:
                pos = full_text.find(marker)
                if pos != -1:
                    start_pos = pos
                    break
            
            if start_pos == -1:
                return ""
                
            # Find end of section
            end_pos = len(full_text)
            for marker in end_markers:
                pos = full_text.find(marker, start_pos)
                if pos != -1:
                    end_pos = pos
                    break
            
            return full_text[start_pos:end_pos]
            
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return ""

def parse_cognitive_scores(cognitive_text, patient_id="test"):
    """Parse cognitive scores using the hierarchical structure of the tests"""
    scores = []
    current_test = None
    
    # Split into lines
    lines = [line.strip() for line in cognitive_text.split('\n') if line.strip()]
    
    for line in lines:
        # Try to match test header pattern
        test_match = re.match(r'^(.*?)\s*(?:\([A-Z]+\))?\s*Score\s*Standard\s*Percentile\s*$', line)
        if test_match:
            current_test = test_match.group(1).strip()
            continue
            
        # Try to match score pattern for sub-items
        if current_test:
            match = re.match(r'^(.*?)\s+(\d+|NA)\s+(\d+)\s+(\d+)\s*$', line)
            if match:
                sub_item = match.group(1).strip()
                if len(sub_item) > 3 and sub_item.isascii():
                    scores.append({
                        'patient_id': patient_id,
                        'test': current_test,
                        'sub_item': sub_item,
                        'patient_score': match.group(2),
                        'standard_score': match.group(3),
                        'percentile': match.group(4)
                    })
            elif len(line.split()) > 10:  # Likely a description paragraph
                current_test = None
    
    return scores

def main():
    parser = argparse.ArgumentParser(description='Extract cognitive scores from a PDF file.')
    parser.add_argument('pdf_path', help='Path to the PDF file')
    args = parser.parse_args()
    
    if not os.path.exists(args.pdf_path):
        logging.error(f"PDF file not found: {args.pdf_path}")
        return
    
    print(f"Processing: {args.pdf_path}")
    
    # Extract and parse
    cognitive_text = extract_cognitive_section(args.pdf_path)
    scores = parse_cognitive_scores(cognitive_text)
    
    # Print results
    print("\nExtracted Cognitive Scores:")
    print("=" * 50)
    if not scores:
        print("No cognitive scores found!")
    else:
        current_test = None
        for score in scores:
            if score['test'] != current_test:
                current_test = score['test']
                print(f"\n{current_test}")
                print("-" * len(current_test))
            print(f"{score['sub_item']}:")
            print(f"  Score: {score['patient_score']}")
            print(f"  Standard: {score['standard_score']}")
            print(f"  Percentile: {score['percentile']}")

if __name__ == "__main__":
    main()
